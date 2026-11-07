"""
Relational SQLite Database Execution Engine.

Provides pure functional schema introspection, PRAGMA constraint analysis,
and safe query execution for SQLite relational databases (.db, .sqlite, .sql).

Zero OOP classes; 100% stateless functions with clean, typed inputs and outputs.
"""

import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import (
    BACKEND_DIR,
    DATA_DIR,
    DEFAULT_CHINOOK_PATH,
    DEFAULT_DATA_DIR,
    DEFAULT_DB_DIR,
    UPLOADS_DIR,
)


# ==============================================================================
# Path Resolution Helpers (Stateless)
# ==============================================================================
def resolve_sqlite_path(db_target: Optional[Path | str] = None) -> Path:
    """
    Resolves various representations of a database path (relative, absolute, or URI)
    into a canonical, existing Path object. Defaults to Chinook if None.
    """
    if db_target is None or db_target == "" or db_target == "chinook":
        return DEFAULT_CHINOOK_PATH.resolve()

    target_str = str(db_target).strip()
    if target_str.startswith("sqlite:///"):
        target_str = target_str.replace("sqlite:///", "")

    p = Path(target_str)
    if p.is_absolute() and p.exists():
        return p.resolve()

    filename = p.name
    if filename == DEFAULT_CHINOOK_PATH.name and DEFAULT_CHINOOK_PATH.exists():
        return DEFAULT_CHINOOK_PATH.resolve()

    search_bases = [
        DEFAULT_DATA_DIR,
        DEFAULT_DB_DIR,
        UPLOADS_DIR,
        UPLOADS_DIR / "db",
        UPLOADS_DIR / "sqlite",
        DATA_DIR,
        BACKEND_DIR,
    ]

    for base in search_bases:
        candidate_file = (base / filename).resolve()
        if candidate_file.exists():
            return candidate_file

    for base in search_bases:
        try:
            candidate = (base / target_str).resolve()
            if candidate.exists():
                return candidate
        except Exception:
            pass

    return p.resolve()


def _sanitize_value(val: Any) -> Any:
    """Normalizes database scalar types to JSON-serializable primitives."""
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, bytes):
        try:
            return val.decode("utf-8")
        except UnicodeDecodeError:
            return val.hex()
    return val


# ==============================================================================
# Schema Introspection (Pure Functions)
# ==============================================================================
def get_table_names(db_path: Optional[Path | str] = None) -> List[str]:
    """
    Returns the list of all user-defined table names in the SQLite database,
    excluding internal SQLite system tables.
    """
    path = resolve_sqlite_path(db_path)
    if not path.exists():
        return []

    conn = sqlite3.connect(str(path))
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_table_schema(db_path: Optional[Path | str], table_name: str) -> List[Dict[str, Any]]:
    """
    Introspects columns for a specific table via PRAGMA table_info.
    Returns list of dicts with name, type, nullable, default, and primary_key.
    Matches legacy F01 / SQLAlchemy column mapping.
    """
    path = resolve_sqlite_path(db_path)
    if not path.exists():
        return []

    conn = sqlite3.connect(str(path))
    try:
        cursor = conn.cursor()
        cursor.execute(f'PRAGMA table_info("{table_name}");')
        columns: List[Dict[str, Any]] = []
        for row in cursor.fetchall():
            # row: (cid, name, type, notnull, dflt_value, pk)
            columns.append({
                "name": row[1],
                "type": row[2] or "TEXT",
                "nullable": bool(row[3] == 0),
                "default": row[4],
                "primary_key": bool(row[5] > 0)
            })
        return columns
    finally:
        conn.close()


def get_table_details(
    db_path: Optional[Path | str],
    table_name: str
) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
    """
    Returns a 3-tuple: (columns, primary_keys, foreign_keys) for a given table.
    - columns: List[Dict] with column definitions
    - primary_keys: List[str] of primary key column names
    - foreign_keys: List[Dict] with constrained_columns, referred_table, referred_columns
    """
    path = resolve_sqlite_path(db_path)
    if not path.exists():
        return [], [], []

    conn = sqlite3.connect(str(path))
    try:
        cursor = conn.cursor()
        cursor.execute(f'PRAGMA table_info("{table_name}");')
        columns: List[Dict[str, Any]] = []
        primary_keys: List[str] = []
        for row in cursor.fetchall():
            col_info = {
                "name": row[1],
                "type": row[2] or "TEXT",
                "nullable": bool(row[3] == 0),
                "default": row[4],
                "primary_key": bool(row[5] > 0)
            }
            columns.append(col_info)
            if row[5] > 0:
                primary_keys.append(row[1])

        cursor.execute(f'PRAGMA foreign_key_list("{table_name}");')
        foreign_keys: List[Dict[str, Any]] = []
        for row in cursor.fetchall():
            # row: (id, seq, table, from, to, on_update, on_delete, match)
            foreign_keys.append({
                "constrained_columns": [row[3]],
                "referred_table": row[2],
                "referred_columns": [row[4]]
            })

        return columns, primary_keys, foreign_keys
    finally:
        conn.close()


def get_table_row_count(db_path: Optional[Path | str], table_name: str) -> int:
    """
    Returns the total row count for a given SQLite table.
    Safely escapes the table name.
    """
    path = resolve_sqlite_path(db_path)
    if not path.exists():
        return 0

    conn = sqlite3.connect(str(path))
    try:
        cursor = conn.cursor()
        safe_name = table_name.replace('"', '""')
        cursor.execute(f'SELECT COUNT(*) FROM "{safe_name}";')
        row = cursor.fetchone()
        return row[0] if row else 0
    except Exception:
        return 0
    finally:
        conn.close()


def get_all_relationships(db_path: Optional[Path | str] = None) -> List[Dict[str, str]]:
    """
    Introspects and returns all foreign key relationships across the entire database.
    Format: [{"from_table": ..., "from_col": ..., "to_table": ..., "to_col": ...}]
    """
    path = resolve_sqlite_path(db_path)
    if not path.exists():
        return []

    tables = get_table_names(path)
    relationships: List[Dict[str, str]] = []

    conn = sqlite3.connect(str(path))
    try:
        cursor = conn.cursor()
        for table in tables:
            cursor.execute(f'PRAGMA foreign_key_list("{table}");')
            for row in cursor.fetchall():
                relationships.append({
                    "from_table": table,
                    "from_col": row[3],
                    "to_table": row[2],
                    "to_col": row[4]
                })
        return relationships
    finally:
        conn.close()


def get_sql_schema(db_path: Optional[Path | str] = None) -> Dict[str, Any]:
    """
    Returns a comprehensive structured schema catalog:
    {
        "database": str,
        "path": str,
        "tables": {table_name: {"columns": [...], "primary_keys": [...], "foreign_keys": [...]}},
        "relationships": [...]
    }
    """
    path = resolve_sqlite_path(db_path)
    tables = get_table_names(path)
    schema: Dict[str, Any] = {
        "database": path.name,
        "path": str(path),
        "tables": {},
        "relationships": get_all_relationships(path)
    }

    for table in tables:
        cols, pks, fks = get_table_details(path, table)
        schema["tables"][table] = {
            "columns": cols,
            "primary_keys": pks,
            "foreign_keys": fks
        }

    return schema


def format_schema_context(db_path: Optional[Path | str] = None) -> str:
    """
    Generates a clean, readable text representation of the database schema,
    including table names, columns, data types, and foreign key relationships,
    formatted specifically for feeding as prompt context to the LLM.
    """
    path = resolve_sqlite_path(db_path)
    tables = get_table_names(path)
    rels = get_all_relationships(path)
    schema_lines: List[str] = []

    for table in tables:
        cols, _, _ = get_table_details(path, table)
        col_string = ", ".join(f"{col['name']} {col['type']}" for col in cols)
        lines = [f"Table: {table}", f"Columns: {col_string}"]

        # Include foreign key relationships originating from this table
        table_fks = [r for r in rels if r["from_table"] == table]
        if table_fks:
            fk_string = ", ".join(f"{fk['from_col']} -> {fk['to_table']}.{fk['to_col']}" for fk in table_fks)
            lines.append(f"Foreign Keys: {fk_string}")

        schema_lines.append("\n".join(lines))

    return "\n\n".join(schema_lines)


# ==============================================================================
# Query Execution (Stateless)
# ==============================================================================
def execute_sql_query(
    sql_query: str,
    db_path: Optional[Path | str] = None,
    max_rows: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Executes a read-only SQL query against the target SQLite database.
    Returns rows as a list of column-mapped dictionaries.
    
    Attempts opening in read-only URI mode (mode=ro) to enforce zero mutation.
    """
    path = resolve_sqlite_path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"Database file not found: {path}")

    # Enforce read-only mode if possible
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    except Exception:
        conn = sqlite3.connect(str(path))

    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(sql_query)

        if cursor.description is None:
            return []

        if max_rows is not None and max_rows > 0:
            rows = cursor.fetchmany(max_rows)
        else:
            rows = cursor.fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            results.append({k: _sanitize_value(row[k]) for k in row.keys()})
        return results
    finally:
        conn.close()


# ==============================================================================
# Compilation / Script Assembly
# ==============================================================================
def compile_sql_scripts_to_db(
    sql_scripts: List[Tuple[str, str]],
    target_db_path: Path | str
) -> List[str]:
    """
    Compiles a series of raw .sql script tuples (script_name, sql_content)
    into a unified SQLite database file at target_db_path.
    Returns the list of tables created.
    """
    target = Path(target_db_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        target.unlink()

    conn = sqlite3.connect(str(target))
    try:
        cursor = conn.cursor()
        for _, script_content in sql_scripts:
            cursor.executescript(script_content)
        conn.commit()
    finally:
        conn.close()

    return get_table_names(target)


# Backward-compatible function aliases
execute_query = execute_sql_query
get_schema_context = format_schema_context

