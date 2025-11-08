"""Google OAuth authentication service"""

import os
import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import Config
from app.utils.logger import setup_logger

logger = setup_logger(__name__, Config.LOG_LEVEL)


class GoogleAuthService:
    """Handles OAuth authentication for Google services"""

    SCOPES = [
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/spreadsheets",
    ]

    TOKEN_FILE = "credentials/token.pickle"

    @classmethod
    def get_credentials(cls) -> Credentials:
        """
        Get valid user credentials from storage or run OAuth flow

        Returns:
            Google OAuth2 Credentials object
        """
        creds = None

        # Try to load existing credentials
        if os.path.exists(cls.TOKEN_FILE):
            with open(cls.TOKEN_FILE, "rb") as token:
                creds = pickle.load(token)
                logger.debug("Loaded existing credentials from token file")

        # If no valid credentials, run OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired credentials")
                creds.refresh(Request())
            else:
                logger.info("Running OAuth authentication flow")
                flow = InstalledAppFlow.from_client_secrets_file(
                    Config.GOOGLE_OAUTH_CLIENT_PATH, cls.SCOPES
                )
                creds = flow.run_local_server(port=0)
                logger.info("OAuth authentication successful")

            # Save credentials for next run
            with open(cls.TOKEN_FILE, "wb") as token:
                pickle.dump(creds, token)
                logger.debug("Saved credentials to token file")

        return creds
