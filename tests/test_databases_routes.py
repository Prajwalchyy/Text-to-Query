"""
Unit Tests for Database & Dataset API Routes.
Phase D Step D.2 Verification
"""

import io
import pytest
from fastapi import HTTPException, UploadFile

from backend.src.api.databases_routes import (
    get_databases,
    get_tables,
    delete_database,
    upload_dataset,
    append_table_script,
    append_collection_docs,
    introspect_schema,
    DatabaseController,
)


def test_get_databases_endpoint():
    """Verify get_databases returns all registered data sources."""
    data = get_databases()
    assert "databases" in data
    assert isinstance(data["databases"], list)
    assert len(data["databases"]) >= 4

    ids = [d["id"] for d in data["databases"]]
    assert "chinook" in ids
    assert "ecommerce_store" in ids
    assert "sales_performance" in ids
    assert "financial_budget" in ids


def test_get_tables_chinook_sql():
    """Verify get_tables('chinook') introspects SQLite schema and foreign keys."""
    data = get_tables("chinook")
    assert data["db_id"] == "chinook"
    assert data["type"] == "sql"
    assert len(data["tables"]) == 11
    assert len(data["relationships"]) > 0

    table_names = [t["name"] for t in data["tables"]]
    assert "Customer" in table_names
    assert "Invoice" in table_names

    customer_table = next(t for t in data["tables"] if t["name"] == "Customer")
    assert any("PK" in c for c in customer_table["cols"])
    assert any("CustomerId" in c["name"] for c in customer_table["columns"])


def test_get_tables_nosql():
    """Verify get_tables('ecommerce_store') introspects NoSQL collections."""
    data = get_tables("ecommerce_store")
    assert data["db_id"] == "ecommerce_store"
    assert data["type"] == "nosql"
    assert len(data["tables"]) >= 4

    col_names = [t["name"] for t in data["tables"]]
    assert "customers" in col_names or "products" in col_names
    assert len(data["relationships"]) >= 0


def test_get_tables_csv():
    """Verify get_tables('sales_performance') introspects CSV single sheet."""
    data = get_tables("sales_performance")
    assert data["type"] == "csv"
    assert len(data["tables"]) >= 1
    assert "columns" in data["tables"][0]


def test_get_tables_excel():
    """Verify get_tables('financial_budget') introspects Excel sheets."""
    data = get_tables("financial_budget")
    assert data["type"] == "excel"
    assert len(data["tables"]) >= 2
    sheet_names = [t["name"] for t in data["tables"]]
    assert "DepartmentBudget" in sheet_names or "ExpenseDetails" in sheet_names


def test_upload_missing_files_fails():
    """Verify upload_dataset without files raises HTTPException(400)."""
    with pytest.raises(HTTPException) as exc:
        upload_dataset(files=[], file=None, name="test_empty")
    assert exc.value.status_code == 400
    assert "At least one file is required" in str(exc.value.detail)


def test_merge_upload_requires_name():
    """Verify merge mode upload without display name raises HTTPException(400)."""
    mock_file = UploadFile(filename="test.sql", file=io.BytesIO(b"CREATE TABLE test (id INT);"))
    with pytest.raises(HTTPException) as exc:
        upload_dataset(files=[mock_file], name="   ", mode="merge", dataset_type="sql")
    assert exc.value.status_code == 400
    assert "Custom Display Name is required" in str(exc.value.detail)


def test_append_table_invalid_extension():
    """Verify appending non-sql file raises HTTPException(400)."""
    mock_file = UploadFile(filename="test.txt", file=io.BytesIO(b"dummy text"))
    with pytest.raises(HTTPException) as exc:
        append_table_script(db_id="chinook", file=mock_file)
    assert exc.value.status_code == 400
    assert "Only .sql table scripts" in str(exc.value.detail)


def test_append_collection_invalid_extension():
    """Verify appending non-json/bson file raises HTTPException(400)."""
    mock_file = UploadFile(filename="test.txt", file=io.BytesIO(b"dummy text"))
    with pytest.raises(HTTPException) as exc:
        append_collection_docs(db_id="ecommerce_store", file=mock_file)
    assert exc.value.status_code == 400
    assert "Only .json, .jsonl, or .bson" in str(exc.value.detail)


def test_delete_default_database_blocked():
    """Verify attempting to delete protected system datasets is blocked with 400."""
    with pytest.raises(HTTPException) as exc:
        delete_database(db_id="chinook")
    assert exc.value.status_code == 400
    assert "Cannot delete data source" in str(exc.value.detail)


def test_database_controller_adapter():
    """Verify backward-compatible DatabaseController adapter class."""
    dbs = DatabaseController.list_databases()
    assert "databases" in dbs
    schema = DatabaseController.get_tables_schema("chinook")
    assert schema["type"] == "sql"
    assert len(schema["tables"]) == 11
