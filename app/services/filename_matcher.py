"""Filename pattern engine using human-friendly named placeholders.

Patterns are templates containing literal text and placeholder tokens:

    account-statement_{date}_{date}_en_{any}.csv

Supported placeholders:
    {date}  -> a date in YYYY-MM-DD form
    {any}   -> any run of characters except an underscore

:func:`suggest_pattern` builds such a template from a single example filename;
:func:`compile_pattern` turns a template into a regex matched with ``re.fullmatch``.
"""

import re

from app.config import Config
from app.utils.logger import setup_logger

logger = setup_logger(__name__, Config.LOG_LEVEL)

# Regex fragments each placeholder expands to when compiled.
PLACEHOLDERS = {
    "date": r"\d{4}-\d{2}-\d{2}",
    "any": r"[^_]+",
}

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TOKEN_SPLIT_RE = re.compile(r"(\{[^}]*\})")


def _looks_like_hash(token: str) -> bool:
    """Heuristic: a token that varies per file (hex id, alphanumeric hash)."""
    if not token:
        return False
    # Pure hex of reasonable length (e.g. "6d52ac", "a1b2c3d4").
    if re.fullmatch(r"[0-9a-fA-F]{6,}", token):
        return True
    # Alphanumeric, long-ish, and contains at least one digit (e.g. "f3k9q2").
    if len(token) >= 6 and token.isalnum() and any(c.isdigit() for c in token):
        return True
    return False


def suggest_pattern(filename: str) -> str:
    """Propose a {date}/{any} template from one example filename."""
    # Preserve the extension as a literal (".csv" etc.).
    if "." in filename:
        stem, ext = filename.rsplit(".", 1)
        ext = "." + ext
    else:
        stem, ext = filename, ""

    # Replace any date-like substrings first.
    stem = _DATE_RE.sub("{date}", stem)

    # Then replace hash-like tokens (split on underscore, the common separator).
    tokens = stem.split("_")
    rebuilt = [
        "{any}" if (tok != "{date}" and _looks_like_hash(tok)) else tok
        for tok in tokens
    ]
    return "_".join(rebuilt) + ext


def compile_pattern(template: str) -> str:
    """Compile a {date}/{any} template into a regex string for ``re.fullmatch``.

    Literal text is escaped; unknown ``{token}`` placeholders are treated as
    ``{any}`` (with a warning).
    """
    out = []
    for part in _TOKEN_SPLIT_RE.split(template):
        if part.startswith("{") and part.endswith("}"):
            name = part[1:-1].strip().lower()
            if name not in PLACEHOLDERS:
                logger.warning(
                    f"Unknown placeholder '{part}' in pattern; treating as {{any}}"
                )
                name = "any"
            out.append(PLACEHOLDERS[name])
        elif part:
            out.append(re.escape(part))
    return "".join(out)
