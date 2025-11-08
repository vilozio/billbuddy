"""Google Sheets service for logging receipt data"""

from typing import List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import Config
from app.models.receipt import Receipt
from app.services.google_auth import GoogleAuthService
from app.utils.logger import setup_logger

logger = setup_logger(__name__, Config.LOG_LEVEL)


class GoogleSheetsService:
    """Service for logging receipt data to Google Sheets"""

    # Column headers for the sheet
    HEADERS = [
        "Date",
        "Merchant",
        "Amount",
        "Tax",
        "Payment Method",
        "Category",
        "Items",
        "Drive Link",
    ]

    def __init__(self):
        """Initialize Google Sheets service"""
        try:
            credentials = GoogleAuthService.get_credentials()
            self.service = build("sheets", "v4", credentials=credentials)
            self.spreadsheet_id = Config.GOOGLE_SHEET_ID
            logger.info("Google Sheets service initialized successfully")

            # Ensure headers are set
            self._ensure_headers()

        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets service: {e}")
            raise

    def _ensure_headers(self):
        """Ensure the spreadsheet has proper headers"""
        try:
            # Read the first row
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range="A1:H1")
                .execute()
            )

            values = result.get("values", [])

            # If no headers or incorrect headers, set them
            if not values or values[0] != self.HEADERS:
                logger.info("Setting up spreadsheet headers")
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range="A1:H1",
                    valueInputOption="RAW",
                    body={"values": [self.HEADERS]},
                ).execute()

                # Format headers (bold)
                requests = [
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": 0,
                                "startRowIndex": 0,
                                "endRowIndex": 1,
                            },
                            "cell": {
                                "userEnteredFormat": {"textFormat": {"bold": True}}
                            },
                            "fields": "userEnteredFormat.textFormat.bold",
                        }
                    }
                ]

                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id, body={"requests": requests}
                ).execute()

                logger.info("Headers set successfully")

        except HttpError as e:
            logger.warning(f"Could not check/set headers: {e}")

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def append_receipt(self, receipt: Receipt) -> bool:
        """
        Append receipt data to the spreadsheet

        Args:
            receipt: Receipt object with extracted data

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Appending receipt to Google Sheets: {receipt.merchant}")

            # Convert receipt to row format
            row_data = receipt.to_sheet_row()

            # Append to sheet
            body = {"values": [row_data]}

            result = (
                self.service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=self.spreadsheet_id,
                    range="A:H",
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",
                    body=body,
                )
                .execute()
            )

            logger.info(
                f"Receipt appended successfully. Updated {result.get('updates', {}).get('updatedRows', 0)} rows"
            )
            return True

        except HttpError as e:
            logger.error(f"HTTP error appending to sheet: {e}")
            return False
        except Exception as e:
            logger.error(f"Error appending to sheet: {e}", exc_info=True)
            return False

    def get_all_receipts(self) -> List[List]:
        """
        Get all receipt data from the spreadsheet

        Returns:
            List of rows (each row is a list of values)
        """
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range="A:H")
                .execute()
            )

            values = result.get("values", [])

            # Skip header row if present
            if values and values[0] == self.HEADERS:
                return values[1:]

            return values

        except HttpError as e:
            logger.error(f"Error reading from sheet: {e}")
            return []

    def clear_sheet(self) -> bool:
        """
        Clear all data from the sheet (keeping headers)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Clear everything except headers
            self.service.spreadsheets().values().clear(
                spreadsheetId=self.spreadsheet_id, range="A2:H"
            ).execute()

            logger.info("Sheet cleared successfully")
            return True

        except HttpError as e:
            logger.error(f"Error clearing sheet: {e}")
            return False
