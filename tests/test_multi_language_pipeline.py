import sys
import pytest
from pathlib import Path

# Add project root and backend/src to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "backend" / "src"))

from backend.src.core.polyglot import MultiLanguageGenerator, LANGUAGE_CONFIG
from backend.src.dialects.tabular import SpreadsheetEngine


def test_domain_compatibility_rules():
    """Validates strict domain guardrails: Excel formula and MQL boundary enforcement."""
    gen = MultiLanguageGenerator()

    # 1. Relational SQL DB: accepts SQL, Python (Pandas), R; rejects NoSQL, Excel, JS, Java, C#
    assert gen.is_language_supported("sql", "sql") is True
    assert gen.is_language_supported("sql", "pandas") is True
    assert gen.is_language_supported("sql", "r") is True
    assert gen.is_language_supported("sql", "excel_formula") is False
    assert gen.is_language_supported("sql", "nosql") is False
    assert gen.is_language_supported("sql", "javascript") is False
    assert gen.is_language_supported("sql", "java") is False
    assert gen.is_language_supported("sql", "csharp") is False

    # 2. NoSQL DB: accepts MQL, Python, R; rejects SQL, Excel, JS, Java, C#
    assert gen.is_language_supported("nosql", "nosql") is True
    assert gen.is_language_supported("nosql", "pandas") is True
    assert gen.is_language_supported("nosql", "r") is True
    assert gen.is_language_supported("nosql", "excel_formula") is False
    assert gen.is_language_supported("nosql", "sql") is False
    assert gen.is_language_supported("nosql", "javascript") is False
    assert gen.is_language_supported("nosql", "java") is False
    assert gen.is_language_supported("nosql", "csharp") is False

    # 3. CSV & Excel Spreadsheets: accept Pandas, Excel Formula, R; reject SQL, NoSQL, JS, Java, C#
    for sheet_type in ["csv", "excel"]:
        assert gen.is_language_supported(sheet_type, "pandas") is True
        assert gen.is_language_supported(sheet_type, "excel_formula") is True
        assert gen.is_language_supported(sheet_type, "r") is True
        assert gen.is_language_supported(sheet_type, "sql") is False
        assert gen.is_language_supported(sheet_type, "nosql") is False
        assert gen.is_language_supported(sheet_type, "javascript") is False
        assert gen.is_language_supported(sheet_type, "java") is False
        assert gen.is_language_supported(sheet_type, "csharp") is False


def test_sql_execution_on_csv_spreadsheet():
    """Verifies executing ANSI SQL directly on spreadsheet data via in-memory SQLite virtual tables."""
    csv_path = root_dir / "backend" / "data" / "csv" / "sales_performance.csv"
    engine = SpreadsheetEngine(str(csv_path), file_type="csv")

    # Run SQL directly on the CSV dataframe
    sql = "SELECT CustomerName, TotalAmount FROM data WHERE TotalAmount > 1000 ORDER BY TotalAmount DESC LIMIT 3"
    results = engine.execute_sql_query(sql)

    assert isinstance(results, list)
    assert len(results) > 0
    assert "CustomerName" in results[0]
    assert "TotalAmount" in results[0]
    assert results[0]["TotalAmount"] > 1000


def test_sql_execution_on_excel_spreadsheet():
    """Verifies executing ANSI SQL directly on multi-sheet Excel workbooks via in-memory SQLite tables."""
    excel_path = root_dir / "backend" / "data" / "excel" / "financial_budget.xlsx"
    engine = SpreadsheetEngine(str(excel_path), file_type="excel")

    sheet_name = list(engine.dfs.keys())[0]
    sql = f"SELECT * FROM {sheet_name} LIMIT 5"
    results = engine.execute_sql_query(sql)

    assert isinstance(results, list)
    assert len(results) > 0


def test_unsupported_language_exception():
    """Ensures attempting to run nosql on SQL raises an explicit ValueError."""
    gen = MultiLanguageGenerator()
    with pytest.raises(ValueError) as excinfo:
        gen.generate_code(
            question="Calculate total revenue",
            schema_context="CREATE TABLE sales (id INT, amount INT);",
            db_type="sql",
            target_language="nosql"
        )
    assert "not supported" in str(excinfo.value)
