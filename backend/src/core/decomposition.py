"""
Query Decomposition & Multi-Query Intent Analysis (Stateless Pure Functional).

Provides:
  - `is_compound_question`: Fast heuristic detector for compound multi-part questions.
  - `decompose_question`: LLM-assisted multi-query prompt decomposition into atomic sub-questions.
  - `parse_query_tasks`: Universal parser converting generator outputs (raw query, JSON object,
    JSON list, or out-of-domain rejection) into standardized query task payloads.

Zero OOP required; pure functional interfaces replacing scattered splitting logic in F02 and F06.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure backend root is discoverable for internal imports
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from src.core.llm import call_llm_json
except ImportError:
    try:
        from core.llm import call_llm_json
    except ImportError:
        call_llm_json = None


# Patterns indicating multiple distinct questions or goals
COMPOUND_CONJUNCTION_PATTERNS = [
    r"\b(?:and\s+also|and\s+then|as\s+well\s+as|along\s+with|additionally|plus\s+show|plus\s+list)\b",
    r"\b(?:and\s+show\s+me|and\s+give\s+me|and\s+tell\s+me|and\s+display|and\s+find)\b",
    r"\b(?:also\s+show|also\s+list|also\s+give|also\s+tell|also\s+find|also\s+display)\b",
    r"\b(?:first|1\.)\b.*\b(?:second|then|2\.)\b",
]

# Simple single-intent patterns that contain 'and' but are NOT compound questions
# (e.g. "rock and roll", "between 2020 and 2024", "first and last name")
NON_COMPOUND_PHRASES = [
    r"\b(?:rock\s+and\s+roll|r&b|r\s+and\s+b)\b",
    r"\b(?:between\s+\S+\s+and\s+\S+)\b",
    r"\b(?:first\s+and\s+last\s+name|firstname\s+and\s+lastname)\b",
    r"\b(?:city\s+and\s+country|state\s+and\s+country)\b",
    r"\b(?:min\s+and\s+max|minimum\s+and\s+maximum)\b",
]


def is_compound_question(question: str) -> bool:
    """
    Fast regex heuristic check to identify compound multi-intent questions
    needing query decomposition.

    Returns True if the prompt contains multiple distinct requests or actions.
    """
    if not question or not question.strip():
        return False

    q_lower = question.strip().lower()

    # Check for multiple question marks separated by words: e.g. "Who is top customer? What is total revenue?"
    if len(re.findall(r"\?\s+[A-Za-z]", question)) > 0:
        return True

    # Semicolons separating clauses: e.g. "Show top 5 tracks; also show top artist"
    if ";" in question and len(question.split(";")) > 1:
        parts = [p.strip() for p in question.split(";") if p.strip()]
        if len(parts) >= 2 and any(len(p) > 10 for p in parts):
            return True

    # Check for compound conjunction patterns
    for pattern in COMPOUND_CONJUNCTION_PATTERNS:
        if re.search(pattern, q_lower):
            return True

    # Check for simple ' and ' followed by verb command
    # e.g., "List all genres and show total invoices"
    command_verbs = r"(?:show|list|display|find|get|give|calculate|count|tell)"
    if re.search(rf"\band\s+{command_verbs}\b", q_lower):
        # Exclude known false positives
        for non_comp in NON_COMPOUND_PHRASES:
            if re.search(non_comp, q_lower):
                return False
        return True

    return False


def decompose_question(
    question: str,
    schema_context: str = "",
    model_override: Optional[str] = None,
) -> List[str]:
    """
    Splits compound user prompts into a list of discrete, atomic sub-questions.
    If the question is atomic/single, returns a single-element list `[question]`.

    Args:
        question: Natural language question.
        schema_context: Database schema context for semantic disambiguation.
        model_override: Optional model override.

    Returns:
        List[str]: Discrete sub-questions in execution order.
    """
    q_clean = question.strip()
    if not q_clean:
        return []

    # If heuristic says not compound, return directly
    if not is_compound_question(q_clean):
        return [q_clean]

    # Use LLM in JSON mode for clean decomposition
    if call_llm_json is not None:
        prompt = f"""You are a Database Query Decomposer.
Analyze this user question and determine if it asks for multiple distinct pieces of data or queries.

User Question: "{q_clean}"
"""
        if schema_context:
            prompt += f"\nSchema Context:\n{schema_context[:500]}\n"

        prompt += """
Instructions:
- If the question contains 2 or more distinct sub-tasks (e.g. "List top 5 tracks and show total album revenue"), split it into separate, standalone sub-questions.
- If it is already a single cohesive task, return only 1 item in the list.
- Return ONLY valid JSON:
{
  "sub_questions": [
    "Sub question 1",
    "Sub question 2"
  ]
}
"""
        system_prompt = "You are a precise question decomposer. Output JSON only."
        try:
            parsed = call_llm_json(
                prompt=prompt,
                system_prompt=system_prompt,
                model_override=model_override,
            )
            if isinstance(parsed, dict) and "sub_questions" in parsed:
                sub_qs = parsed["sub_questions"]
                if isinstance(sub_qs, list) and len(sub_qs) > 0:
                    cleaned_subs = [str(sq).strip() for sq in sub_qs if str(sq).strip()]
                    if cleaned_subs:
                        return cleaned_subs
        except Exception:
            pass

    # Heuristic fallback: split by semicolon or ' and ' + command verb
    if ";" in q_clean:
        parts = [p.strip() for p in q_clean.split(";") if p.strip()]
        if len(parts) >= 2:
            return parts

    split_match = re.split(
        r"\s+(?:and\s+also|and\s+then|as\s+well\s+as|along\s+with|additionally|plus\s+show|and\s+show)\s+",
        q_clean,
        flags=re.IGNORECASE,
    )
    if len(split_match) >= 2:
        return [p.strip() for p in split_match if p.strip()]

    return [q_clean]


def parse_query_tasks(
    raw_output: str,
    default_query_key: str = "sql",
) -> Union[List[Dict[str, str]], Dict[str, Any]]:
    """
    Parses LLM generator output into structured query tasks:
      - `[{"title": "...", "sql": "..."}]` for single or compound queries
      - `{"is_relevant": False, "reason": "...", ...}` for out-of-domain rejections

    Handles:
      - Raw query text (SQL, MQL, Python)
      - JSON object with "is_relevant": False
      - JSON object with "sql" / "mql" / "code"
      - JSON array of objects `[{"title": "...", "sql": "..."}, ...]`
      - Markdown fences (```json, ```sql, etc.)
    """
    cleaned = raw_output.strip() if raw_output else ""
    if not cleaned:
        return [{"title": "Query Objective", default_query_key: ""}]

    # Strip markdown code blocks
    if "```" in cleaned:
        parts = cleaned.split("```")
        cleaned = parts[1] if len(parts) > 1 else parts[0]
        cleaned = re.sub(r"^(?:json|sql|python|mql)\s*\n?", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip()

    # 1. Check if output is a JSON object (out-of-domain rejection OR structured single query)
    if cleaned.startswith("{") and cleaned.endswith("}"):
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                # Out-of-Domain rejection
                if parsed.get("is_relevant") is False:
                    return parsed

                # Single structured query object
                for candidate_key in ["sql", "mql", "code", "query", "formula"]:
                    if candidate_key in parsed:
                        q_str = str(parsed[candidate_key]).strip()
                        title_str = str(parsed.get("title") or "Query Objective").strip()
                        return [{"title": title_str, default_query_key: q_str}]
        except Exception:
            pass

    # 2. Check if output is a JSON array for compound multi-part questions
    if cleaned.startswith("[") and cleaned.endswith("]"):
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
                tasks = []
                for i, item in enumerate(parsed):
                    for candidate_key in ["sql", "mql", "code", "query", "formula"]:
                        if candidate_key in item:
                            q_str = str(item[candidate_key]).strip()
                            t_str = str(item.get("title") or f"Query {i + 1}").strip()
                            tasks.append({"title": t_str, default_query_key: q_str})
                            break
                if tasks:
                    return tasks
        except Exception:
            pass

    # 3. Fallback: single raw query string
    return [{"title": "Query Objective", default_query_key: cleaned}]

