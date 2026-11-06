import sys
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
src_dir = backend_dir / "src"
for p in [str(root_dir), str(backend_dir), str(src_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from engines.spreadsheet_engine import (
    resolve_spreadsheet_path,
    excel_col_letter,
    letter_to_col_index,
    clean_records_for_json,
    load_spreadsheet,
    get_spreadsheet_schema,
    format_spreadsheet_schema_context,
    execute_pandas_code,
    execute_sql_on_spreadsheet,
    execute_excel_formula,
)


def test_excel_coordinate_conversions():
    assert excel_col_letter(0) == "A"
    assert excel_col_letter(25) == "Z"
    assert excel_col_letter(26) == "AA"
    assert excel_col_letter(27) == "AB"

    assert letter_to_col_index("A") == 0
    assert letter_to_col_index("Z") == 25
    assert letter_to_col_index("AA") == 26
    assert letter_to_col_index("AB") == 27


def test_clean_records_for_json():
    records = [
        {
            "name": "Alpha",
            "nan_val": float("nan"),
            "inf_val": float("inf"),
            "timestamp": pd.Timestamp("2026-03-01 12:00:00"),
            "np_int": np.int64(42),
            "np_float": np.float64(3.1415),
        }
    ]
    cleaned = clean_records_for_json(records)
    assert cleaned[0]["nan_val"] is None
    assert cleaned[0]["inf_val"] is None
    assert cleaned[0]["timestamp"] == "2026-03-01 12:00:00"
    assert cleaned[0]["np_int"] == 42
    assert isinstance(cleaned[0]["np_float"], float)


def test_load_default_csv():
    dfs = load_spreadsheet(file_type="csv")
    assert len(dfs) == 1
    sheet_name = list(dfs.keys())[0]
    df = dfs[sheet_name]
    assert len(df) > 0
    assert len(df.columns) > 0


def test_load_default_excel():
    dfs = load_spreadsheet(file_type="excel")
    assert len(dfs) >= 1
    for sheet_name, df in dfs.items():
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0


def test_spreadsheet_schema_and_context():
    dfs = load_spreadsheet(file_type="csv")
    schema = get_spreadsheet_schema(dfs)
    assert "tables" in schema
    assert len(schema["tables"]) == 1
    table_meta = schema["tables"][0]
    assert "columns_meta" in table_meta
    assert "data_range" in table_meta

    context = format_spreadsheet_schema_context(dfs)
    assert "### Sheet:" in context
    assert "Columns & Cell Coordinates:" in context
    assert "Sample Data" in context


def test_execute_pandas_code():
    dfs = load_spreadsheet(file_type="csv")
    code = """
result_df = df.head(3)
"""
    records = execute_pandas_code(dfs, code)
    assert len(records) == 3
    assert isinstance(records[0], dict)


def test_execute_sql_on_spreadsheet():
    dfs = load_spreadsheet(file_type="csv")
    sheet_name = list(dfs.keys())[0]
    sql = f"SELECT COUNT(*) AS row_count FROM {sheet_name};"
    records = execute_sql_on_spreadsheet(dfs, sql)
    assert len(records) == 1
    assert "row_count" in records[0]
    assert records[0]["row_count"] > 0

    # Also test 'sales' alias
    alias_records = execute_sql_on_spreadsheet(dfs, "SELECT COUNT(*) AS total FROM sales;")
    assert len(alias_records) == 1
    assert alias_records[0]["total"] == records[0]["row_count"]


def test_execute_excel_formula():
    dfs = {
        "Budget": pd.DataFrame({
            "Department": ["Engineering", "Marketing", "Sales", "HR"],
            "Allocated": [100000, 50000, 75000, 30000],
            "Spent": [90000, 55000, 60000, 28000],
        })
    }

    # Test =SUM(B2:B5)
    sum_res = execute_excel_formula(dfs, "=SUM(B2:B5)", primary_sheet="Budget")
    assert len(sum_res) == 1
    assert sum_res[0]["Result"] == 255000.0

    # Test =AVERAGE(B2:B5)
    avg_res = execute_excel_formula(dfs, "=AVERAGE(B2:B5)", primary_sheet="Budget")
    assert len(avg_res) == 1
    assert avg_res[0]["Result"] == 63750.0

    # Test =FILTER(A2:C5, B2:B5 > 60000)
    filter_res = execute_excel_formula(dfs, "=FILTER(A2:C5, B2:B5 > 60000)", primary_sheet="Budget")
    assert len(filter_res) == 2
    deps = [r["Department"] for r in filter_res]
    assert "Engineering" in deps
    assert "Sales" in deps

