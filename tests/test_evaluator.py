"""
Unit tests for Semantic Evaluator (backend/src/core/evaluator.py).
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.core.evaluator import (
    SQLEvaluator,
    evaluate_result,
    format_data_preview,
)


def test_format_data_preview_empty():
    """Verify empty data preview string."""
    assert format_data_preview([]) == "[] (0 rows returned)"
    assert format_data_preview(None) == "[] (0 rows returned)"


def test_format_data_preview_truncation():
    """Verify data preview limits to 5 rows and mentions total row count."""
    rows = [{"id": i} for i in range(20)]
    preview = format_data_preview(rows, max_rows=5)
    assert "20 total rows" in preview
    assert "{'id': 4}" in preview
    assert "{'id': 5}" not in preview


def test_evaluate_result_with_mock_llm():
    """Verify evaluation parsing when LLM returns high-confidence answer."""
    mock_payload = {
        "is_accurate": True,
        "confidence_score": 0.98,
        "summary": "Helena Holý is the top spender with $49.62.",
    }

    with patch("src.core.evaluator.call_llm_json", return_value=mock_payload):
        res = evaluate_result(
            question="Who is the top customer?",
            query="SELECT FirstName, LastName, SUM(Total) FROM Customer ...",
            data=[{"FirstName": "Helena", "LastName": "Holý", "SUM(Total)": 49.62}],
        )

        assert res["is_accurate"] is True
        assert res["confidence_score"] == 0.98
        assert "Helena" in res["summary"]


def test_evaluate_result_clamping_and_fallback():
    """Verify score clamping and fallback handling when LLM returns invalid data or fails."""
    # Score > 1.0 clamped to 1.0
    with patch("src.core.evaluator.call_llm_json", return_value={"confidence_score": 1.5, "summary": "Great"}):
        res = evaluate_result("Q", "SQL", [{"a": 1}])
        assert res["confidence_score"] == 1.0

    # Score < 0.0 clamped to 0.0
    with patch("src.core.evaluator.call_llm_json", return_value={"confidence_score": -0.2, "summary": "Bad"}):
        res = evaluate_result("Q", "SQL", [{"a": 1}])
        assert res["confidence_score"] == 0.0

    # Exception fallback with rows
    with patch("src.core.evaluator.call_llm_json", side_effect=RuntimeError("API error")):
        res = evaluate_result("Q", "SQL", [{"a": 1}, {"a": 2}])
        assert res["is_accurate"] is True
        assert res["confidence_score"] == 0.85
        assert "Found 2 matching records." in res["summary"]

    # Exception fallback with 0 rows
    with patch("src.core.evaluator.call_llm_json", side_effect=RuntimeError("API error")):
        res_empty = evaluate_result("Q", "SQL", [])
        assert res_empty["confidence_score"] == 0.50
        assert "No matching records found." in res_empty["summary"]


def test_sql_evaluator_legacy_adapter():
    """Verify backward-compatible SQLEvaluator adapter class."""
    evaluator = SQLEvaluator()
    mock_payload = {
        "is_accurate": True,
        "confidence_score": 0.90,
        "summary": "Found 1 record.",
    }

    with patch("src.core.evaluator.call_llm_json", return_value=mock_payload):
        res = evaluator.evaluate(
            user_question="Top artist?",
            sql_query="SELECT Name FROM Artist LIMIT 1;",
            data=[{"Name": "AC/DC"}],
        )
        assert res["is_accurate"] is True
        assert res["confidence_score"] == 0.90
        assert "Found 1 record." in res["summary"]

