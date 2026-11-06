"""
Unit Tests for Centralized Prompt Catalog (Step C.5).
Verifies build_sql_prompt, build_nosql_prompt, build_spreadsheet_prompt,
build_repair_prompt, format_history_context, and parse_generator_output.
"""

import json
import pytest
from backend.src.pipelines.prompts import (
    build_sql_prompt,
    build_nosql_prompt,
    build_spreadsheet_prompt,
    build_repair_prompt,
    format_history_context,
    parse_generator_output,
    SQL_SYSTEM_PROMPT_TEMPLATE,
    NOSQL_SYSTEM_PROMPT_TEMPLATE,
    SPREADSHEET_CSV_SYSTEM_PROMPT_TEMPLATE,
    SPREADSHEET_EXCEL_SYSTEM_PROMPT_TEMPLATE,
)


def test_build_sql_prompt_without_history():
    question = "List top 5 customers by invoice spending"
    schema = "Table: Customer\nColumns: CustomerId INTEGER, Total NUMERIC"
    sys_prompt, user_content = build_sql_prompt(question, schema)

    assert "You are an expert SQL Database Engineer" in sys_prompt
    assert "Table: Customer" in sys_prompt
    assert user_content == question
    assert "PREVIOUS CONVERSATION CONTEXT" not in user_content


def test_build_sql_prompt_with_history():
    question = "Now show only those from Canada"
    schema = "Table: Customer\nColumns: CustomerId INTEGER, Country TEXT"
    history = [
        {"role": "user", "content": "List top 5 customers"},
        {"role": "assistant", "sql": "SELECT * FROM Customer ORDER BY Total DESC LIMIT 5;", "content": "Here are 5 customers."}
    ]
    sys_prompt, user_content = build_sql_prompt(question, schema, history=history)

    assert "Table: Customer" in sys_prompt
    assert "PREVIOUS CONVERSATION CONTEXT" in user_content
    assert 'User asked: "List top 5 customers"' in user_content
    assert 'Generated SQL: SELECT * FROM Customer ORDER BY Total DESC LIMIT 5;' in user_content
    assert 'Answer Summary: Here are 5 customers.' in user_content
    assert f'CURRENT QUESTION TO ANSWER:\n"{question}"' in user_content


def test_build_nosql_prompt_with_collections_and_history():
    question = "Find all delivered orders"
    schema = "Collection: orders\nFields: order_id: str, status: str"
    cols = ["orders", "customers", "products"]
    history = [{"role": "user", "content": "How many orders total?"}]

    sys_prompt, user_content = build_nosql_prompt(
        question, schema, history=history, collection_names=cols
    )

    assert "orders, customers, products" in sys_prompt
    assert "Collection: orders" in sys_prompt
    assert "PREVIOUS CONVERSATION CONTEXT" in user_content
    assert 'User asked: "How many orders total?"' in user_content
    assert f'CURRENT QUESTION TO ANSWER:\n"{question}"' in user_content


def test_build_spreadsheet_prompt_csv_vs_excel():
    schema = "Columns: Department (object), Budget (int64)"
    q = "What is total budget for Marketing?"

    # CSV mode
    sys_csv, user_csv = build_spreadsheet_prompt(q, schema, file_type="csv")
    assert "Senior Python Data Analyst and Pandas Expert" in sys_csv
    assert "result_df" in sys_csv
    assert user_csv == q

    # Excel mode
    sys_excel, user_excel = build_spreadsheet_prompt(q, schema, file_type="excel")
    assert "Microsoft Excel Specialist and Spreadsheet Architect" in sys_excel
    assert "=SUMIFS" in sys_excel
    assert user_excel == q


def test_build_repair_prompt_dialects():
    q = "Count customers"
    schema = "Table: Customer"
    err = "no such column: NonExistent"

    # SQL dialect
    sys_sql, user_sql = build_repair_prompt(q, "SELECT NonExistent FROM Customer", err, schema, dialect="sql")
    assert "expert SQL Database Engineer" in sys_sql
    assert "Failed SQL Query" in user_sql
    assert "no such column: NonExistent" in user_sql

    # NoSQL dialect
    sys_mql, user_mql = build_repair_prompt(q, "db.cust.find()", "Unknown collection 'cust'", schema, dialect="nosql")
    assert "expert MongoDB" in sys_mql
    assert "Failed MQL Query" in user_mql

    # Pandas dialect
    sys_pd, user_pd = build_repair_prompt(q, "result_df = df['bad_col']", "KeyError: 'bad_col'", schema, dialect="pandas")
    assert "expert Data Engineer" in sys_pd
    assert "Failed Pandas Code" in user_pd

    # Excel dialect
    sys_xl, user_xl = build_repair_prompt(q, "=SUM(Z1:Z10)", "Invalid range Z1:Z10", schema, dialect="excel")
    assert "expert Microsoft Excel" in sys_xl
    assert "Failed Excel Formula" in user_xl


def test_format_history_context_edge_cases():
    assert format_history_context(None) == ""
    assert format_history_context([]) == ""
    assert format_history_context("") == ""

    # Pre-formatted string
    raw_str = "PREVIOUS CONVERSATION CONTEXT:\nUser asked: hello"
    assert format_history_context(raw_str) == raw_str

    # Plain string
    assert "PREVIOUS CONVERSATION CONTEXT" in format_history_context("User asked: something")

    # List with various query types
    hist = [
        {"role": "user", "content": "Show sales"},
        {"role": "assistant", "code": "result_df = df.head()", "summary": "Top 5 rows"},
        {"role": "user", "content": "Now filter revenue > 100"},
        {"role": "assistant", "formula": "=FILTER(A2:B10, B2:B10>100)"}
    ]
    res = format_history_context(hist, query_label="Code")
    assert 'User asked: "Show sales"' in res
    assert "Generated Code: result_df = df.head()" in res
    assert "Answer Summary: Top 5 rows" in res
    assert "Generated Code: =FILTER(A2:B10, B2:B10>100)" in res


def test_parse_generator_output_json_single():
    raw_json = json.dumps({
        "title": "Top Customers",
        "sql": "SELECT * FROM Customer LIMIT 10;"
    })
    tasks = parse_generator_output(raw_json)
    assert isinstance(tasks, list)
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Top Customers"
    assert tasks[0]["sql"] == "SELECT * FROM Customer LIMIT 10;"


def test_parse_generator_output_markdown_fences():
    fenced = """```json
    {
      "title": "Delivered Orders",
      "mql": "db.orders.find({\\"status\\": \\"delivered\\"})"
    }
    ```"""
    tasks = parse_generator_output(fenced)
    assert isinstance(tasks, list)
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Delivered Orders"
    assert 'db.orders.find' in tasks[0]["mql"]


def test_parse_generator_output_compound_array():
    compound_json = json.dumps([
        {"title": "1. All Customers", "sql": "SELECT * FROM Customer;"},
        {"title": "2. All Invoices", "sql": "SELECT * FROM Invoice;"}
    ])
    tasks = parse_generator_output(compound_json)
    assert isinstance(tasks, list)
    assert len(tasks) == 2
    assert tasks[0]["title"] == "1. All Customers"
    assert tasks[1]["title"] == "2. All Invoices"


def test_parse_generator_output_out_of_domain():
    ood_json = json.dumps({
        "is_relevant": False,
        "reason": "This database does not contain patient medical records.",
        "needed_tables": ["Patients", "MedicalRecords"],
        "suggested_questions": ["What music tracks are available?", "List top artists."]
    })
    res = parse_generator_output(ood_json)
    assert isinstance(res, dict)
    assert res["is_relevant"] is False
    assert len(res["needed_tables"]) == 2
    assert len(res["suggested_questions"]) == 2


def test_parse_generator_output_raw_fallbacks():
    # Raw SQL fallback
    raw_sql = "SELECT TrackId, Name FROM Track LIMIT 5;"
    t1 = parse_generator_output(raw_sql)
    assert t1[0]["sql"] == raw_sql

    # Raw MQL fallback
    raw_mql = "db.products.find({price: {$gt: 100}})"
    t2 = parse_generator_output(raw_mql)
    assert t2[0]["mql"] == raw_mql

    # Raw Pandas fallback
    raw_pd = "result_df = df[df['Age'] > 30]"
    t3 = parse_generator_output(raw_pd)
    assert t3[0]["code"] == raw_pd

    # Raw Excel formula fallback
    raw_xl = "=SUMIFS(C2:C10, A2:A10, \"East\")"
    t4 = parse_generator_output(raw_xl)
    assert t4[0]["formula"] == raw_xl

