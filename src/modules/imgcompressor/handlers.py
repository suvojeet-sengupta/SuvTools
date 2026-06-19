import os
import asyncio
import uuid
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TelegramError

from src.modules.base import BaseModule
from src.utils.logger import logger
import config

# Define specific image file filter
IMAGE_FILTER = (
    filters.PHOTO | 
    filters.Document.IMAGE | 
    filters.Document.FileExtension("png") | 
    filters.Document.FileExtension("jpg") | 
    filters.Document.FileExtension("jpeg") | 
    filters.Document.FileExtension("webp")
)

# Ensure downloads path exists
os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)

class ImageCompressorModule(BaseModule):
    @property
    def name(self) -> str:
        return "imgcompressor"

    def register_handlers(self, application: Application) -> None:
        # Image detector
        application.add_handler(MessageHandler(IMAGE_FILTER, self.handle_image_received))
        
        # Button click handler
        application.add_handler(CallbackQueryHandler(self.handle_callback, pattern="^img_"))

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

    async def handle_image_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Called when a photo or image document is sent in chat."""
        if not self._is_allowed(update):
            return

        message = update.message
        file_id = ""
        file_name = "image.png"

        # Extract the highest resolution photo version or document details
        if message.photo:
            file_id = message.photo[-1].file_id
            file_name = f"photo_{message.message_id}.jpg"
        elif message.document:
            file_id = message.document.file_id
            file_name = message.document.file_name or "image.png"

        # Cache file ID metadata in user session storage (saves VPS disk space until they click)
        context.user_data['pending_img_id'] = file_id
        context.user_data['pending_img_name'] = file_name

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📉 Compress (Medium - 50%)", callback_data="img_comp_50"),
                InlineKeyboardButton("📉 Compress (High - 20%)", callback_data="img_comp_20")
            ],
            [
                InlineKeyboardButton("🔄 Convert to WebP", callback_data="img_conv_webp"),
                InlineKeyboardButton("🔄 Convert to PNG", callback_data="img_conv_png"),
                InlineKeyboardButton("🔄 Convert to JPEG", callback_data="img_conv_jpg")
            ]
        ])

        await message.reply_text(
            f"📸 **Image received:** `{file_name}`\n"
            "Select an operation below to perform compression or convert formats:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processes the button selections for compression and conversion."""
        query = update.callback_query
        await query.answer()

        if not self._is_allowed(update):
            await query.message.reply_text("⛔ You are not authorized.")
            return

        file_id = context.user_data.get('pending_img_id')
        original_name = context.user_data.get('pending_img_name', 'image.png')

        if not file_id:
            await query.message.edit_text("⚠️ Session expired. Please send the image again.")
            return

        # Clear session storage once processed
        context.user_data.pop('pending_img_id', None)
        context.user_data.pop('pending_img_name', None)

        action = query.data
        status_msg = await query.message.reply_text("📥 Downloading image from Telegram...")

        # Setup local file paths
        _, ext = os.path.splitext(original_name)
        if not ext:
            ext = ".jpg"
            
        input_path = os.path.join(config.DOWNLOAD_DIR, f"in_{uuid.uuid4()}{ext}")
        output_path = None

        try:
            # Download file on click
            telegram_file = await context.bot.get_file(file_id)
            await telegram_file.download_to_drive(input_path)

            await status_msg.edit_text("⚙️ Processing image details...")
            logger.info(f"Processing image {original_name} for action '{action}'")

            # Determine operations
            if action == "img_comp_50":
                output_path = os.path.join(config.DOWNLOAD_DIR, f"compressed_{uuid.uuid4()}{ext}")
                await asyncio.to_thread(self._compress, input_path, output_path, 50)
                caption = "📉 **Image compressed to 50% quality.**"
                out_name = f"compressed_{original_name}"
            elif action == "img_comp_20":
                output_path = os.path.join(config.DOWNLOAD_DIR, f"compressed_{uuid.uuid4()}{ext}")
                await asyncio.to_thread(self._compress, input_path, output_path, 20)
                caption = "📉 **Image compressed to 20% quality.**"
                out_name = f"compressed_{original_name}"
            elif action == "img_conv_webp":
                output_path = os.path.join(config.DOWNLOAD_DIR, f"converted_{uuid.uuid4()}.webp")
                await asyncio.to_thread(self._convert, input_path, output_path, "WEBP")
                caption = "🔄 **Converted to WebP format.**"
                out_name = f"{os.path.splitext(original_name)[0]}.webp"
            elif action == "img_conv_png":
                output_path = os.path.join(config.DOWNLOAD_DIR, f"converted_{uuid.uuid4()}.png")
                await asyncio.to_thread(self._convert, input_path, output_path, "PNG")
                caption = "🔄 **Converted to PNG format.**"
                out_name = f"{os.path.splitext(original_name)[0]}.png"
            elif action == "img_conv_jpg":
                output_path = os.path.join(config.DOWNLOAD_DIR, f"converted_{uuid.uuid4()}.jpg")
                await asyncio.to_thread(self._convert, input_path, output_path, "JPEG")
                caption = "🔄 **Converted to JPEG format.**"
                out_name = f"{os.path.splitext(original_name)[0]}.jpg"
            else:
                raise ValueError("Invalid callback selection.")

            # Send output document
            await status_msg.edit_text("📤 Uploading output image...")
            await query.message.reply_document(
                document=open(output_path, "rb"),
                filename=out_name,
                caption=f"{caption}\n\n⚡ _Processed via SuvTools!_"
            )
            await status_msg.delete()
            # Clean up the original options menu
            await query.message.delete()

        except Exception as e:
            logger.exception(f"Failed to process image operation: {e}")
            try:
                await status_msg.edit_text(f"❌ Image operation failed: {str(e)}")
            except TelegramError:
                pass
        finally:
            # Delete local files immediately after send
            if os.path.exists(input_path):
                os.remove(input_path)
            if output_path and os.path.exists(output_path):
                os.remove(output_path)

    def _compress(self, in_path: str, out_path: str, quality: int):
        """Performs Pillow compression."""
        with Image.open(in_path) as img:
            # JPEG doesn't support RGBA, convert to RGB
            if img.mode in ("RGBA", "P") and out_path.lower().endswith(('.jpg', '.jpeg')):
                img = img.convert("RGB")
            img.save(out_path, quality=quality, optimize=True)

    def _convert(self, in_path: str, out_path: str, fmt: str):
        """Performs format conversion using Pillow."""
        with Image.open(in_path) as img:
            # JPEG doesn't support RGBA, convert to RGB
            if img.mode in ("RGBA", "P") and fmt.upper() == "JPEG":
                img = img.convert("RGB")
            img.save(out_path, format=fmt)
