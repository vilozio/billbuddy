"""SQLite database access for statement scenarios and runtime settings.

The database is created lazily on first connection. All schema is created with
``CREATE TABLE IF NOT EXISTS`` so :func:`init_db` is safe to call repeatedly.
"""

import sqlite3
from pathlib import Path

from app.config import Config
from app.utils.logger import setup_logger

logger = setup_logger(__name__, Config.LOG_LEVEL)


SCHEMA = """
CREATE TABLE IF NOT EXISTS scenarios (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    name                 TEXT NOT NULL,
    filename_pattern     TEXT NOT NULL,   -- {date}/{any} template as typed by the user
    pattern_regex        TEXT NOT NULL,   -- compiled regex (matched with re.fullmatch)
    has_header           INTEGER NOT NULL DEFAULT 1,
    transform_json       TEXT NOT NULL,   -- confirmed transform schema (JSON)
    dest_sheet           INTEGER NOT NULL DEFAULT 0,
    sheet_spreadsheet_id TEXT,
    sheet_tab            TEXT,
    dest_drive           INTEGER NOT NULL DEFAULT 0,
    drive_folder_id      TEXT,
    created_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS known_sheets (
    spreadsheet_id TEXT PRIMARY KEY,  -- a spreadsheet the user has used before
    label          TEXT,              -- friendly name (spreadsheet title)
    last_used      TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    """Open a connection to the SQLite database, creating the parent dir if needed."""
    db_path = Path(Config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they do not already exist."""
    with get_connection() as conn:
        conn.executescript(SCHEMA)
    logger.info(f"Database initialized at {Config.DB_PATH}")
