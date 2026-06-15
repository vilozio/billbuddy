"""Deterministic CSV transformation engine (stdlib ``csv`` only).

A transform schema is::

    {
        "keep":   ["Completed Date", "Amount"],   # source columns to retain
        "rename": {"Completed Date": "Date"},      # source -> output name
        "order":  ["Date", "Amount"]               # final order, by output name
    }

All keys are optional. ``keep`` defaults to all columns; ``rename`` defaults to
identity; ``order`` defaults to ``keep`` order (after renaming).
"""

import csv
from typing import List, Tuple

from app.config import Config
from app.utils.logger import setup_logger

logger = setup_logger(__name__, Config.LOG_LEVEL)


def _generated_names(n: int) -> List[str]:
    """Synthetic column names for header-less CSVs: 'Column 1', 'Column 2', ..."""
    return [f"Column {i + 1}" for i in range(n)]


def read_headers(path: str, has_header: bool = True) -> List[str]:
    """Return the column names of a CSV.

    With ``has_header`` the first row is returned verbatim; otherwise synthetic
    ``Column N`` names sized to the first data row are returned.
    """
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            first = next(reader)
        except StopIteration:
            return []
    return first if has_header else _generated_names(len(first))


def _resolve_columns(source_header, transform) -> List[Tuple[str, str]]:
    """Compute ordered (output_name, source_name) pairs from the transform schema."""
    keep = transform.get("keep") or list(source_header)
    rename = transform.get("rename") or {}
    order = transform.get("order")

    # Keep only requested columns that actually exist, preserving `keep` order.
    pairs = [(rename.get(src, src), src) for src in keep if src in source_header]

    if order:
        index = {out: (out, src) for out, src in pairs}
        ordered = [index[name] for name in order if name in index]
        # Append any kept columns the user didn't mention in `order`.
        ordered += [p for p in pairs if p[0] not in set(order)]
        pairs = ordered
    return pairs


def apply_transform(
    in_path: str, out_path: str, transform: dict, has_header: bool = True
) -> Tuple[List[str], int]:
    """Transform ``in_path`` into ``out_path`` per the schema.

    Returns ``(output_header, row_count)``.
    """
    with open(in_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        logger.warning(f"CSV {in_path} is empty")
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            pass
        return [], 0

    if has_header:
        source_header = rows[0]
        data_rows = rows[1:]
    else:
        source_header = _generated_names(len(rows[0]))
        data_rows = rows

    col_index = {name: i for i, name in enumerate(source_header)}
    pairs = _resolve_columns(source_header, transform)
    output_header = [out for out, _ in pairs]
    indices = [col_index[src] for _, src in pairs]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(output_header)
        for row in data_rows:
            writer.writerow([row[i] if i < len(row) else "" for i in indices])

    logger.info(
        f"Transformed {in_path}: {len(data_rows)} rows, "
        f"{len(output_header)} columns -> {out_path}"
    )
    return output_header, len(data_rows)
