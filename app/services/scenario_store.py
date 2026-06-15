"""CRUD layer for statement scenarios and runtime settings (SQLite-backed)."""

import json
import re
import sqlite3
from datetime import datetime
from typing import List, Optional, Tuple

from app.config import Config
from app.db import get_connection
from app.models.scenario import Scenario
from app.utils.logger import setup_logger

logger = setup_logger(__name__, Config.LOG_LEVEL)


def add_scenario(scenario: Scenario) -> int:
    """Insert a scenario and return its new id."""
    row = scenario.to_row()
    columns = ", ".join(row.keys())
    placeholders = ", ".join("?" for _ in row)
    with get_connection() as conn:
        cursor = conn.execute(
            f"INSERT INTO scenarios ({columns}) VALUES ({placeholders})",
            tuple(row.values()),
        )
        scenario.id = cursor.lastrowid
    logger.info(f"Saved scenario #{scenario.id}: {scenario.name}")
    return scenario.id


def list_scenarios() -> List[Scenario]:
    """Return all scenarios, newest first."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM scenarios ORDER BY id DESC").fetchall()
    return [Scenario.from_row(r) for r in rows]


def find_matches(filename: str) -> List[Scenario]:
    """Return all scenarios whose pattern fully matches ``filename`` (creation order)."""
    matches = []
    for scenario in list_scenarios():
        try:
            if re.fullmatch(scenario.pattern_regex, filename):
                matches.append(scenario)
        except re.error as e:
            logger.warning(f"Bad regex on scenario #{scenario.id}: {e}")
    # list_scenarios() is newest-first; present matches in creation order instead.
    matches.sort(key=lambda s: s.id or 0)
    return matches


def find_matching(filename: str) -> Optional[Scenario]:
    """Return the first scenario whose pattern fully matches ``filename``, or None."""
    matches = find_matches(filename)
    return matches[0] if matches else None


def delete_scenario(scenario_id: int) -> bool:
    """Delete a scenario by id. Returns True if a row was removed."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))
        deleted = cursor.rowcount > 0
    if deleted:
        logger.info(f"Deleted scenario #{scenario_id}")
    return deleted


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Return a setting value, or ``default`` if unset."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    """Insert or update a setting."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


# --- Known spreadsheets (destinations the user has used before) ---


def list_known_sheets() -> List[Tuple[str, str]]:
    """Return previously-used spreadsheets as (spreadsheet_id, label), recent first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT spreadsheet_id, label FROM known_sheets ORDER BY last_used DESC"
        ).fetchall()
    return [(r["spreadsheet_id"], r["label"]) for r in rows]


def add_known_sheet(spreadsheet_id: str, label: str) -> None:
    """Remember a spreadsheet destination (insert or refresh its label/last_used)."""
    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO known_sheets (spreadsheet_id, label, last_used) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(spreadsheet_id) DO UPDATE SET "
            "label = excluded.label, last_used = excluded.last_used",
            (spreadsheet_id, label, now),
        )


# --- Action log (for undo) ---


def record_action(user_id: int, kind: str, description: str, undo: dict) -> int:
    """Log a completed, reversible action and return its id."""
    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO actions (user_id, kind, description, undo_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, kind, description, json.dumps(undo), now),
        )
        return cursor.lastrowid


def last_undoable_action(user_id: int) -> Optional[sqlite3.Row]:
    """Return the user's most recent not-yet-undone action, or None."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM actions WHERE user_id = ? AND undone = 0 "
            "ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()


def mark_action_undone(action_id: int) -> None:
    """Mark an action as undone so a later /undo skips it."""
    with get_connection() as conn:
        conn.execute("UPDATE actions SET undone = 1 WHERE id = ?", (action_id,))


# --- Convenience helpers for the receipt-processing toggle ---

RECEIPTS_ENABLED_KEY = "receipts_enabled"


def receipts_enabled() -> bool:
    """Whether receipt (photo/PDF) processing is currently enabled (default: True)."""
    return get_setting(RECEIPTS_ENABLED_KEY, "1") == "1"


def set_receipts_enabled(enabled: bool) -> None:
    set_setting(RECEIPTS_ENABLED_KEY, "1" if enabled else "0")
