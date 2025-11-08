"""Google Drive service for storing receipts"""
import os
from typing import Optional
from pathlib import Path
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import Config
from app.utils.logger import setup_logger

logger = setup_logger(__name__, Config.LOG_LEVEL)


class GoogleDriveService:
    """Service for uploading and managing receipts in Google Drive"""
    
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    
    def __init__(self):
        """Initialize Google Drive service"""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                Config.GOOGLE_CREDENTIALS_PATH,
                scopes=self.SCOPES
            )
            self.service = build('drive', 'v3', credentials=credentials)
            logger.info("Google Drive service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
            raise
    
    def _find_or_create_folder(self, folder_name: str, parent_id: str) -> Optional[str]:
        """
        Find or create a folder in Google Drive
        
        Args:
            folder_name: Name of the folder
            parent_id: Parent folder ID
            
        Returns:
            Folder ID or None if operation fails
        """
        try:
            # Search for existing folder
            query = f"name='{folder_name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                logger.debug(f"Found existing folder: {folder_name}")
                return folders[0]['id']
            
            # Create new folder if not found
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            
            logger.info(f"Created new folder: {folder_name}")
            return folder.get('id')
            
        except HttpError as e:
            logger.error(f"Error finding/creating folder {folder_name}: {e}")
            return None
    
    def _get_folder_structure(self, date_str: str) -> Optional[str]:
        """
        Get or create the year/month folder structure
        
        Args:
            date_str: Date string in YYYY-MM-DD format
            
        Returns:
            Folder ID for the month folder, or None if operation fails
        """
        try:
            # Parse date to get year and month
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            year = str(date_obj.year)
            month = date_obj.strftime("%m")  # 01-12
            
            # Find or create year folder
            year_folder_id = self._find_or_create_folder(year, Config.GOOGLE_DRIVE_FOLDER_ID)
            if not year_folder_id:
                return None
            
            # Find or create month folder
            month_folder_id = self._find_or_create_folder(month, year_folder_id)
            return month_folder_id
            
        except Exception as e:
            logger.error(f"Error creating folder structure: {e}")
            return None
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def upload_receipt(
        self,
        file_path: str,
        receipt_date: str,
        merchant_name: str,
        amount: float
    ) -> Optional[str]:
        """
        Upload receipt file to Google Drive with organized folder structure
        
        Args:
            file_path: Path to the receipt file
            receipt_date: Receipt date in YYYY-MM-DD format
            merchant_name: Merchant name for filename
            amount: Receipt amount for filename
            
        Returns:
            Shareable link to the uploaded file, or None if upload fails
        """
        try:
            logger.info(f"Uploading receipt to Google Drive: {file_path}")
            
            # Get the appropriate folder
            folder_id = self._get_folder_structure(receipt_date)
            if not folder_id:
                logger.error("Failed to get/create folder structure")
                return None
            
            # Create a clean filename
            file_extension = Path(file_path).suffix
            clean_merchant = "".join(c for c in merchant_name if c.isalnum() or c in (' ', '-', '_')).strip()
            filename = f"{receipt_date}_{clean_merchant}_{amount:.2f}{file_extension}"
            
            # Prepare file metadata
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            
            # Upload the file
            media = MediaFileUpload(
                file_path,
                resumable=True
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            file_id = file.get('id')
            
            # Make the file accessible via link
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            
            self.service.permissions().create(
                fileId=file_id,
                body=permission
            ).execute()
            
            web_link = file.get('webViewLink')
            logger.info(f"Receipt uploaded successfully: {web_link}")
            
            return web_link
            
        except HttpError as e:
            logger.error(f"HTTP error uploading receipt: {e}")
            return None
        except Exception as e:
            logger.error(f"Error uploading receipt: {e}", exc_info=True)
            return None
    
    def delete_file(self, file_id: str) -> bool:
        """
        Delete a file from Google Drive
        
        Args:
            file_id: ID of the file to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.service.files().delete(fileId=file_id).execute()
            logger.info(f"Deleted file: {file_id}")
            return True
        except HttpError as e:
            logger.error(f"Error deleting file {file_id}: {e}")
            return False

