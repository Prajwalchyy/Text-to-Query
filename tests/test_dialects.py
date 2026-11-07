"""
Unit tests for the Unified Dialects Architecture (backend/src/dialects/).

Validates that:
  1. dialects.base exports universal normalization and protocols.
  2. dialects.sql encapsulates SQL guardrails, schema introspection, and execution.
  3. dialects.nosql encapsulates NoSQL guardrails, collection loading, and in-memory MQL execution.
  4. dialects.tabular encapsulates Pandas AST guardrails, spreadsheet loading, and execution.
"""

import sys
from pathlib import Path
import pytest

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
src_dir = backend_dir / "src"
for p in [str(root_dir), str(backend_dir), str(src_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from dialects.base import (
    EngineProtocol,
    ValidationResult,
    normalize_doc_tree,
    resolve_dataset_file,
    sanitize_records_for_json,
    sanitize_scalar,
)
from dialects.sql import (
    FORBIDDEN_SQL_KEYWORDS,
    SQLValidationResult,
    check_keyword_not_allowed,
    execute_sql_query,
    get_table_names,
    validate_sql,
)
from dialects.nosql import (
    FORBIDDEN_NOSQL_OPERATORS,
    NoSQLValidationResult,
    execute_mql,
    get_collection_names,
    load_nosql_collections,
    validate_mql,
)
from dialects.tabular import (
    PandasValidationResult,
    SpreadsheetEngine,
    execute_excel_formula,
    execute_pandas_code,
    load_spreadsheet,
    validate_pandas_code,
)


def test_dialects_base():
    # ValidationResult contract
    vr = ValidationResult(is_valid=True, error=None, sanitized_query="SELECT 1;")
    assert vr.is_valid is True
    assert vr.sanitized_query == "SELECT 1;"

    # Sanitizer
    assert sanitize_scalar(float("nan")) is None
    assert sanitize_scalar({"a": float("inf"), "b": 10}) == {"a": None, "b": 10}


def test_dialects_sql():
    # Guardrail
    valid_res = validate_sql("SELECT * FROM Artist LIMIT 3;")
    assert valid_res.is_valid is True
    assert valid_res.error is None

    drop_res = validate_sql("DROP TABLE Artist;")
    assert drop_res.is_valid is False
    assert "Forbidden keyword 'DROP'" in drop_res.error

    # Execution
    tables = get_table_names()
    assert "Artist" in tables
    rows = execute_sql_query("SELECT ArtistId, Name FROM Artist LIMIT 2;")
    assert len(rows) == 2
    assert "Name" in rows[0]


def test_dialects_nosql():
    # Guardrail
    valid_mql = validate_mql("db.products.find({'price': {'$gt': 100}})")
    assert valid_mql.is_valid is True
    assert valid_mql.collection == "products"

    bad_mql = validate_mql("db.products.drop()")
    assert bad_mql.is_valid is False
    assert "Forbidden NoSQL operator 'drop'" in bad_mql.error

    # In-memory execution
    collections = load_nosql_collections()
    col_names = get_collection_names(collections)
    assert len(col_names) > 0
    first_col = col_names[0]
    res = execute_mql(collections, f"db.{first_col}.find().limit(2)")
    assert len(res) <= 2


def test_dialects_tabular():
    # Guardrail
    safe_code = "result_df = df[df['Amount'] > 100]"
    safe_res = validate_pandas_code(safe_code)
    assert safe_res.is_valid is True

    unsafe_code = "import os\nos.system('dir')"
    unsafe_res = validate_pandas_code(unsafe_code)
    assert unsafe_res.is_valid is False
    assert "Security Guardrail Rejection" in unsafe_res.error

    # Execution
    dfs = load_spreadsheet(file_type="excel")
    assert len(dfs) > 0
    formula_res = execute_excel_formula(dfs, "=SUM(C2:C5)")
    assert len(formula_res) == 1
    assert "Result" in formula_res[0]

