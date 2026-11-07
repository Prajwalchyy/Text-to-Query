"""
Unit & Integration Tests for Master Pipeline Router (src/pipelines/router.py).

Tests:
  - Database type normalization (SQL, NoSQL, CSV, Excel).
  - Data source and entity introspection.
  - Empty question validation.
  - SQL end-to-end execution with schema introspection and telemetry.
  - Out-of-Domain (OOD) guardrail interception.
  - Multi-language polyglot routing (e.g. Python on SQL).
  - Domain compatibility guardrail (e.g. Excel formula on SQL database blocked).
  - Multi-query compound query decomposition and execution.
  - Self-repair reflection loop on failed initial queries.
  - CSV spreadsheet pipeline execution.
  - NoSQL MQL pipeline execution.
  - FunctionalPipelineAdapter backward compatibility.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root and backend/src are on sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
backend_src_dir = backend_dir / "src"
for p in [str(root_dir), str(backend_dir), str(backend_src_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.pipelines.router import (
    run_pipeline,
    normalize_db_type,
    resolve_datasource,
    introspect_datasource,
    FunctionalPipelineAdapter,
)
from config import DEFAULT_CHINOOK_PATH, DEFAULT_CSV_PATH, DEFAULT_EXCEL_PATH, DEFAULT_NOSQL_PATH


# ==============================================================================
# 1. Type Normalization Tests
# ==============================================================================
def test_normalize_db_type():
    assert normalize_db_type("sqlite") == "sql"
    assert normalize_db_type("SQLITE3") == "sql"
    assert normalize_db_type("relational") == "sql"
    assert normalize_db_type("sql") == "sql"

    assert normalize_db_type("nosql") == "nosql"
    assert normalize_db_type("mongodb") == "nosql"
    assert normalize_db_type("mql") == "nosql"
    assert normalize_db_type("json") == "nosql"

    assert normalize_db_type("csv") == "csv"

    assert normalize_db_type("excel") == "excel"
    assert normalize_db_type("xlsx") == "excel"

    assert normalize_db_type(None) == "sql"
    assert normalize_db_type("unknown_type") == "sql"


# ==============================================================================
# 2. Data Source Resolution Tests
# ==============================================================================
def test_resolve_datasource_chinook():
    db_info, canonical_type, resolved_path = resolve_datasource("chinook")
    assert canonical_type == "sql"
    assert resolved_path.exists()
    assert resolved_path.name == "chinook.db"


def test_resolve_datasource_fallback():
    db_info, canonical_type, resolved_path = resolve_datasource("non_existent_id")
    assert canonical_type == "sql"
    assert resolved_path.exists()


# ==============================================================================
# 3. Introspection Tests
# ==============================================================================
def test_introspect_datasource_sql():
    tables, schema_str, path = introspect_datasource("sql", DEFAULT_CHINOOK_PATH)
    assert isinstance(tables, list)
    assert len(tables) > 0
    assert "Artist" in tables or "Album" in tables
    assert "CREATE TABLE" in schema_str or "Table:" in schema_str or "Artist" in schema_str


def test_introspect_datasource_csv():
    sheets, schema_str, dfs = introspect_datasource("csv", DEFAULT_CSV_PATH)
    assert isinstance(sheets, list)
    assert len(sheets) > 0
    assert "data" in sheets or len(dfs) > 0
    assert "Columns:" in schema_str or "TotalAmount" in schema_str or len(schema_str) > 0


# ==============================================================================
# 4. Empty Question Validation
# ==============================================================================
def test_run_pipeline_empty_question():
    res = run_pipeline("", db_id="chinook")
    assert res["status"] == "FAILED"
    assert "empty" in res["summary"].lower()
    assert res["confidence_score"] == 0.0
    assert res["latency_ms"] >= 0


# ==============================================================================
# 5. SQL Pipeline End-to-End Success
# ==============================================================================
def test_run_pipeline_sql_success():
    mock_llm_sql = (
        '```json\n'
        '[\n'
        '  {"title": "Top Artists", "sql": "SELECT Name FROM Artist ORDER BY ArtistId ASC LIMIT 3;"}\n'
        ']\n'
        '```'
    )

    with patch("src.pipelines.router.call_llm", return_value=mock_llm_sql):
        res = run_pipeline("Show top 3 artists", db_id="chinook")

    assert res["status"] == "SUCCESS"
    assert res["final_sql"] is not None
    assert "SELECT Name FROM Artist" in res["final_sql"]
    assert res["code_type"] == "sql"
    assert len(res["data"]) == 3
    assert "Name" in res["columns"]
    assert res["confidence_score"] > 0.0
    assert res["attempts"] == 1
    assert len(res["sub_queries"]) == 1
    assert res["sub_queries"][0]["status"] == "SUCCESS"


# ==============================================================================
# 6. Out-of-Domain (OOD) Guardrail Interception
# ==============================================================================
def test_run_pipeline_out_of_domain():
    mock_ood_response = (
        '{\n'
        '  "is_relevant": false,\n'
        '  "reason": "This database does not contain cryptocurrency prices.",\n'
        '  "needed_tables": ["CryptoCurrencies", "ExchangeRates"],\n'
        '  "suggested_questions": ["What artists are in the catalog?", "Show top selling tracks"]\n'
        '}'
    )

    with patch("src.pipelines.router.call_llm", return_value=mock_ood_response):
        res = run_pipeline("What is the current Bitcoin price?", db_id="chinook")

    assert res["status"] == "OUT_OF_DOMAIN"
    assert res["final_sql"] is None
    assert res["data"] == []
    assert res["is_relevant"] is False
    assert "CryptoCurrencies" in res["needed_tables"]
    assert len(res["available_tables"]) > 0
    assert len(res["suggested_questions"]) == 2
    assert "Bitcoin" in res["summary"] or "cryptocurrency" in res["summary"]


# ==============================================================================
# 7. Polyglot Multi-Language Routing Tests
# ==============================================================================
def test_run_pipeline_polyglot_python_on_sql():
    mock_poly_res = {
        "title": "Top Artists in Python",
        "code": "import sqlite3\nconn = sqlite3.connect('chinook.db')\ncursor = conn.cursor()\ncursor.execute('SELECT Name FROM Artist LIMIT 3')\nrows = cursor.fetchall()",
        "eval_sql": "SELECT Name FROM Artist LIMIT 3",
        "explanation": "Connects to SQLite database and queries the Artist table using sqlite3 driver.",
        "language": "python",
    }

    with patch("src.pipelines.router.generate_polyglot_code", return_value=mock_poly_res):
        res = run_pipeline(
            "Show top 3 artists",
            db_id="chinook",
            target_language="python",
        )

    assert res["status"] == "SUCCESS"
    assert res["code_type"] == "python"
    assert "sqlite3" in res["final_sql"]
    assert len(res["data"]) == 3
    assert "Name" in res["columns"]
    assert res["confidence_score"] == 0.95


def test_run_pipeline_polyglot_unsupported_language_blocked():
    # Attempting to run NoSQL MQL on a relational SQLite database must fail cleanly
    res = run_pipeline(
        "Show all customers",
        db_id="chinook",
        target_language="nosql",
    )

    assert res["status"] == "FAILED"
    assert "not supported" in res["summary"].lower()
    assert res["final_sql"] is None


# ==============================================================================
# 8. Compound Query Decomposition Path
# ==============================================================================
def test_run_pipeline_compound_multi_query():
    mock_compound_llm = (
        '[\n'
        '  {"title": "First 2 Artists", "sql": "SELECT Name FROM Artist LIMIT 2;"},\n'
        '  {"title": "First 2 Genres", "sql": "SELECT Name FROM Genre LIMIT 2;"}\n'
        ']'
    )

    with patch("src.pipelines.router.call_llm", return_value=mock_compound_llm):
        res = run_pipeline("List 2 artists and 2 genres", db_id="chinook")

    assert res["status"] == "SUCCESS"
    assert res.get("is_multi_query") is True
    assert len(res["sub_queries"]) == 2
    assert res["sub_queries"][0]["status"] == "SUCCESS"
    assert res["sub_queries"][1]["status"] == "SUCCESS"
    assert len(res["sub_queries"][0]["data"]) == 2
    assert len(res["sub_queries"][1]["data"]) == 2
    assert "Executed all 2 sub-queries successfully." in res["summary"]


# ==============================================================================
# 9. Self-Repair Reflection Loop
# ==============================================================================
def test_run_pipeline_self_repair_reflection():
    # Initial LLM query references a nonexistent column
    broken_llm_output = (
        '[\n'
        '  {"title": "Artist Query", "sql": "SELECT NonExistentColumn FROM Artist LIMIT 1;"}\n'
        ']'
    )
    # Repaired SQL is valid
    repaired_sql = "SELECT Name FROM Artist LIMIT 1;"

    with patch("src.pipelines.router.call_llm", return_value=broken_llm_output), \
         patch("src.core.llm.call_llm", return_value=repaired_sql), \
         patch("src.pipelines.router.evaluate_result", return_value={"is_accurate": True, "confidence_score": 0.90, "summary": "Found 1 artist."}):
        res = run_pipeline("Get an artist", db_id="chinook", max_retries=2)

    assert res["status"] == "SUCCESS"
    assert res["attempts"] == 2
    assert "SELECT Name FROM Artist" in res["final_sql"]
    assert len(res["data"]) == 1


# ==============================================================================
# 10. Spreadsheet Pipeline CSV Execution
# ==============================================================================
def test_run_pipeline_csv_execution():
    mock_csv_output = (
        '```json\n'
        '[\n'
        '  {\n'
        '    "title": "Top Spenders",\n'
        '    "code": "result_df = df.sort_values(by=\'TotalAmount\', ascending=False).head(3)",\n'
        '    "explanation": "Sorts DataFrame by TotalAmount descending."\n'
        '  }\n'
        ']\n'
        '```'
    )

    # Register CSV or resolve direct CSV
    with patch("src.pipelines.router.call_llm", return_value=mock_csv_output), \
         patch("src.pipelines.router.get_database", return_value={
             "id": "sales_csv",
             "name": "Sales Performance",
             "type": "csv",
             "path": str(DEFAULT_CSV_PATH)
         }):
        res = run_pipeline("Show top 3 customers by total amount", db_id="sales_csv")

    assert res["status"] == "SUCCESS"
    assert res["code_type"] == "pandas"
    assert "result_df" in res["final_sql"]
    assert len(res["data"]) == 3
    assert "TotalAmount" in res["columns"]


# ==============================================================================
# 11. NoSQL Pipeline MQL Execution
# ==============================================================================
def test_run_pipeline_nosql_execution():
    mock_nosql_output = (
        '[\n'
        '  {\n'
        '    "title": "Find In Stock Products",\n'
        '    "mql": "db.products.find({\\"stock\\": {\\"$gt\\": 0}}).limit(3)",\n'
        '    "explanation": "Finds up to 3 products with stock > 0."\n'
        '  }\n'
        ']'
    )

    with patch("src.pipelines.router.call_llm", return_value=mock_nosql_output), \
         patch("src.pipelines.router.get_database", return_value={
             "id": "ecommerce_nosql",
             "name": "Ecommerce Store",
             "type": "nosql",
             "path": str(DEFAULT_NOSQL_PATH)
         }):
        res = run_pipeline("Show products in stock", db_id="ecommerce_nosql")

    assert res["status"] == "SUCCESS"
    assert res["code_type"] == "nosql"
    assert "find" in res["final_sql"]
    assert len(res["data"]) > 0


# ==============================================================================
# 12. FunctionalPipelineAdapter Tests
# ==============================================================================
def test_functional_pipeline_adapter():
    adapter = FunctionalPipelineAdapter(db_id="chinook")
    langs = adapter.get_supported_languages()
    lang_ids = [l["id"] for l in langs]
    assert "sql" in lang_ids
    assert "pandas" in lang_ids
    assert "r" in lang_ids
    assert "excel_formula" not in lang_ids
    assert "nosql" not in lang_ids

    mock_llm_sql = '[{"title": "Test", "sql": "SELECT 1 AS num;"}]'
    with patch("src.pipelines.router.call_llm", return_value=mock_llm_sql):
        res = adapter.run_pipeline("Select one")

    assert res["status"] == "SUCCESS"
    assert res["data"] == [{"num": 1}]
