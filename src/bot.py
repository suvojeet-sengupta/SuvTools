import os
import shutil
import asyncio
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, ContextTypes, MessageHandler, filters
from src.utils.logger import logger
from src.modules.transcriber import TranscriberModule
from src.modules.translator import TranslatorModule
from src.modules.monitor import MonitorModule
from src.modules.monitor.server import DashboardServer
from src.modules.downloader import DownloaderModule
from src.modules.devutils import DevUtilsModule
from src.modules.imgcompressor import ImageCompressorModule
import config

# Create single instance of the Live Diagnostics Server
dashboard_server = DashboardServer()

async def post_init(application: Application) -> None:
    """Triggered on bot startup. Starts the HTTP/WS diagnostics server."""
    asyncio.create_task(dashboard_server.start())

async def post_shutdown(application: Application) -> None:
    """Triggered on bot shutdown. Closes the HTTP/WS diagnostics server."""
    await dashboard_server.stop()

def startup_cleanup() -> None:
    """Wipes all contents of the download directory at boot time to prevent resource leakage."""
    if os.path.exists(config.DOWNLOAD_DIR):
        logger.info(f"Running startup cleanup for directory: {config.DOWNLOAD_DIR}")
        for item in os.listdir(config.DOWNLOAD_DIR):
            item_path = os.path.join(config.DOWNLOAD_DIR, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            except Exception as e:
                logger.warning(f"Failed to clear {item_path} during startup: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a message if possible."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

async def fallback_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Replies to any unrecognized plain text messages with a quick helper menu."""
    help_text = (
        "👋 **Hello! I am a Multitool Bot.**\n\n"
        "Here is what I can do for you:\n\n"
        "🎙️ **Audio-to-Text Transcription**:\n"
        "Send or forward me any **Voice Note**, **Audio File**, or **Video/Audio Document** and I will transcribe it line-by-line with precise timestamps.\n\n"
        "🌐 **Language Translation**:\n"
        "Use `/translate <lang_code> <text>` or reply to any transcription or message with `/translate <lang_code>` to translate it.\n"
        "• _Use `/languages` to see supported language codes._\n\n"
        "🛠️ **Developer Text Utilities**:\n"
        "• `/base64 <encode/decode> <text>`\n"
        "• `/url <encode/decode> <text>`\n"
        "• `/json <beautify/minify> <json_text>`\n"
        "• `/hash <sha256/md5> <text>`\n"
        "• _(You can also reply to any message with these commands)_\n\n"
        "📉 **Image Compressor & Converter**:\n"
        "Send or forward any photo/image document, and I will prompt you with inline options to compress or convert format (JPEG, PNG, WebP) on demand.\n\n"
        "💻 **VPS Diagnostics** (For Admins):\n"
        "• Use `/status` to check bot health status.\n"
        "• Use `/sysinfo` to view system resources (CPU load, memory, disk load).\n\n"
        "📚 Type `/help` for detailed instructions."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

def create_app() -> Application:
    """Builds and returns the Application instance with loaded modules."""
    # Clear any residual downloaded files from past runs
    startup_cleanup()

    if not config.TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN is not set. Cannot start bot.")
        raise ValueError("Missing TELEGRAM_BOT_TOKEN config.")

    # Initialize the Application with post_init and post_shutdown hooks
    app = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # List of modular extensions to load
    # To add more tools to this multitool bot, simply implement BaseModule and add here
    modules = [
        TranscriberModule(),
        TranslatorModule(),
        MonitorModule(),
        DevUtilsModule(),
        ImageCompressorModule()
        # DownloaderModule() - Disabled for now
    ]

    # Load each module
    for module in modules:
        logger.info(f"Loading modular tool: '{module.name}'")
        module.register_handlers(app)

    # Register fallback handler for general text messages (non-commands)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_text_handler))

    # Register global error handler
    app.add_error_handler(error_handler)
    logger.info("All handlers and modules loaded successfully.")

    return app
