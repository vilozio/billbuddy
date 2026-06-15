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
  "order": ["<output name>", ...]            // final order, using renamed (output) names
}}

Rules:
- "keep" entries MUST be exact names from the column list above.
- "rename" keys MUST be exact source names; values are the desired output names.
- "order" entries use the OUTPUT names (i.e. after renaming).
- If the user does not mention dropping columns, keep all of them.
- If the user does not mention ordering, you may omit "order".
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
        # Output names after renaming (used to validate "order").
        output_names = {rename.get(c, c) for c in keep}
        order = [o for o in (schema.get("order") or []) if o in output_names]
        result = {"keep": keep, "rename": rename}
        if order:
            result["order"] = order
        return result


def describe_transform(schema: dict) -> str:
    """Human-readable rendering of a transform schema for confirmation in chat."""
    keep = schema.get("keep", [])
    rename = schema.get("rename") or {}
    order = schema.get("order")
    lines = ["Proposed mapping:"]
    for src in keep:
        dst = rename.get(src)
        lines.append(f"  • {src} → {dst} (renamed)" if dst else f"  • {src} (keep)")
    lines.append("  • [all other columns dropped]")
    if order:
        lines.append(f"Order: {', '.join(order)}")
    return "\n".join(lines)
