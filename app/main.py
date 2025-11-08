"""BillBuddy - Receipt Processing Telegram Bot"""

import sys

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from app.bot.commands import (
    help_command,
    start_command,
    status_command,
    unknown_command,
)
from app.bot.handlers import error_handler, handle_document, handle_photo, handle_text
from app.config import Config
from app.utils.logger import setup_logger

logger = setup_logger(__name__, Config.LOG_LEVEL)


def main():
    """Main entry point for the bot"""
    try:
        # Validate configuration
        logger.info("Validating configuration...")
        Config.validate()
        logger.info("Configuration validated successfully")

        # Create application
        logger.info("Initializing Telegram bot...")
        application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()

        # Register command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("status", status_command))

        # Register message handlers
        # Photos
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

        # Documents (PDFs)
        application.add_handler(MessageHandler(filters.Document.PDF, handle_document))

        # Text messages (not commands)
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
        )

        # Unknown commands
        application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

        # Error handler
        application.add_error_handler(error_handler)

        # Start the bot
        logger.info("Starting BillBuddy bot...")
        logger.info("Bot is running. Press Ctrl+C to stop.")

        # Run the bot until Ctrl+C
        application.run_polling(allowed_updates=["message"])

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
