"""Map a free-text instruction to a CSV transform schema using OpenAI.

The model only proposes the mapping; the user confirms it and the transform
itself always runs in deterministic code (see ``csv_transformer``).
"""

import json
from typing import List

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import Config
from app.utils.logger import setup_logger

logger = setup_logger(__name__, Config.LOG_LEVEL)


class TransformAIService:
    """Turns natural-language column instructions into a transform schema."""

    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL
        logger.info(f"Transform AI service initialized with model: {self.model}")

    def _build_prompt(self, columns: List[str], instruction: str) -> str:
        return f"""You map a user's natural-language instruction about CSV columns into a JSON transform schema.

The CSV has exactly these columns (use these EXACT names as source columns):
{json.dumps(columns)}

User instruction:
\"\"\"{instruction}\"\"\"

Return ONLY a JSON object with this shape:
{{
  "keep": ["<source column>", ...],         // columns to keep; omit/empty means keep all
  "rename": {{"<source column>": "<new name>"}},  // optional renames
  "constants": {{"<new column>": "<fixed value>"}}, // optional added columns with a constant value
  "order": ["<output name>", ...],           // final order, using output names (after renaming)
  "sort": {{"by": "<output name>", "descending": false}}  // optional: reorder rows by a column
}}

Rules:
- "keep" entries MUST be exact names from the column list above.
- "rename" keys MUST be exact source names; values are the desired output names.
- "constants" adds NEW columns (names not in the source) where every row gets the same value.
- "order" entries use the OUTPUT names — i.e. renamed source columns and constant column names.
- "sort.by" MUST be an output name (a kept/renamed column or a constant). Use "descending": true for high-to-low / newest-first.
- If the user does not mention dropping columns, keep all of them.
- Omit "constants", "order", or "sort" if the user does not ask for them.
- Return ONLY the JSON object, no commentary."""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def propose_transform(self, columns: List[str], instruction: str) -> dict:
        """Return a transform schema dict for the given columns and instruction."""
        logger.info(f"Proposing transform for instruction: {instruction[:80]}")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": self._build_prompt(columns, instruction)}],
            max_tokens=800,
            temperature=0.1,
        )
        content = response.choices[0].message.content
        logger.debug(f"Transform AI response: {content}")

        # The model may wrap JSON in markdown code blocks (same as openai_service).
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        schema = json.loads(content)
        return self._sanitize(schema, columns)

    @staticmethod
    def _sanitize(schema: dict, columns: List[str]) -> dict:
        """Drop hallucinated columns so only real source names survive."""
        valid = set(columns)
        keep = [c for c in schema.get("keep", []) if c in valid] or list(columns)
        rename = {
            src: dst for src, dst in (schema.get("rename") or {}).items() if src in valid
        }
        # Constant columns are new output columns; coerce their values to strings.
        constants = {
            str(name): str(value)
            for name, value in (schema.get("constants") or {}).items()
        }
        # All output names: renamed source columns plus constant column names.
        output_names = {rename.get(c, c) for c in keep} | set(constants)
        order = [o for o in (schema.get("order") or []) if o in output_names]

        result = {"keep": keep, "rename": rename}
        if constants:
            result["constants"] = constants
        if order:
            result["order"] = order

        sort = schema.get("sort")
        if isinstance(sort, dict) and sort.get("by") in output_names:
            result["sort"] = {
                "by": sort["by"],
                "descending": bool(sort.get("descending", False)),
            }
        return result


def describe_transform(schema: dict) -> str:
    """Human-readable rendering of a transform schema for confirmation in chat."""
    keep = schema.get("keep", [])
    rename = schema.get("rename") or {}
    constants = schema.get("constants") or {}
    order = schema.get("order")
    sort = schema.get("sort")
    lines = ["Proposed mapping:"]
    for src in keep:
        dst = rename.get(src)
        lines.append(f"  • {src} → {dst} (renamed)" if dst else f"  • {src} (keep)")
    for name, value in constants.items():
        lines.append(f"  • {name} = \"{value}\" (constant)")
    lines.append("  • [all other columns dropped]")
    if order:
        lines.append(f"Order: {', '.join(order)}")
    if sort:
        direction = "descending" if sort.get("descending") else "ascending"
        lines.append(f"Sort rows by: {sort['by']} ({direction})")
    return "\n".join(lines)
