"""BillBuddy - Receipt Processing Telegram Bot"""

import sys

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from app.bot.commands import (
    help_command,
    start_command,
    status_command,
    unknown_command,
)
from app.bot.csv_handlers import build_csv_conversation
from app.bot.handlers import error_handler, handle_document, handle_photo, handle_text
from app.bot.settings_commands import (
    delete_scenario_command,
    receipts_off_command,
    receipts_on_command,
    scenarios_command,
    undo_command,
)
from app.config import Config
from app.db import init_db
from app.utils.logger import setup_logger

logger = setup_logger(__name__, Config.LOG_LEVEL)


def main():
    """Main entry point for the bot"""
    try:
        # Validate configuration
        logger.info("Validating configuration...")
        Config.validate()
        logger.info("Configuration validated successfully")

        # Initialize local database (statement scenarios + runtime settings)
        init_db()

        # Create application
        logger.info("Initializing Telegram bot...")
        application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()

        # Register command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("status", status_command))

        # Statement / settings commands
        application.add_handler(CommandHandler("receipts_on", receipts_on_command))
        application.add_handler(CommandHandler("receipts_off", receipts_off_command))
        application.add_handler(CommandHandler("scenarios", scenarios_command))
        application.add_handler(CommandHandler("delete_scenario", delete_scenario_command))
        application.add_handler(CommandHandler("undo", undo_command))

        # CSV statement upload + scenario setup wizard (handles .csv documents).
        # Registered before the receipt document handler so CSVs are routed here.
        application.add_handler(build_csv_conversation())

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
