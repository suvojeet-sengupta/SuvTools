import sys
from src.bot import create_app
from src.utils.logger import logger

def main():
    try:
        logger.info("Initializing Bot Services...")
        app = create_app()
        
        logger.info("Starting Polling Loop. Bot is now online!")
        app.run_polling()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user interrupt.")
    except Exception as e:
        logger.critical(f"Unhandled critical failure at startup: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
