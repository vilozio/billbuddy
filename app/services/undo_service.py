"""Reverses a previously recorded bot action (Drive upload + Sheet rows).

Used by the ``/undo`` command. Google services are initialized lazily.
"""

from typing import List

from app.config import Config
from app.utils.logger import setup_logger

logger = setup_logger(__name__, Config.LOG_LEVEL)


class UndoService:
    """Executes the reversal described by an action's ``undo`` payload."""

    def __init__(self):
        self._sheets = None
        self._drive = None

    def _sheets_service(self):
        if self._sheets is None:
            from app.services.google_sheets import GenericSheetsService

            self._sheets = GenericSheetsService()
        return self._sheets

    def _drive_service(self):
        if self._drive is None:
            from app.services.google_drive import GoogleDriveService

            self._drive = GoogleDriveService()
        return self._drive

    def execute(self, undo: dict) -> List[str]:
        """Reverse an action. Returns human-readable result lines."""
        results: List[str] = []

        sheet = undo.get("sheet")
        if sheet and sheet.get("range"):
            ok = self._sheets_service().delete_rows_in_range(
                sheet["spreadsheet_id"], sheet["range"]
            )
            results.append(
                "🗑️ Removed appended Sheet rows"
                if ok
                else "⚠️ Could not remove Sheet rows"
            )

        file_id = undo.get("drive_file_id")
        if file_id:
            ok = self._drive_service().delete_file(file_id)
            results.append(
                "🗑️ Deleted the Drive file" if ok else "⚠️ Could not delete the Drive file"
            )

        return results or ["Nothing to reverse for this action."]
