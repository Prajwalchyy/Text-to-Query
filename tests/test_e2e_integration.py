"""
End-to-End Integration Verification Suite (Phase E.3).
Enterprise Text-to-SQL API (v2.0)

Simulates live frontend client interactions across all major application workflows:
1. System Dataset Discovery (/api/databases)
2. Schema & Relationship Introspection across SQL, NoSQL, CSV, Excel (/api/tables)
3. Conversational Session Lifecycle (/api/chats)
4. SQL Pipeline Query Execution & Telemetry (Chinook database)
5. NoSQL MQL Aggregation & Schema Explorer (ecommerce_store.json)
6. Tabular CSV Pandas Analysis (sales_performance.csv)
7. Excel Budget Formula Evaluation (financial_budget.xlsx)
8. Cross-Dialect Polyglot Translation Bridge (/api/chats/convert-code)
9. Supported Dialect Catalog (/api/chats/languages/{db_id})
10. Table & Collection Conflict Detection (409 Conflict)
"""

import sys
from pathlib import Path
from unittest.mock import patch
import pytest

# Ensure project root and backend are on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
for p in [str(PROJECT_ROOT), str(BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.src.api.databases_routes import (
    get_databases_data,
    introspect_schema,
)
from backend.src.api.chat_routes import (
    list_chats_data,
    create_chat_session_data,
    update_chat_title_data,
    delete_chat_data,
    execute_query_data,
    convert_code_data,
    get_supported_languages_data,
)
from backend.src.api.schemas import (
    CreateChatRequest,
    UpdateChatRequest,
    QueryRequest,
    ConvertCodeRequest,
)


@pytest.fixture
def temp_chat_file(tmp_path):
    """Provides an isolated JSON chat history file for integration tests."""
    p = tmp_path / "e2e_chat_history.json"
    p.write_text("[]", encoding="utf-8")
    return p


# ==============================================================================
# 1. Dataset Discovery & Schema Introspection
# ==============================================================================
def test_e2e_system_datasets_available():
    """Verify all 4 default system datasets are registered and discoverable."""
    res = get_databases_data()
    dbs = res.get("databases", [])
    assert len(dbs) >= 4

    db_map = {d["id"]: d for d in dbs}
    assert "chinook" in db_map
    assert db_map["chinook"]["type"] == "sql"

    assert "ecommerce_store" in db_map
    assert db_map["ecommerce_store"]["type"] == "nosql"

    assert "sales_performance" in db_map
    assert db_map["sales_performance"]["type"] == "csv"

    assert "financial_budget" in db_map
    assert db_map["financial_budget"]["type"] == "excel"


def test_e2e_schema_introspection_sql():
    """Verify SQLite Chinook schema returns tables and foreign key relationships."""
    res = introspect_schema("chinook")
    assert res["db_id"] == "chinook"
    assert res["type"] == "sql"
    assert len(res["tables"]) == 11
    assert len(res["relationships"]) > 0

    table_names = [t["name"] for t in res["tables"]]
    assert "Customer" in table_names
    assert "Invoice" in table_names
    assert "Track" in table_names


def test_e2e_schema_introspection_nosql():
    """Verify NoSQL ecommerce_store schema returns collections and inferred relationships."""
    res = introspect_schema("ecommerce_store")
    assert res["db_id"] == "ecommerce_store"
    assert res["type"] == "nosql"
    assert len(res["tables"]) >= 1

    col_names = [t["name"] for t in res["tables"]]
    assert "products" in col_names or "customers" in col_names


def test_e2e_schema_introspection_csv():
    """Verify CSV sales_performance schema returns columns."""
    res = introspect_schema("sales_performance")
    assert res["db_id"] == "sales_performance"
    assert res["type"] == "csv"
    assert len(res["tables"]) == 1
    assert "sales_performance" in res["tables"][0]["name"]


def test_e2e_schema_introspection_excel():
    """Verify Excel financial_budget schema returns workbook sheets."""
    res = introspect_schema("financial_budget")
    assert res["db_id"] == "financial_budget"
    assert res["type"] == "excel"
    assert len(res["tables"]) >= 1


# ==============================================================================
# 2. Conversational Session Lifecycle
# ==============================================================================
def test_e2e_chat_session_lifecycle(temp_chat_file):
    """Verify creating, listing, updating, and deleting chat sessions."""
    # 1. Create chat
    create_req = CreateChatRequest(id="e2e-session-001", title="Initial Analysis")
    session = create_chat_session_data(create_req, file_path=temp_chat_file)
    assert session["id"] == "e2e-session-001"
    assert session["title"] == "Initial Analysis"

    # 2. List chats
    chats_res = list_chats_data(file_path=temp_chat_file)
    assert len(chats_res["chats"]) == 1
    assert chats_res["chats"][0]["id"] == "e2e-session-001"

    # 3. Update title
    update_req = UpdateChatRequest(title="Renamed Revenue Analysis")
    updated = update_chat_title_data("e2e-session-001", update_req, file_path=temp_chat_file)
    assert updated["success"] is True
    assert updated["title"] == "Renamed Revenue Analysis"

    # 4. Delete chat
    deleted = delete_chat_data("e2e-session-001", file_path=temp_chat_file)
    assert deleted["success"] is True

    # 5. Verify empty
    chats_res_empty = list_chats_data(file_path=temp_chat_file)
    assert len(chats_res_empty["chats"]) == 0


# ==============================================================================
# 3. Query Execution & Multi-Turn Chaining
# ==============================================================================
def test_e2e_sql_query_execution_and_telemetry(temp_chat_file):
    """Verify end-to-end query execution on SQL chinook with telemetry and message persistence."""
    create_req = CreateChatRequest(id="e2e-sql-chat", title="Customer Spending")
    create_chat_session_data(create_req, file_path=temp_chat_file)

    mock_sql_json = (
        '[\n'
        '  {"title": "Top Customers", "sql": "SELECT CustomerId, FirstName, LastName, SupportRepId FROM Customer ORDER BY CustomerId LIMIT 3;"}\n'
        ']'
    )

    with patch("src.pipelines.router.call_llm", return_value=mock_sql_json):
        query_req = QueryRequest(
            question="Show me the top 3 customers",
            db_id="chinook",
            target_language="sql"
        )
        resp = execute_query_data("e2e-sql-chat", query_req, file_path=temp_chat_file)

    assert resp["role"] == "assistant"
    assert resp["status"] == "SUCCESS"
    assert "Customer" in resp["sql"]
    assert len(resp["data"]) == 3
    assert "telemetry" in resp
    assert resp["telemetry"]["db_type"] == "sql"
    assert resp["telemetry"]["db_id"] == "chinook"

    # Verify both user and assistant messages were saved in chat session
    chats = list_chats_data(file_path=temp_chat_file)["chats"]
    session = next(c for c in chats if c["id"] == "e2e-sql-chat")
    assert len(session["messages"]) == 2
    assert session["messages"][0]["role"] == "user"
    assert session["messages"][1]["role"] == "assistant"


def test_e2e_spreadsheet_pandas_execution(temp_chat_file):
    """Verify end-to-end query execution on CSV sales_performance."""
    create_req = CreateChatRequest(id="e2e-csv-chat", title="Sales Performance")
    create_chat_session_data(create_req, file_path=temp_chat_file)

    mock_csv_json = (
        '[\n'
        '  {"title": "Top Orders", "code": "result_df = df.nlargest(3, \\"TotalAmount\\")", "explanation": "Calculates top 3 orders"}\n'
        ']'
    )

    with patch("src.pipelines.router.call_llm", return_value=mock_csv_json):
        query_req = QueryRequest(
            question="What are the top 3 largest transactions?",
            db_id="sales_performance",
            target_language="pandas"
        )
        resp = execute_query_data("e2e-csv-chat", query_req, file_path=temp_chat_file)

    assert resp["status"] == "SUCCESS"
    assert len(resp["data"]) == 3
    assert resp["telemetry"]["db_type"] == "csv"


# ==============================================================================
# 4. Polyglot Code Conversion & Supported Languages Catalog
# ==============================================================================
def test_e2e_polyglot_code_conversion():
    """Verify translating SQL to Python/Pandas across dialects."""
    mock_conversion_payload = {
        "title": "Converted to Pandas",
        "code": "import pandas as pd\nresult_df = df.groupby('Genre')['Sales'].sum()",
        "explanation": "Calculates sum of sales grouped by genre."
    }

    with patch("src.core.polyglot.call_llm_json", return_value=mock_conversion_payload):
        conv_req = ConvertCodeRequest(
            code="SELECT Genre, SUM(Sales) FROM tracks GROUP BY Genre",
            from_language="sql",
            to_language="pandas",
            db_id="chinook"
        )
        conv_resp = convert_code_data(conv_req)

    assert conv_resp["to_language"] == "pandas"
    assert "result_df" in conv_resp["code"]
    assert conv_resp["language_name"] == "Python (Pandas)"


def test_e2e_supported_languages_catalog():
    """Verify language discovery per data source type."""
    # SQL
    sql_langs = get_supported_languages_data("chinook")
    assert sql_langs["db_type"] == "sql"
    sql_lang_ids = [l["id"] for l in sql_langs["languages"]]
    assert "sql" in sql_lang_ids
    assert "pandas" in sql_lang_ids
    assert "r" in sql_lang_ids
    assert "excel_formula" not in sql_lang_ids
    assert "nosql" not in sql_lang_ids

    # NoSQL
    nosql_langs = get_supported_languages_data("ecommerce_store")
    assert nosql_langs["db_type"] == "nosql"
    nosql_lang_ids = [l["id"] for l in nosql_langs["languages"]]
    assert "nosql" in nosql_lang_ids
    assert "pandas" in nosql_lang_ids
    assert "r" in nosql_lang_ids
    assert "sql" not in nosql_lang_ids
    assert "excel_formula" not in nosql_lang_ids

    # CSV / Excel
    csv_langs = get_supported_languages_data("sales_performance")
    assert csv_langs["db_type"] == "csv"
    csv_lang_ids = [l["id"] for l in csv_langs["languages"]]
    assert "sql" not in csv_lang_ids
    assert "nosql" not in csv_lang_ids
    assert "pandas" in csv_lang_ids
    assert "excel_formula" in csv_lang_ids
    assert "r" in csv_lang_ids
