from telegram import Update
from telegram.ext import Application, ApplicationBuilder, ContextTypes, MessageHandler, filters
from src.utils.logger import logger
from src.modules.transcriber import TranscriberModule
from src.modules.translator import TranslatorModule
from src.modules.monitor import MonitorModule
import config

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
        "💻 **VPS Diagnostics** (For Admins):\n"
        "• Use `/status` to check bot health status.\n"
        "• Use `/sysinfo` to view system resources (CPU load, memory, disk load).\n\n"
        "📚 Type `/help` for detailed instructions."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

def create_app() -> Application:
    """Builds and returns the Application instance with loaded modules."""
    if not config.TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN is not set. Cannot start bot.")
        raise ValueError("Missing TELEGRAM_BOT_TOKEN config.")

    # Initialize the Application
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()

    # List of modular extensions to load
    # To add more tools to this multitool bot, simply implement BaseModule and add here
    modules = [
        TranscriberModule(),
        TranslatorModule(),
        MonitorModule()
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
