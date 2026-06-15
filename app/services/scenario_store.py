"""CRUD layer for statement scenarios and runtime settings (SQLite-backed)."""

import re
from typing import List, Optional

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


def find_matching(filename: str) -> Optional[Scenario]:
    """Return the first scenario whose pattern fully matches ``filename``."""
    for scenario in list_scenarios():
        try:
            if re.fullmatch(scenario.pattern_regex, filename):
                return scenario
        except re.error as e:
            logger.warning(f"Bad regex on scenario #{scenario.id}: {e}")
    return None


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


# --- Convenience helpers for the receipt-processing toggle ---

RECEIPTS_ENABLED_KEY = "receipts_enabled"


def receipts_enabled() -> bool:
    """Whether receipt (photo/PDF) processing is currently enabled (default: True)."""
    return get_setting(RECEIPTS_ENABLED_KEY, "1") == "1"


def set_receipts_enabled(enabled: bool) -> None:
    set_setting(RECEIPTS_ENABLED_KEY, "1" if enabled else "0")
