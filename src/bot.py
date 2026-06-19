from telegram.ext import Application, ApplicationBuilder, ContextTypes
from src.utils.logger import logger
from src.modules.transcriber import TranscriberModule
from src.modules.translator import TranslatorModule
from src.modules.monitor import MonitorModule
import config

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a message if possible."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

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

    # Register global error handler
    app.add_error_handler(error_handler)
    logger.info("All handlers and modules loaded successfully.")

    return app
