"""
Unit tests for Query Decomposition & Multi-Query Intent Analysis (backend/src/core/decomposition.py).
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.core.decomposition import (
    decompose_question,
    is_compound_question,
    parse_query_tasks,
)


def test_is_compound_question_negative():
    """Verify single-intent questions are identified as non-compound."""
    assert is_compound_question("Who is the top artist?") is False
    assert is_compound_question("Find customers born between 1980 and 1990") is False
    assert is_compound_question("List tracks in the Rock and Roll genre") is False
    assert is_compound_question("Show FirstName and LastName of customers") is False
    assert is_compound_question("") is False


def test_is_compound_question_positive():
    """Verify multi-part questions trigger compound detection."""
    assert is_compound_question("List all genres and show total invoices") is True
    assert is_compound_question("Show top 5 tracks; also show top artist") is True
    assert is_compound_question("What is total sales? Who is top customer?") is True
    assert is_compound_question("List albums and also give me total revenue") is True
    assert is_compound_question("Show customers along with total spending") is True


def test_decompose_single_question_no_llm():
    """Verify single question is returned directly without invoking LLM."""
    with patch("src.core.decomposition.call_llm_json") as mock_call:
        res = decompose_question("How many tracks are there?")
        assert res == ["How many tracks are there?"]
        mock_call.assert_not_called()


def test_decompose_compound_question_with_mock_llm():
    """Verify compound question is split into sub-questions via LLM."""
    mock_payload = {
        "sub_questions": [
            "List all genres",
            "Show total invoices count",
        ]
    }
    with patch("src.core.decomposition.call_llm_json", return_value=mock_payload) as mock_call:
        res = decompose_question("List all genres and show total invoices")
        assert res == ["List all genres", "Show total invoices count"]
        mock_call.assert_called_once()


def test_decompose_heuristic_fallback():
    """Verify semicolon splitting when LLM is unavailable."""
    with patch("src.core.decomposition.call_llm_json", side_effect=RuntimeError("LLM offline")):
        res = decompose_question("List top 5 tracks; show total album revenue")
        assert len(res) == 2
        assert res[0] == "List top 5 tracks"
        assert res[1] == "show total album revenue"


def test_parse_query_tasks_raw_sql():
    """Verify parsing plain raw SQL."""
    res = parse_query_tasks("SELECT * FROM Track LIMIT 5;")
    assert len(res) == 1
    assert res[0]["title"] == "Query Objective"
    assert res[0]["sql"] == "SELECT * FROM Track LIMIT 5;"


def test_parse_query_tasks_markdown_fence():
    """Verify parsing markdown fenced SQL."""
    raw = "```sql\nSELECT * FROM Invoice;\n```"
    res = parse_query_tasks(raw)
    assert len(res) == 1
    assert res[0]["sql"] == "SELECT * FROM Invoice;"


def test_parse_query_tasks_json_array():
    """Verify parsing compound array of query tasks."""
    json_array = """[
        {"title": "Top Artists", "sql": "SELECT * FROM Artist LIMIT 5;"},
        {"title": "Top Albums", "sql": "SELECT * FROM Album LIMIT 5;"}
    ]"""
    res = parse_query_tasks(json_array)
    assert isinstance(res, list)
    assert len(res) == 2
    assert res[0]["title"] == "Top Artists"
    assert res[1]["title"] == "Top Albums"


def test_parse_query_tasks_out_of_domain():
    """Verify parsing out-of-domain rejection JSON object."""
    ood_json = """{
        "is_relevant": false,
        "reason": "This database does not contain patient medical records.",
        "needed_tables": ["patients", "prescriptions"],
        "suggested_questions": ["Show top tracks"]
    }"""
    res = parse_query_tasks(ood_json)
    assert isinstance(res, dict)
    assert res["is_relevant"] is False
    assert "patient" in res["reason"]

