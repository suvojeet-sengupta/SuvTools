import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError

from src.modules.base import BaseModule
from src.modules.translator.services import TranslationService
from src.utils.logger import logger
import config

translation_service = TranslationService()

class TranslatorModule(BaseModule):
    @property
    def name(self) -> str:
        return "translator"

    def register_handlers(self, application: Application) -> None:
        application.add_handler(CommandHandler("translate", self.handle_translate))
        application.add_handler(CommandHandler("languages", self.handle_languages))

    def _is_allowed(self, update: Update) -> bool:
        """Helper to verify user permission."""
        if not config.ALLOWED_USERS:
            return True
        user = update.effective_user
        if not user:
            return False
        user_id_str = str(user.id)
        username = user.username
        return user_id_str in config.ALLOWED_USERS or (username and username in config.ALLOWED_USERS)

    async def handle_translate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processes the /translate command."""
        if not self._is_allowed(update):
            await update.message.reply_text("⛔ You are not authorized to use this bot.")
            return

        message = update.message
        args = context.args

        target_lang = "en"
        text_to_translate = ""

        # Scenario 1: User replies to a message with '/translate <lang>'
        if message.reply_to_message:
            text_to_translate = message.reply_to_message.text or message.reply_to_message.caption
            if args:
                target_lang = args[0].lower()
        # Scenario 2: User provides translation details directly like '/translate <lang> <text>'
        else:
            if len(args) < 2:
                help_message = (
                    "🌐 **Translation Tool Usage:**\n\n"
                    "• `/translate <lang_code> <text>` to translate text directly.\n"
                    "  _Example:_ `/translate es Hello, how are you?`\n\n"
                    "• Reply to any text message or transcription with `/translate <lang_code>` to translate it.\n"
                    "  _Example (replying to a message):_ `/translate hi`\n\n"
                    "• Use `/languages` to view common language codes."
                )
                await message.reply_text(help_message, parse_mode="Markdown")
                return
            
            target_lang = args[0].lower()
            text_to_translate = " ".join(args[1:])

        if not text_to_translate or not text_to_translate.strip():
            await message.reply_text("⚠️ No valid text found to translate.")
            return

        status_msg = await message.reply_text("⏳ Translating...")
        try:
            translation = await asyncio.to_thread(
                translation_service.translate, text_to_translate, target_lang
            )
            # Send result
            response_text = f"🌐 **Translated Text ({target_lang}):**\n\n{translation}"
            # If output is too long, send as text file (same logic as transcription)
            if len(response_text) <= 4000:
                await status_msg.edit_text(response_text, parse_mode="Markdown")
            else:
                await status_msg.delete()
                # Create a temporary file
                import uuid
                txt_path = os.path.join(config.DOWNLOAD_DIR, f"translation_{uuid.uuid4()}.txt")
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(translation)
                await message.reply_document(
                    document=open(txt_path, "rb"),
                    filename=f"translation_{target_lang}.txt",
                    caption=f"📄 Translation output was too long to send as a message."
                )
                if os.path.exists(txt_path):
                    os.remove(txt_path)
        except Exception as e:
            logger.exception(f"Error handling translation: {e}")
            try:
                await status_msg.edit_text(f"❌ Translation failed: {str(e)}")
            except TelegramError:
                pass

    async def handle_languages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Displays common ISO codes for translation."""
        supported_langs = (
            "🌐 **Common Language Codes:**\n\n"
            "• `en` - English\n"
            "• `es` - Spanish\n"
            "• `fr` - French\n"
            "• `de` - German\n"
            "• `it` - Italian\n"
            "• `ru` - Russian\n"
            "• `zh` - Chinese\n"
            "• `ja` - Japanese\n"
            "• `hi` - Hindi\n"
            "• `ar` - Arabic\n"
            "• `pt` - Portuguese\n"
            "• `tr` - Turkish"
        )
        await update.message.reply_text(supported_langs, parse_mode="Markdown")
