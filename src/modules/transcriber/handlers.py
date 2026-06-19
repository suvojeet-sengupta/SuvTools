import os
import asyncio
import uuid
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

from src.modules.base import BaseModule
from src.modules.transcriber.services import TranscriptionService
from src.modules.transcriber.utils import convert_to_wav
from src.utils.queue_manager import QueueManager
from src.utils.logger import logger
import config

# Initialize global managers for this module
queue_manager = QueueManager(max_concurrent=config.MAX_CONCURRENT_JOBS)
transcription_service = TranscriptionService()

# Ensure download directory exists
os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)

class TranscriberModule(BaseModule):
    @property
    def name(self) -> str:
        return "transcriber"

    def register_handlers(self, application: Application) -> None:
        # Help/start commands
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))

        # Media message handlers
        # We accept voice, audio, and documents
        application.add_handler(MessageHandler(
            filters.VOICE | filters.AUDIO | filters.Document.ALL,
            self.handle_media
        ))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome command."""
        user = update.effective_user
        logger.info(f"User {user.id} ({user.username}) started the bot.")
        
        welcome_text = (
            "🎙️ **Welcome to the Automated Transcription Bot!**\n\n"
            "Simply send or forward any **Voice Note**, **Audio File**, or **Video/Audio Document** to me. "
            "I will transcribe the contents and provide precise timestamps in the following format:\n"
            "`[MM:SS.cc -> MM:SS.cc] Transcribed Text`\n\n"
            "⚡ **Specs & Optimizations:**\n"
            "• Running *faster-whisper* (small)\n"
            "• CPU-optimized (int8 quantization)\n"
            "• Voice Activity Detection (VAD) enabled to skip silence"
        )
        await update.message.reply_text(welcome_text, parse_mode="Markdown")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command."""
        help_text = (
            "⚙️ **How to Use:**\n\n"
            "1. **Voice Notes**: Tap and record a voice message.\n"
            "2. **Audio Files**: Send an MP3, WAV, M4A, OGG, etc.\n"
            "3. **Documents**: Upload files directly as attachments. I can even extract audio and transcribe video files!\n\n"
            "🔒 *Note: Only authorized users can run transcriptions if access limits are configured.*"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")

    def _is_allowed(self, update: Update) -> bool:
        """Verifies if the user is authorized to use the bot."""
        if not config.ALLOWED_USERS:
            return True
        user = update.effective_user
        if not user:
            return False
        
        user_id_str = str(user.id)
        username = user.username
        
        if user_id_str in config.ALLOWED_USERS:
            return True
        if username and username in config.ALLOWED_USERS:
            return True
            
        return False

    async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processes incoming Voice, Audio, or Document messages."""
        if not self._is_allowed(update):
            await update.message.reply_text("⛔ You are not authorized to use this bot.")
            return

        message = update.message
        file_obj = None
        file_type = ""
        file_name = "audio"

        # Determine media type and extract file object
        if message.voice:
            file_obj = message.voice
            file_type = "voice"
            file_name = "voice_note"
        elif message.audio:
            file_obj = message.audio
            file_type = "audio"
            file_name = message.audio.file_name or "audio"
        elif message.document:
            file_obj = message.document
            file_type = "document"
            file_name = message.document.file_name or "document"
            
            # Basic validation for document types: check file extension
            allowed_extensions = {
                '.mp3', '.wav', '.m4a', '.ogg', '.aac', '.flac', '.opus',
                '.mp4', '.mkv', '.avi', '.mov', '.webm', '.3gp'
            }
            _, ext = os.path.splitext(file_name.lower())
            if ext not in allowed_extensions and not message.document.mime_type.startswith(('audio/', 'video/')):
                await update.message.reply_text(
                    "⚠️ Unsupported document type. Please send an audio or video file."
                )
                return
        else:
            # Not a supported media type
            return

        chat_id = update.effective_chat.id
        message_id = message.message_id
        job_id = f"{chat_id}_{message_id}"

        # Initialize temporary paths
        _, ext = os.path.splitext(file_name)
        if not ext:
            ext = ".ogg" if file_type == "voice" else ".mp3"
            
        input_path = os.path.join(config.DOWNLOAD_DIR, f"in_{uuid.uuid4()}{ext}")
        wav_path = os.path.join(config.DOWNLOAD_DIR, f"proc_{uuid.uuid4()}.wav")
        txt_path = os.path.join(config.DOWNLOAD_DIR, f"transcript_{uuid.uuid4()}.txt")

        # 1. Queueing
        initial_pos = await queue_manager.acquire_slot(job_id)
        status_text = f"⏳ Audio received. Added to queue. Position: {initial_pos}"
        status_msg = await message.reply_text(status_text)

        queue_task = asyncio.create_task(queue_manager.start_job(job_id))
        last_pos = initial_pos

        try:
            # Monitor position until job starts
            while not queue_task.done():
                await asyncio.sleep(3)
                pos = await queue_manager.get_position(job_id)
                if pos > 0 and pos != last_pos:
                    last_pos = pos
                    try:
                        await status_msg.edit_text(f"⏳ Queued. Current position: {pos}")
                    except TelegramError:
                        pass # Ignore if message edits fail or are rate-limited

            # Complete task block
            await queue_task
            
            # 2. Downloading
            await status_msg.edit_text("📥 Audio received, downloading...")
            logger.info(f"Downloading file for job {job_id}...")
            telegram_file = await file_obj.get_file()
            await telegram_file.download_to_drive(input_path)
            logger.info(f"Downloaded file to {input_path}")

            # 3. Preprocessing (FFmpeg)
            await status_msg.edit_text("🔄 Optimizing audio format for Whisper...")
            logger.info(f"Preprocessing audio for job {job_id}...")
            conversion_success = await asyncio.to_thread(convert_to_wav, input_path, wav_path)
            if not conversion_success:
                raise RuntimeError("Audio pre-processing via FFmpeg failed.")

            # 4. Transcription (Whisper)
            await status_msg.edit_text("🎙️ Transcribing your audio, please wait...")
            logger.info(f"Transcribing {wav_path} for job {job_id}...")
            
            # Run blocking Whisper transcription in a threadpool to keep asyncio loop alive
            transcript = await asyncio.to_thread(transcription_service.transcribe, wav_path)
            
            if not transcript or not transcript.strip():
                await status_msg.edit_text("🚫 Transcription complete. No speech was detected in the audio.")
                return

            # 5. Smart Response Delivery
            logger.info(f"Transcription complete for job {job_id}. Transcript length: {len(transcript)} chars.")
            if len(transcript) <= 4000:
                # Direct reply
                await status_msg.delete()
                await message.reply_text(
                    f"📝 **Transcription:**\n\n{transcript}",
                    parse_mode="Markdown"
                )
            else:
                # Text is too long; save to file and upload as document
                await status_msg.edit_text("✍️ Formatting transcript into document...")
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(f"Transcription of: {file_name}\n")
                    f.write("=" * 40 + "\n\n")
                    f.write(transcript)

                # Send file
                await status_msg.delete()
                await message.reply_document(
                    document=open(txt_path, "rb"),
                    filename=f"transcript_{os.path.splitext(file_name)[0]}.txt",
                    caption="📄 Transcript is too long for a text message. Download the attachment above!"
                )

        except asyncio.CancelledError:
            logger.warning(f"Job {job_id} was cancelled.")
            try:
                await status_msg.edit_text("❌ Transcription job was cancelled.")
            except TelegramError:
                pass
        except Exception as e:
            logger.exception(f"Error processing job {job_id}: {e}")
            try:
                await status_msg.edit_text(f"❌ Error occurred during transcription: {str(e)}")
            except TelegramError:
                pass
        finally:
            # 6. Cleanup temp files and release queue slot
            logger.info(f"Running cleanup routine for job {job_id}...")
            
            # Delete temporary download file
            if os.path.exists(input_path):
                try:
                    os.remove(input_path)
                    logger.debug(f"Deleted {input_path}")
                except Exception as ex:
                    logger.warning(f"Failed to delete {input_path}: {ex}")

            # Delete converted wav file
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                    logger.debug(f"Deleted {wav_path}")
                except Exception as ex:
                    logger.warning(f"Failed to delete {wav_path}: {ex}")

            # Delete formatted transcript txt file
            if os.path.exists(txt_path):
                try:
                    os.remove(txt_path)
                    logger.debug(f"Deleted {txt_path}")
                except Exception as ex:
                    logger.warning(f"Failed to delete {txt_path}: {ex}")

            # Always release the queue slot
            await queue_manager.release_slot(job_id)
            logger.info(f"Job {job_id} fully cleaned up.")
