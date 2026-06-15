"""Receipt processing orchestrator service"""
from typing import Optional
from pathlib import Path

from app.models.receipt import Receipt
from app.services.openai_service import OpenAIService
from app.services.google_drive import GoogleDriveService
from app.services.google_sheets import GoogleSheetsService
from app.services import scenario_store
from app.utils.logger import setup_logger
from app.config import Config

logger = setup_logger(__name__, Config.LOG_LEVEL)


class ReceiptProcessor:
    """
    Orchestrator service that coordinates receipt processing pipeline:
    1. Extract data using OpenAI
    2. Upload to Google Drive
    3. Log to Google Sheets
    """
    
    def __init__(self):
        """Initialize all required services"""
        try:
            self.openai_service = OpenAIService()
            self.drive_service = GoogleDriveService()
            self.sheets_service = GoogleSheetsService()
            logger.info("Receipt processor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize receipt processor: {e}")
            raise
    
    def process_receipt(
        self, file_path: str, user_id: Optional[int] = None
    ) -> Optional[Receipt]:
        """
        Process a receipt file through the complete pipeline

        Args:
            file_path: Path to the receipt file (image or PDF)
            user_id: Telegram user id, used to log the action for /undo

        Returns:
            Processed Receipt object, or None if processing fails
        """
        try:
            logger.info(f"Starting receipt processing pipeline for: {file_path}")
            
            # Step 1: Extract data from receipt using OpenAI
            file_extension = Path(file_path).suffix.lower()
            
            if file_extension == '.pdf':
                receipt = self.openai_service.process_receipt_pdf(file_path)
            else:
                # Assume image format (jpg, jpeg, png, etc.)
                receipt = self.openai_service.process_receipt_image(file_path)
            
            if not receipt:
                logger.error("Failed to extract data from receipt")
                return None
            
            logger.info(f"Extracted receipt data: {receipt.merchant}, ${receipt.total}")
            
            # Step 2: Upload to Google Drive
            upload = self.drive_service.upload_receipt(
                file_path=file_path,
                receipt_date=receipt.date,
                merchant_name=receipt.merchant,
                amount=receipt.total
            )

            if not upload:
                logger.error("Failed to upload receipt to Google Drive")
                return None

            drive_link, drive_file_id = upload
            receipt.drive_link = drive_link
            logger.info(f"Uploaded to Google Drive: {drive_link}")

            # Step 3: Log to Google Sheets
            appended_range = self.sheets_service.append_receipt(receipt)

            if not appended_range:
                logger.error("Failed to log receipt to Google Sheets")
                return None

            logger.info("Receipt logged to Google Sheets successfully")

            # Record the action so it can be undone (/undo).
            self._record_action(user_id, receipt, drive_file_id, appended_range)

            # Processing complete
            logger.info(f"Receipt processing completed successfully for: {receipt.merchant}")
            return receipt
            
        except Exception as e:
            logger.error(f"Error in receipt processing pipeline: {e}", exc_info=True)
            return None
    
    def _record_action(self, user_id, receipt, drive_file_id, appended_range):
        """Log the receipt action for undo (best-effort; never breaks processing)."""
        if user_id is None:
            return
        try:
            undo = {
                "drive_file_id": drive_file_id,
                "sheet": {
                    "spreadsheet_id": Config.GOOGLE_SHEET_ID,
                    "range": appended_range,
                },
            }
            description = f"Receipt: {receipt.merchant} (${receipt.total:.2f})"
            scenario_store.record_action(user_id, "receipt", description, undo)
        except Exception as e:
            logger.warning(f"Could not record receipt action for undo: {e}")

    def get_receipt_summary(self, receipt: Receipt) -> str:
        """
        Generate a user-friendly summary of the processed receipt
        
        Args:
            receipt: Processed Receipt object
            
        Returns:
            Formatted summary string
        """
        items_preview = ", ".join(receipt.items[:5]) if receipt.items else "N/A"
        if len(receipt.items) > 5:
            items_preview += f" ... (+{len(receipt.items) - 5} more)"
        
        summary = f"""✅ Receipt processed successfully!

📅 Date: {receipt.date}
🏪 Merchant: {receipt.merchant}
💰 Total: ${receipt.total:.2f}
📊 Tax: ${receipt.tax:.2f}
💳 Payment: {receipt.payment_method}
📂 Category: {receipt.category}
🛒 Items: {items_preview}

🔗 View receipt: {receipt.drive_link}
"""
        return summary

