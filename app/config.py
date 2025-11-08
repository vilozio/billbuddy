"""Configuration management for BillBuddy"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration"""

    # Telegram Bot
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")  # gpt-4o has vision capabilities

    # Google APIs - OAuth
    GOOGLE_OAUTH_CLIENT_PATH = os.getenv(
        "GOOGLE_OAUTH_CLIENT_PATH", "credentials/oauth-client.json"
    )
    GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

    # Application settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY = int(os.getenv("RETRY_DELAY", "2"))  # seconds

    @classmethod
    def validate(cls):
        """Validate that all required configuration is present"""
        required_vars = [
            ("TELEGRAM_BOT_TOKEN", cls.TELEGRAM_BOT_TOKEN),
            ("OPENAI_API_KEY", cls.OPENAI_API_KEY),
            ("GOOGLE_OAUTH_CLIENT_PATH", cls.GOOGLE_OAUTH_CLIENT_PATH),
            ("GOOGLE_DRIVE_FOLDER_ID", cls.GOOGLE_DRIVE_FOLDER_ID),
            ("GOOGLE_SHEET_ID", cls.GOOGLE_SHEET_ID),
        ]

        missing_vars = [
            var_name for var_name, var_value in required_vars if not var_value
        ]

        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}\n"
                "Please check your .env file and ensure all variables are set."
            )

        # Validate OAuth client file exists
        if (
            cls.GOOGLE_OAUTH_CLIENT_PATH
            and not Path(cls.GOOGLE_OAUTH_CLIENT_PATH).exists()
        ):
            raise ValueError(
                f"Google OAuth client file not found at: {cls.GOOGLE_OAUTH_CLIENT_PATH}"
            )

        return True
