"""Statement scenario data model.

A *scenario* describes how a recurring CSV file (recognized by its filename) is
transformed and where the result is written.
"""

import json
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Scenario:
    """A saved CSV-processing scenario, mirroring a row in the ``scenarios`` table."""

    name: str
    filename_pattern: str  # {date}/{any} template as typed by the user
    pattern_regex: str  # compiled regex, matched with re.fullmatch
    transform_json: str  # confirmed transform schema (JSON string)
    has_header: bool = True
    dest_sheet: bool = False
    sheet_spreadsheet_id: Optional[str] = None
    sheet_tab: Optional[str] = None
    dest_drive: bool = False
    drive_folder_id: Optional[str] = None
    created_at: str = ""
    id: Optional[int] = None

    @property
    def transform(self) -> dict:
        """Parsed transform schema: ``{"keep": [...], "rename": {...}, "order": [...]}``."""
        return json.loads(self.transform_json)

    @classmethod
    def from_row(cls, row) -> "Scenario":
        """Build a Scenario from a sqlite3.Row (or any mapping with the column keys)."""
        return cls(
            id=row["id"],
            name=row["name"],
            filename_pattern=row["filename_pattern"],
            pattern_regex=row["pattern_regex"],
            has_header=bool(row["has_header"]),
            transform_json=row["transform_json"],
            dest_sheet=bool(row["dest_sheet"]),
            sheet_spreadsheet_id=row["sheet_spreadsheet_id"],
            sheet_tab=row["sheet_tab"],
            dest_drive=bool(row["dest_drive"]),
            drive_folder_id=row["drive_folder_id"],
            created_at=row["created_at"],
        )

    def to_row(self) -> dict:
        """Return a dict of column -> value for an INSERT (excludes ``id``)."""
        return {
            "name": self.name,
            "filename_pattern": self.filename_pattern,
            "pattern_regex": self.pattern_regex,
            "has_header": 1 if self.has_header else 0,
            "transform_json": self.transform_json,
            "dest_sheet": 1 if self.dest_sheet else 0,
            "sheet_spreadsheet_id": self.sheet_spreadsheet_id,
            "sheet_tab": self.sheet_tab,
            "dest_drive": 1 if self.dest_drive else 0,
            "drive_folder_id": self.drive_folder_id,
            "created_at": self.created_at,
        }

    def destination_summary(self) -> str:
        """Human-readable description of where this scenario writes its output."""
        parts: List[str] = []
        if self.dest_sheet:
            parts.append(f"Sheet tab '{self.sheet_tab}'")
        if self.dest_drive:
            parts.append("Drive folder")
        return " + ".join(parts) if parts else "(no destination)"
