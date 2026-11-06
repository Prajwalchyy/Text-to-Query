import sys
import pytest
from pathlib import Path

# Add project root and archive to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "backend" / "archive" / "legacy_pipeline"))

from backend.src.engines.spreadsheet_engine import SpreadsheetEngine
from backend.src.guardrails.pandas_guard import validate_pandas_code
from backend.archive.legacy_pipeline.F15_spreadsheet_generator import SpreadsheetGenerator
from backend.archive.legacy_pipeline.F16_spreadsheet_pipeline import TextToSpreadsheetPipeline


def test_pandas_guardrail():
    # Safe code
    safe_code = "result_df = df[df['TotalAmount'] > 500].groupby('Region').size().reset_index()"
    is_safe, err = validate_pandas_code(safe_code)
    assert is_safe is True
    assert err is None

    # Malicious import
    bad_code1 = "import os\nos.system('calc')"
    is_safe1, err1 = validate_pandas_code(bad_code1)
    assert is_safe1 is False
    assert "forbidden" in err1.lower()

    # Malicious file open
    bad_code2 = "with open('secret.txt', 'r') as f: data = f.read()"
    is_safe2, err2 = validate_pandas_code(bad_code2)
    assert is_safe2 is False
    assert "forbidden" in err2.lower()


def test_csv_pipeline_execution(monkeypatch):
    csv_path = "backend/data/csv/sales_performance.csv"
    engine = SpreadsheetEngine(csv_path)
    pipeline = TextToSpreadsheetPipeline(engine)

    # Mock generator to avoid live external OpenAI network dependency during automated test runs
    monkeypatch.setattr(
        pipeline.generator,
        "generate",
        lambda *args, **kwargs: [{
            "title": "Top Customers",
            "code": "result_df = df.sort_values(by='TotalAmount', ascending=False).head(3)",
            "explanation": "Top 3 customers"
        }]
    )

    res = pipeline.run_pipeline("Show top 3 customers with highest total spending")
    assert res["status"] == "SUCCESS"
    assert res["code_type"] == "pandas"
    assert "result_df" in res["final_sql"]
    assert len(res["data"]) > 0


def test_excel_pipeline_execution(monkeypatch):
    excel_path = "backend/data/excel/financial_budget.xlsx"
    engine = SpreadsheetEngine(excel_path)
    pipeline = TextToSpreadsheetPipeline(engine)

    # Mock generator to avoid live external OpenAI network dependency during automated test runs
    monkeypatch.setattr(
        pipeline.generator,
        "generate",
        lambda *args, **kwargs: [{
            "title": "Sales Budget",
            "formula": "=SUM(B2:B10)",
            "target_cell": "B11",
            "explanation": "Total budget",
            "eval_code": "result_df = df.head(3)"
        }]
    )

    res = pipeline.run_pipeline("What is the remaining budget for Sales?")
    assert res["status"] == "SUCCESS"
    assert res["code_type"] == "excel_formula"
    assert res["final_sql"].startswith("=")
    assert len(res["data"]) > 0
