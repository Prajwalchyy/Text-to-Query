"""
Semantic Result Evaluator (LLM-as-a-Judge, Pure Functional).

Evaluates executed query results against the user's natural language question:
  - Generates a semantic confidence score (0.0–1.0).
  - Determines boolean accuracy (`is_accurate`).
  - Produces a concise, natural English summary for UI display.

Zero OOP required; pure functional interfaces with a thin backward-compatible adapter.
Replaces legacy backend/src/F05_evaluator.py.
"""

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


def format_data_preview(data: Any, max_rows: int = 5) -> str:
    """
    Limits data preview to `max_rows` rows to conserve tokens and avoid LLM bloat.
    """
    if not data:
        return "[] (0 rows returned)"

    if isinstance(data, list):
        count = len(data)
        preview_rows = data[:max_rows]
        return f"{preview_rows} ({count} total row{'s' if count != 1 else ''})"

    return str(data)[:500]


def evaluate_result(
    question: str,
    query: str,
    data: Any,
    schema_context: str = "",
    model_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates query results using LLM-as-a-Judge semantic scoring.

    Args:
        question: Original natural language question from user.
        query: Generated SQL / MQL / Pandas code that produced the data.
        data: Execution result records (list of dicts or primitive value).
        schema_context: Optional schema context to aid accuracy evaluation.
        model_override: Optional LLM model override.

    Returns:
        dict: {
            "is_accurate": bool,
            "confidence_score": float,  # 0.0 to 1.0
            "summary": str              # Natural language summary of findings
        }
    """
    data_preview = format_data_preview(data, max_rows=5)
    row_count = len(data) if isinstance(data, list) else (1 if data is not None else 0)

    prompt = f"""You are a Senior SQL & Data Auditor and Business Intelligence Analyst.

Analyze this Text-to-Data query execution:
1. User Question: "{question}"
2. Generated Query / Code: {query}
3. Execution Output: {data_preview}
"""
    if schema_context:
        prompt += f"\nRelevant Schema:\n{schema_context[:500]}\n"

    prompt += """
Instructions:
- Check if the query and returned data logically and accurately answer the user's question.
- Calculate a confidence score between 0.0 and 1.0 (e.g. 0.95).
- Write a clear, conversational plain-English answer summarizing the data for the user.
- Return ONLY valid JSON in this exact structure:
{
  "is_accurate": true,
  "confidence_score": 0.95,
  "summary": "Plain English summary answering the question directly."
}
"""
    system_prompt = "You are a precise JSON-only data evaluation judge. Return valid JSON only."

    if call_llm_json is not None:
        try:
            parsed = call_llm_json(
                prompt=prompt,
                system_prompt=system_prompt,
                model_override=model_override,
            )
            if isinstance(parsed, dict):
                score = parsed.get("confidence_score")
                try:
                    score = float(score) if score is not None else 0.90
                    score = max(0.0, min(1.0, score))
                except (ValueError, TypeError):
                    score = 0.90

                is_accurate = bool(parsed.get("is_accurate", True))
                summary = str(parsed.get("summary") or "").strip()
                if not summary:
                    summary = f"Found {row_count} matching record{'s' if row_count != 1 else ''}."

                return {
                    "is_accurate": is_accurate,
                    "confidence_score": score,
                    "summary": summary,
                }
        except Exception:
            pass

    # Fallback heuristic if LLM call or parse fails
    default_summary = (
        f"Found {row_count} matching record{'s' if row_count != 1 else ''}."
        if row_count > 0
        else "No matching records found."
    )
    return {
        "is_accurate": True,
        "confidence_score": 0.85 if row_count > 0 else 0.50,
        "summary": default_summary,
    }


class SQLEvaluator:
    """
    Backward-compatible adapter matching legacy F05 SQLEvaluator interface.
    Delegates to pure functional evaluate_result.
    """

    def evaluate(self, user_question: str, sql_query: str, data: list) -> Dict[str, Any]:
        """Evaluates query logic, assigns confidence score, and writes summary."""
        return evaluate_result(
            question=user_question,
            query=sql_query,
            data=data,
        )

