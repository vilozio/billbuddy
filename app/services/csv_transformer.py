"""Deterministic CSV transformation engine (stdlib ``csv`` only).

A transform schema is::

    {
        "keep":      ["Completed Date", "Amount"],   # source columns to retain
        "rename":    {"Completed Date": "Date"},      # source -> output name
        "constants": {"Currency": "EUR"},             # new columns with a fixed value
        "order":     ["Date", "Amount", "Currency"],  # final order, by output name
        "sort":      {"by": "Date", "descending": false}  # reorder rows by a column
    }

All keys are optional. ``keep`` defaults to all columns; ``rename`` defaults to
identity; ``constants`` adds output columns that don't exist in the source;
``order`` defaults to kept columns (after renaming) followed by constants;
``sort`` reorders the output rows by one output column (numeric when possible).
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


def _resolve_specs(source_header, transform) -> List[dict]:
    """Compute ordered output column specs from the transform schema.

    Each spec is ``{"name": <output name>, "src": <source name>}`` for a column
    copied from the source, or ``{"name": <output name>, "const": <value>}`` for
    an added constant column.
    """
    keep = transform.get("keep") or list(source_header)
    rename = transform.get("rename") or {}
    constants = transform.get("constants") or {}
    order = transform.get("order")

    # Kept source columns that actually exist, preserving `keep` order.
    specs = [
        {"name": rename.get(src, src), "src": src}
        for src in keep
        if src in source_header
    ]
    # Constant columns appended after the source columns by default.
    specs += [{"name": name, "const": str(value)} for name, value in constants.items()]

    if order:
        by_name = {spec["name"]: spec for spec in specs}
        ordered = [by_name[name] for name in order if name in by_name]
        ordered += [s for s in specs if s["name"] not in set(order)]
        specs = ordered
    return specs


def _sort_rows(rows: List[List[str]], idx: int, descending: bool) -> None:
    """Sort ``rows`` in place by column ``idx`` (numeric when all values parse)."""

    def cell(row):
        return row[idx] if idx < len(row) else ""

    def is_numeric(value):
        if value == "":
            return True
        try:
            float(value)
            return True
        except ValueError:
            return False

    if all(is_numeric(cell(r)) for r in rows):
        rows.sort(
            key=lambda r: float(cell(r)) if cell(r) != "" else float("-inf"),
            reverse=descending,
        )
    else:
        rows.sort(key=cell, reverse=descending)


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
    specs = _resolve_specs(source_header, transform)
    output_header = [spec["name"] for spec in specs]

    # Build the output rows (applying constants and source selection).
    out_rows = []
    for row in data_rows:
        out_row = []
        for spec in specs:
            if "const" in spec:
                out_row.append(spec["const"])
            else:
                i = col_index[spec["src"]]
                out_row.append(row[i] if i < len(row) else "")
        out_rows.append(out_row)

    # Optionally reorder rows by a column.
    sort = transform.get("sort")
    if sort and sort.get("by") in output_header:
        _sort_rows(
            out_rows, output_header.index(sort["by"]), bool(sort.get("descending", False))
        )

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(output_header)
        writer.writerows(out_rows)

    logger.info(
        f"Transformed {in_path}: {len(out_rows)} rows, "
        f"{len(output_header)} columns -> {out_path}"
    )
    return output_header, len(out_rows)
