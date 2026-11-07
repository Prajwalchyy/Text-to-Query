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
    assert customer_table.get("count") == 59


def test_get_tables_nosql():
    """Verify get_tables('ecommerce_store') introspects NoSQL collections."""
    data = get_tables("ecommerce_store")
    assert data["db_id"] == "ecommerce_store"
    assert data["type"] == "nosql"
    assert len(data["tables"]) >= 4

    col_names = [t["name"] for t in data["tables"]]
    assert "customers" in col_names or "products" in col_names
    assert len(data["relationships"]) >= 0
    assert all("count" in t and isinstance(t["count"], int) for t in data["tables"])


def test_get_tables_csv():
    """Verify get_tables('sales_performance') introspects CSV single sheet."""
    data = get_tables("sales_performance")
    assert data["type"] == "csv"
    assert len(data["tables"]) >= 1
    assert "columns" in data["tables"][0]
    assert data["tables"][0].get("count") == 12


def test_get_tables_excel():
    """Verify get_tables('financial_budget') introspects Excel sheets."""
    data = get_tables("financial_budget")
    assert data["type"] == "excel"
    assert len(data["tables"]) >= 1
    sheet_names = [t["name"] for t in data["tables"]]
    assert "DepartmentBudget" in sheet_names
    assert all("count" in t and isinstance(t["count"], int) for t in data["tables"])


def test_upload_missing_files_fails():
    """Verify upload_dataset without files raises HTTPException(400)."""
    with pytest.raises(HTTPException) as exc:
        upload_dataset(files=[], file=None, name="test_empty")
    assert exc.value.status_code == 400
    assert "required" in str(exc.value.detail).lower()


def test_merge_mode_rejected():
    """Verify merge mode upload is rejected with HTTPException(400)."""
    mock_file = UploadFile(filename="test.sql", file=io.BytesIO(b"CREATE TABLE test (id INT);"))
    with pytest.raises(HTTPException) as exc:
        upload_dataset(files=[mock_file], name="test", mode="merge", dataset_type="sql")
    assert exc.value.status_code == 400
    assert "Merge mode has been removed" in str(exc.value.detail)


def test_multiple_files_rejected():
    """Verify uploading multiple files is rejected with HTTPException(400)."""
    f1 = UploadFile(filename="test1.db", file=io.BytesIO(b""))
    f2 = UploadFile(filename="test2.db", file=io.BytesIO(b""))
    with pytest.raises(HTTPException) as exc:
        upload_dataset(files=[f1, f2], name="test")
    assert exc.value.status_code == 400
    assert "Multiple file upload has been removed" in str(exc.value.detail)


def test_upload_invalid_sql_extension():
    """Verify uploading non-sql file raises HTTPException(400)."""
    mock_file = UploadFile(filename="test.txt", file=io.BytesIO(b"dummy text"))
    with pytest.raises(HTTPException) as exc:
        upload_dataset(files=[mock_file], name="test", mode="full", dataset_type="sql")
    assert exc.value.status_code == 400
    assert "Invalid file type for SQL" in str(exc.value.detail)


def test_upload_invalid_nosql_extension():
    """Verify uploading non-json/bson file raises HTTPException(400)."""
    mock_file = UploadFile(filename="test.txt", file=io.BytesIO(b"dummy text"))
    with pytest.raises(HTTPException) as exc:
        upload_dataset(files=[mock_file], name="test", mode="full", dataset_type="nosql")
    assert exc.value.status_code == 400
    assert "Invalid file type for NoSQL" in str(exc.value.detail)


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
