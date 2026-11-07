"""
Database execution engines (SQL, NoSQL, and Spreadsheets).

Provides unified, pure functional interfaces to:
- Relational SQLite databases (.db, .sqlite, .sql)
- In-memory NoSQL document collections (.json, .jsonl, .bson)
- Spreadsheets and tabular workbooks (.csv, .xlsx, .xls)
"""

from engines.sql_engine import (
    compile_sql_scripts_to_db,
    execute_sql_query,
    format_schema_context,
    get_all_relationships,
    get_sql_schema,
    get_table_details,
    get_table_names,
    get_table_row_count,
    get_table_schema,
    resolve_sqlite_path,
)
from engines.nosql_engine import (
    compile_collections_to_dataset,
    execute_mql,
    format_nosql_schema_context,
    get_collection_documents,
    get_collection_names,
    get_nosql_schema,
    get_schema_fields,
    get_total_document_count,
    infer_nosql_relationships,
    load_nosql_collections,
    normalize_bson_doc,
    parse_collection_file,
    resolve_nosql_path,
)
from engines.spreadsheet_engine import (
    clean_records_for_json,
    excel_col_letter,
    execute_excel_formula,
    execute_pandas_code,
    execute_sql_on_spreadsheet,
    format_spreadsheet_schema_context,
    get_spreadsheet_schema,
    letter_to_col_index,
    load_spreadsheet,
    resolve_spreadsheet_path,
)

__all__ = [
    # SQL Engine
    "compile_sql_scripts_to_db",
    "execute_sql_query",
    "format_schema_context",
    "get_all_relationships",
    "get_sql_schema",
    "get_table_details",
    "get_table_names",
    "get_table_row_count",
    "get_table_schema",
    "resolve_sqlite_path",
    # NoSQL Engine
    "compile_collections_to_dataset",
    "execute_mql",
    "format_nosql_schema_context",
    "get_collection_documents",
    "get_collection_names",
    "get_nosql_schema",
    "get_schema_fields",
    "get_total_document_count",
    "infer_nosql_relationships",
    "load_nosql_collections",
    "normalize_bson_doc",
    "parse_collection_file",
    "resolve_nosql_path",
    # Spreadsheet Engine
    "clean_records_for_json",
    "excel_col_letter",
    "execute_excel_formula",
    "execute_pandas_code",
    "execute_sql_on_spreadsheet",
    "format_spreadsheet_schema_context",
    "get_spreadsheet_schema",
    "letter_to_col_index",
    "load_spreadsheet",
    "resolve_spreadsheet_path",
]
