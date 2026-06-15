"""Statement (CSV) processing orchestrator.

Given a downloaded CSV and a matching :class:`Scenario`, transform the file in
deterministic code and dispatch the result to the scenario's destinations
(append to a Google Sheet tab and/or upload the transformed CSV to Drive).

Google services are initialized lazily so the statement path never forces Google
auth unless a CSV is actually processed.
"""

import os
from pathlib import Path
from typing import Optional

from app.config import Config
from app.models.scenario import Scenario
from app.services import csv_transformer
from app.utils.logger import setup_logger

logger = setup_logger(__name__, Config.LOG_LEVEL)

TEMP_DIR = Path("temp_statements")
TEMP_DIR.mkdir(exist_ok=True)


class StatementProcessor:
    """Coordinates transform -> destination dispatch for CSV statements."""

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

    def process(self, file_path: str, filename: str, scenario: Scenario) -> Optional[str]:
        """Run the scenario against ``file_path`` and return a user-facing summary."""
        try:
            out_path = str(TEMP_DIR / f"transformed_{filename}")
            header, n_rows = csv_transformer.apply_transform(
                file_path, out_path, scenario.transform, scenario.has_header
            )

            results = [
                f"📄 Processed *{scenario.name}*",
                f"Rows: {n_rows} · Columns: {len(header)}",
            ]

            try:
                if scenario.dest_sheet:
                    with open(out_path, newline="", encoding="utf-8") as f:
                        import csv as _csv

                        reader = _csv.reader(f)
                        next(reader, None)  # skip header (handled by append_rows)
                        rows = list(reader)
                    spreadsheet_id = scenario.sheet_spreadsheet_id or Config.STATEMENTS_SHEET_ID
                    appended = self._sheets_service().append_rows(
                        spreadsheet_id, scenario.sheet_tab, header, rows
                    )
                    results.append(f"✅ Appended {appended} rows to tab '{scenario.sheet_tab}'")

                if scenario.dest_drive:
                    link = self._drive_service().upload_file(
                        out_path, scenario.drive_folder_id, filename=filename
                    )
                    if link:
                        results.append(f"✅ Uploaded to Drive: {link}")
                    else:
                        results.append("⚠️ Drive upload failed")
            finally:
                # Always clean up the transformed temp file.
                try:
                    os.remove(out_path)
                except OSError:
                    pass

            return "\n".join(results)

        except Exception as e:
            logger.error(f"Error processing statement: {e}", exc_info=True)
            return None
