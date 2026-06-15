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


class GenericSheetsService:
    """Append arbitrary rows to a named tab of any spreadsheet.

    Unlike :class:`GoogleSheetsService` (hard-wired to the receipt sheet, ``A:H``
    range and fixed headers), this writes to a caller-supplied spreadsheet/tab
    with a caller-supplied header. Used by the statement (CSV) pipeline.
    """

    def __init__(self):
        try:
            credentials = GoogleAuthService.get_credentials()
            self.service = build("sheets", "v4", credentials=credentials)
            logger.info("Generic Sheets service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Generic Sheets service: {e}")
            raise

    def create_spreadsheet(self, title: str) -> str:
        """Create a new spreadsheet and return its id."""
        spreadsheet = (
            self.service.spreadsheets()
            .create(body={"properties": {"title": title}}, fields="spreadsheetId")
            .execute()
        )
        spreadsheet_id = spreadsheet["spreadsheetId"]
        logger.info(f"Created spreadsheet '{title}' ({spreadsheet_id})")
        return spreadsheet_id

    def get_spreadsheet_title(self, spreadsheet_id: str) -> str:
        """Return the title of a spreadsheet (raises if inaccessible)."""
        meta = (
            self.service.spreadsheets()
            .get(spreadsheetId=spreadsheet_id, fields="properties.title")
            .execute()
        )
        return meta["properties"]["title"]

    def _ensure_tab(self, spreadsheet_id: str, tab: str):
        """Create the tab if it does not already exist."""
        try:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": tab}}}]},
            ).execute()
            logger.info(f"Created tab '{tab}' in spreadsheet {spreadsheet_id}")
        except HttpError as e:
            # A duplicate-tab error is expected and fine; re-raise anything else.
            if "already exists" in str(e).lower():
                logger.debug(f"Tab '{tab}' already exists")
            else:
                raise

    def _ensure_header(self, spreadsheet_id: str, tab: str, header: List[str]):
        """Write ``header`` to row 1 if the tab is empty or has a different header."""
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=f"'{tab}'!1:1")
            .execute()
        )
        existing = result.get("values", [[]])
        if not existing or existing[0] != header:
            self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{tab}'!A1",
                valueInputOption="RAW",
                body={"values": [header]},
            ).execute()
            logger.info(f"Set header on tab '{tab}'")

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def append_rows(
        self, spreadsheet_id: str, tab: str, header: List[str], rows: List[List]
    ) -> int:
        """Ensure the tab/header exist, then append ``rows``. Returns rows appended."""
        self._ensure_tab(spreadsheet_id, tab)
        self._ensure_header(spreadsheet_id, tab, header)

        if not rows:
            return 0

        result = (
            self.service.spreadsheets()
            .values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=f"'{tab}'!A:A",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": rows},
            )
            .execute()
        )
        appended = result.get("updates", {}).get("updatedRows", 0)
        logger.info(f"Appended {appended} rows to tab '{tab}'")
        return appended
