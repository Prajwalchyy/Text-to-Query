"""
Unit tests for Universal Reflection & Self-Correction Engine (backend/src/core/reflection.py).
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.core.reflection import (
    CorrectionEngine,
    build_nosql_repair_prompt,
    build_pandas_repair_prompt,
    build_sql_repair_prompt,
    clean_repaired_code,
    run_with_reflection,
)
from src.guardrails.sql_guard import SQLValidationResult


def test_clean_repaired_code_markdown_blocks():
    """Verify cleaning markdown code fences across various dialects."""
    # SQL fence
    raw_sql = "```sql\nSELECT * FROM Track LIMIT 10;\n```"
    assert clean_repaired_code(raw_sql) == "SELECT * FROM Track LIMIT 10;"

    # Python fence
    raw_py = "```python\nresult_df = df[df['Total'] > 10]\n```"
    assert clean_repaired_code(raw_py) == "result_df = df[df['Total'] > 10]"

    # Raw string without fences
    raw_plain = "SELECT COUNT(*) FROM Invoice;"
    assert clean_repaired_code(raw_plain) == "SELECT COUNT(*) FROM Invoice;"


def test_clean_repaired_code_json_wrapper():
    """Verify extracting code when LLM returns a JSON object."""
    json_response = '{"title": "Track count", "code": "SELECT COUNT(*) FROM Track;"}'
    assert clean_repaired_code(json_response) == "SELECT COUNT(*) FROM Track;"

    json_sql = '{"sql": "SELECT TrackId, Name FROM Track LIMIT 5;"}'
    assert clean_repaired_code(json_sql) == "SELECT TrackId, Name FROM Track LIMIT 5;"


def test_prompt_builders():
    """Verify prompt formatting for SQL, NoSQL, and Pandas."""
    sql_prompt = build_sql_repair_prompt(
        question="How many tracks?",
        broken_sql="SELECT count FROM Track;",
        error_message="no such column: count",
        schema_context="Track(TrackId, Name)",
    )
    assert "How many tracks?" in sql_prompt
    assert "SELECT count FROM Track;" in sql_prompt
    assert "no such column: count" in sql_prompt
    assert "Track(TrackId, Name)" in sql_prompt

    nosql_prompt = build_nosql_repair_prompt(
        question="Find active customers",
        broken_mql='{"$match": {"status": "active"}}',
        error_message="collection not found",
        schema_context="customers: {_id, status}",
    )
    assert "MongoDB Engineer" in nosql_prompt
    assert "collection not found" in nosql_prompt

    pandas_prompt = build_pandas_repair_prompt(
        question="Highest budget",
        broken_code="result_df = df.sort('Budget')",
        error_message="DataFrame object has no attribute sort",
        schema_context="Columns: ['Budget', 'Department']",
    )
    assert "result_df" in pandas_prompt
    assert "DataFrame object has no attribute sort" in pandas_prompt


def test_run_with_reflection_immediate_success():
    """Verify reflection completes in 1 attempt when query executes cleanly."""
    mock_execute = MagicMock(return_value=[{"TrackId": 1, "Name": "For Those About To Rock"}])
    mock_validate = MagicMock(return_value=(True, None))

    result = run_with_reflection(
        execute_fn=mock_execute,
        initial_query="SELECT TrackId, Name FROM Track LIMIT 1;",
        validate_fn=mock_validate,
        max_attempts=3,
    )

    assert result["success"] is True
    assert result["attempts"] == 1
    assert result["error"] is None
    assert len(result["data"]) == 1
    assert result["final_query"] == "SELECT TrackId, Name FROM Track LIMIT 1;"
    assert len(result["history"]) == 1
    assert result["history"][0]["success"] is True
    mock_execute.assert_called_once()


def test_run_with_reflection_self_corrects_on_attempt_2():
    """Verify reflection heals an execution error on attempt 2."""
    attempts_seen = []

    def mock_execute(query: str):
        attempts_seen.append(query)
        if "InvalidCol" in query:
            raise RuntimeError("no such column: InvalidCol")
        return [{"TrackId": 1, "Title": "Album 1"}]

    def mock_repair(query: str, error: str, attempt: int) -> str:
        assert "InvalidCol" in query
        assert "no such column" in error
        return "SELECT TrackId, Title FROM Album LIMIT 1;"

    result = run_with_reflection(
        execute_fn=mock_execute,
        initial_query="SELECT InvalidCol, Title FROM Album LIMIT 1;",
        repair_fn=mock_repair,
        max_attempts=3,
    )

    assert result["success"] is True
    assert result["attempts"] == 2
    assert result["error"] is None
    assert result["final_query"] == "SELECT TrackId, Title FROM Album LIMIT 1;"
    assert len(result["data"]) == 1
    assert len(result["history"]) == 2
    assert result["history"][0]["execution_error"] == "no such column: InvalidCol"
    assert result["history"][1]["success"] is True


def test_run_with_reflection_guardrail_blocked_then_healed():
    """Verify reflection catches guardrail failure on attempt 1 and recovers on attempt 2."""
    def mock_validate(query: str):
        if "DROP" in query.upper():
            return False, "Destructive keyword DROP forbidden."
        return True, None

    def mock_execute(query: str):
        return [{"count": 42}]

    def mock_repair(query: str, error: str) -> str:
        return "SELECT COUNT(*) FROM Invoice;"

    result = run_with_reflection(
        execute_fn=mock_execute,
        initial_query="DROP TABLE Invoice; SELECT 1;",
        validate_fn=mock_validate,
        repair_fn=mock_repair,
        max_attempts=3,
    )

    assert result["success"] is True
    assert result["attempts"] == 2
    assert result["final_query"] == "SELECT COUNT(*) FROM Invoice;"
    assert result["data"] == [{"count": 42}]
    assert result["history"][0]["validation_error"] == "Destructive keyword DROP forbidden."


def test_run_with_reflection_exhausts_max_retries():
    """Verify reflection loop halts cleanly when max_attempts is reached."""
    def mock_execute(query: str):
        raise ValueError("Persistent syntax error")

    def mock_repair(query: str, error: str) -> str:
        return query + " -- repair attempted"

    result = run_with_reflection(
        execute_fn=mock_execute,
        initial_query="SELECT * FROM Unknown;",
        repair_fn=mock_repair,
        max_attempts=3,
    )

    assert result["success"] is False
    assert result["attempts"] == 3
    assert "Failed after 3 attempts" in result["error"]
    assert result["data"] == []
    assert len(result["history"]) == 3


def test_run_with_reflection_with_namedtuple_validator():
    """Verify compatibility with NamedTuple validator results (like SQLValidationResult)."""
    valid_res = SQLValidationResult(is_valid=True, reason=None, sanitized_sql="SELECT 1")
    invalid_res = SQLValidationResult(is_valid=False, reason="Disallowed table", sanitized_sql="")

    # Valid
    res_ok = run_with_reflection(
        execute_fn=lambda q: [{"1": 1}],
        initial_query="SELECT 1",
        validate_fn=lambda q: valid_res,
        max_attempts=1,
    )
    assert res_ok["success"] is True

    # Invalid
    res_bad = run_with_reflection(
        execute_fn=lambda q: [{"1": 1}],
        initial_query="SELECT * FROM secret",
        validate_fn=lambda q: invalid_res,
        max_attempts=1,
    )
    assert res_bad["success"] is False
    assert "Disallowed table" in res_bad["error"]


def test_run_with_reflection_prompt_fn_with_mock_llm():
    """Verify repair_prompt_fn dispatches to call_llm when provided."""
    mock_llm_response = "```sql\nSELECT ArtistId, Name FROM Artist LIMIT 5;\n```"

    with patch("src.core.llm.call_llm", return_value=mock_llm_response) as mock_call:
        def mock_execute(query: str):
            if "FAIL" in query:
                raise RuntimeError("Failed query execution")
            return [{"ArtistId": 1, "Name": "AC/DC"}]

        def mock_prompt_builder(query: str, err: str):
            return f"Repair this: {query} with error: {err}"

        result = run_with_reflection(
            execute_fn=mock_execute,
            initial_query="SELECT FAIL FROM Artist;",
            repair_prompt_fn=mock_prompt_builder,
            max_attempts=2,
        )

        assert result["success"] is True
        assert result["attempts"] == 2
        assert result["final_query"] == "SELECT ArtistId, Name FROM Artist LIMIT 5;"
        mock_call.assert_called_once()


def test_correction_engine_adapter():
    """Verify legacy CorrectionEngine adapter returns expected 4-element tuple."""
    mock_db = MagicMock()
    mock_db.get_table_names.return_value = ["Album"]
    mock_db.execute_query.side_effect = [
        RuntimeError("no such column: BadCol"),
        [{"AlbumId": 1, "Title": "Balls to the Wall"}],
    ]

    engine = CorrectionEngine(db_engine=mock_db)
    
    with patch.object(
        engine,
        "build_reflection_prompt",
        return_value="Fix query prompt"
    ), patch(
        "src.core.llm.call_llm",
        return_value="SELECT AlbumId, Title FROM Album LIMIT 1;"
    ):
        success, data, sql, attempts = engine.run_with_self_correction(
            user_question="Get first album",
            initial_sql="SELECT BadCol FROM Album LIMIT 1;",
            max_retries=2,
        )

        assert success is True
        assert attempts == 2
        assert sql == "SELECT AlbumId, Title FROM Album LIMIT 1;"
        assert len(data) == 1
