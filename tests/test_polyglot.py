"""
Unit tests for Polyglot Multi-Language Generator & Converter (backend/src/core/polyglot.py).
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.core.polyglot import (
    LANGUAGE_CONFIG,
    MultiLanguageGenerator,
    convert_code,
    generate_polyglot_code,
    get_supported_languages,
    is_language_supported,
)


def test_language_config_catalog():
    """Verify all 5 target languages are defined with required attributes."""
    expected_keys = {"sql", "pandas", "r", "nosql", "excel_formula"}
    assert set(LANGUAGE_CONFIG.keys()) == expected_keys
    for lang_id, cfg in LANGUAGE_CONFIG.items():
        assert cfg["id"] == lang_id
        assert "name" in cfg
        assert "badge" in cfg
        assert "color" in cfg
        assert "supported_db_types" in cfg


def test_is_language_supported_matrix():
    """Verify matrix of supported languages across SQL, NoSQL, CSV, and Excel."""
    # 1. SQL (Relational)
    assert is_language_supported("sql", "sql") is True
    assert is_language_supported("sql", "pandas") is True
    assert is_language_supported("sql", "r") is True
    assert is_language_supported("sql", "excel_formula") is True
    assert is_language_supported("sql", "javascript") is False
    assert is_language_supported("sql", "java") is False
    assert is_language_supported("sql", "csharp") is False
    assert is_language_supported("sql", "nosql") is False

    # 2. NoSQL (MongoDB)
    assert is_language_supported("nosql", "nosql") is True
    assert is_language_supported("nosql", "pandas") is True
    assert is_language_supported("nosql", "r") is True
    assert is_language_supported("nosql", "excel_formula") is True
    assert is_language_supported("nosql", "javascript") is False
    assert is_language_supported("nosql", "java") is False
    assert is_language_supported("nosql", "csharp") is False
    assert is_language_supported("nosql", "sql") is False

    # 3. CSV & Excel (Spreadsheets)
    for sheet_type in ["csv", "excel"]:
        assert is_language_supported(sheet_type, "sql") is True
        assert is_language_supported(sheet_type, "pandas") is True
        assert is_language_supported(sheet_type, "excel_formula") is True
        assert is_language_supported(sheet_type, "r") is True
        assert is_language_supported(sheet_type, "javascript") is False
        assert is_language_supported(sheet_type, "java") is False
        assert is_language_supported(sheet_type, "csharp") is False
        assert is_language_supported(sheet_type, "nosql") is False


def test_get_supported_languages():
    """Verify language list filtering by database engine type."""
    sql_langs = [cfg["id"] for cfg in get_supported_languages("sql")]
    assert "sql" in sql_langs
    assert "excel_formula" in sql_langs
    assert "nosql" not in sql_langs

    nosql_langs = [cfg["id"] for cfg in get_supported_languages("nosql")]
    assert "nosql" in nosql_langs
    assert "excel_formula" in nosql_langs
    assert "sql" not in nosql_langs

    csv_langs = [cfg["id"] for cfg in get_supported_languages("csv")]
    assert "excel_formula" in csv_langs
    assert "sql" in csv_langs
    assert "nosql" not in csv_langs


def test_generate_polyglot_code_success_with_mock():
    """Verify generating code in a supported dialect."""
    mock_payload = {
        "title": "Top Spenders in R",
        "code": "library(mongolite)\nm <- mongo(collection = 'customers')\nm$find()",
        "eval_mql": '{"collection": "customers", "query": {}}',
        "explanation": "Fetches customers in R.",
    }

    with patch("src.core.polyglot.call_llm_json", return_value=mock_payload):
        res = generate_polyglot_code(
            question="Find customers",
            schema_context="customers collection",
            db_type="nosql",
            target_language="r",
        )
        assert res["code_type"] == "r"
        assert "mongolite" in res["code"]
        assert res["title"] == "Top Spenders in R"


def test_generate_polyglot_code_unsupported_language_raises():
    """Verify attempting to generate nosql on SQL dataset raises ValueError."""
    with pytest.raises(ValueError) as exc:
        generate_polyglot_code(
            question="Total sum",
            schema_context="Track table",
            db_type="sql",
            target_language="nosql",
        )
    assert "not supported" in str(exc.value)


def test_convert_code_success_with_mock():
    """Verify cross-dialect query conversion."""
    mock_payload = {
        "title": "Converted to Pandas",
        "code": "result_df = df[df['price'] > 50]",
        "explanation": "Filters rows where price > 50.",
    }

    with patch("src.core.polyglot.call_llm_json", return_value=mock_payload):
        res = convert_code(
            code="SELECT * FROM products WHERE price > 50",
            from_language="sql",
            to_language="pandas",
            schema_context="products(price INT)",
            db_type="csv",
        )
        assert res["code_type"] == "pandas"
        assert "result_df" in res["code"]


def test_convert_code_unsupported_language_raises():
    """Verify converting to an incompatible dialect raises ValueError."""
    with pytest.raises(ValueError) as exc:
        convert_code(
            code="SELECT 1",
            from_language="sql",
            to_language="nosql",
            schema_context="schema",
            db_type="sql",
        )
    assert "not supported" in str(exc.value)


def test_multi_language_generator_legacy_adapter():
    """Verify backward compatibility of MultiLanguageGenerator adapter class."""
    gen = MultiLanguageGenerator()
    assert gen.is_language_supported("sql", "sql") is True
    assert gen.is_language_supported("sql", "nosql") is False

    langs = gen.get_supported_languages("nosql")
    assert any(l["id"] == "nosql" for l in langs)

    mock_payload = {
        "title": "Top Customers",
        "code": "SELECT * FROM Customer LIMIT 10;",
        "eval_sql": "SELECT * FROM Customer LIMIT 10;",
        "explanation": "Query customer table.",
    }
    with patch("src.core.polyglot.call_llm_json", return_value=mock_payload):
        code_res = gen.generate_code(
            question="Top 10 customers",
            schema_context="Customer(CustomerId)",
            db_type="sql",
            target_language="sql",
        )
        assert code_res["code_type"] == "sql"
        assert "Customer" in code_res["code"]

