import os
import asyncio
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

from src.modules.base import BaseModule
from src.modules.downloader.services import DownloaderService
from src.utils.queue_manager import QueueManager
from src.utils.logger import logger
import config

# Regular expression to identify supported media links
URL_PATTERN = re.compile(
    r'https?://(?:www\.)?(?:youtube\.com|youtu\.be|facebook\.com|fb\.watch|instagram\.com|tiktok\.com)/[^\s]+',
    re.IGNORECASE
)

# Limit concurrent download processing (network intensive)
download_queue_manager = QueueManager(max_concurrent=2)
downloader_service = DownloaderService()

# Ensure download directory is configured
os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)

class DownloaderModule(BaseModule):
    @property
    def name(self) -> str:
        return "downloader"

    def register_handlers(self, application: Application) -> None:
        # Command handler
        application.add_handler(CommandHandler("download", self.handle_download_cmd))
        
        # Link listener (intercepts text messages that match domains)
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(URL_PATTERN),
            self.handle_link_auto
        ))

    def _is_allowed(self, update: Update) -> bool:
        """Verifies if the user is authorized."""
        if not config.ALLOWED_USERS:
            return True
        user = update.effective_user
        if not user:
            return False
        user_id_str = str(user.id)
        username = user.username
        return user_id_str in config.ALLOWED_USERS or (username and username in config.ALLOWED_USERS)

    async def handle_download_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processes the /download command."""
        if not self._is_allowed(update):
            await update.message.reply_text("⛔ You are not authorized to use this bot.")
            return

        args = context.args
        if not args:
            await update.message.reply_text(
                "⚠️ **Usage:**\n"
                "• `/download <video_url>` to download video.\n"
                "• Alternatively, just send the link directly to the bot!\n\n"
                "ℹ️ _Supports YouTube, Instagram, Facebook, and TikTok!_"
            )
            return

        url = args[0]
        await self._process_video_download(update, url)

    async def handle_link_auto(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Automatically detects and processes media URLs sent in chat."""
        if not self._is_allowed(update):
            return # Ignore unauthorized users silently in auto mode

        # Extract the matched URL
        text = update.message.text
        match = URL_PATTERN.search(text)
        if match:
            url = match.group(0)
            await self._process_video_download(update, url)

    async def _process_video_download(self, update: Update, url: str):
        """Core download and upload task orchestrator."""
        message = update.message
        chat_id = update.effective_chat.id
        message_id = message.message_id
        job_id = f"dl_{chat_id}_{message_id}"

        # Initialize tracking variables
        video_path = None
        status_msg = None

        # 1. Queueing
        initial_pos = await download_queue_manager.acquire_slot(job_id)
        status_text = f"⏳ Link received. Added to download queue. Position: {initial_pos}"
        status_msg = await message.reply_text(status_text)

        queue_task = asyncio.create_task(download_queue_manager.start_job(job_id))
        last_pos = initial_pos

        try:
            # Monitor position updates
            while not queue_task.done():
                await asyncio.sleep(3)
                pos = await download_queue_manager.get_position(job_id)
                if pos > 0 and pos != last_pos:
                    last_pos = pos
                    try:
                        await status_msg.edit_text(f"⏳ Queued. Current download queue position: {pos}")
                    except TelegramError:
                        pass

            # Acquire execution slot
            await queue_task

            # 2. Downloading
            await status_msg.edit_text("📥 Fetching video from remote servers...")
            logger.info(f"Downloading video from URL={url} for job {job_id}...")
            
            # Run yt-dlp in a thread pool to keep asyncio non-blocking
            video_path, title = await asyncio.to_thread(
                downloader_service.download_video, url, config.DOWNLOAD_DIR
            )

            # 3. Size validation
            # Telegram Bot API upload cap is 50MB (52,428,800 bytes)
            file_size_bytes = os.path.getsize(video_path)
            file_size_mb = file_size_bytes / (1024 * 1024)
            
            if file_size_bytes > 52428800:
                logger.warning(f"File size {file_size_mb:.1f}MB exceeds limit for job {job_id}.")
                await status_msg.edit_text(
                    f"⚠️ **Limit Exceeded:**\n\n"
                    f"Downloaded: `{title}`\n"
                    f"Size: `{file_size_mb:.1f} MB`\n\n"
                    f"Telegram bot files are capped at **50 MB** maximum. Please choose a shorter clip/lower quality.",
                    parse_mode="Markdown"
                )
                return

            # 4. Uploading Video
            await status_msg.edit_text("📤 Uploading video to Telegram...")
            logger.info(f"Uploading video {video_path} ({file_size_mb:.1f}MB) for job {job_id}...")
            
            # Send file as video (so it renders inline with a player)
            await status_msg.delete()
            await message.reply_video(
                video=open(video_path, "rb"),
                caption=f"🎥 **{title}**\n\n⚡ _Downloaded successfully via SuvTools!_",
                supports_streaming=True,
                parse_mode="Markdown"
            )
            logger.info(f"Job {job_id} completed successfully.")

        except asyncio.CancelledError:
            logger.warning(f"Download job {job_id} was cancelled.")
            try:
                await status_msg.edit_text("❌ Download job was cancelled.")
            except TelegramError:
                pass
        except Exception as e:
            logger.exception(f"Error handling download for job {job_id}: {e}")
            try:
                await status_msg.edit_text(f"❌ Failed to download video: {str(e)}")
            except TelegramError:
                pass
        finally:
            # 5. Cleanup local video file
            if video_path and os.path.exists(video_path):
                try:
                    os.remove(video_path)
                    logger.debug(f"Removed temporary video file: {video_path}")
                except Exception as ex:
                    logger.warning(f"Failed to delete {video_path}: {ex}")

            # Always release download slot
            await download_queue_manager.release_slot(job_id)
