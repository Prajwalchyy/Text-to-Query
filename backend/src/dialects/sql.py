"""
Unified Relational SQLite Dialect.

Combines pure functional SQL validation guardrails, schema introspection,
PRAGMA constraint analysis, and safe query execution for SQLite databases (.db, .sqlite, .sql).
"""

import re
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Set, Tuple

import sqlglot
from sqlglot import expressions as exp

from config import (
    BACKEND_DIR,
    DATA_DIR,
    DEFAULT_CHINOOK_PATH,
    DEFAULT_DATA_DIR,
    DEFAULT_DB_DIR,
    UPLOADS_DIR,
)

# Shared Base Foundation
try:
    from dialects.base import (
        ValidationResult,
        resolve_dataset_file,
        sanitize_records_for_json,
        sanitize_scalar,
    )
except ImportError:
    from src.dialects.base import (
        ValidationResult,
        resolve_dataset_file,
        sanitize_records_for_json,
        sanitize_scalar,
    )


# ==============================================================================
# 1. SQL Security Guardrails (Stateless Pure Functional)
# ==============================================================================
FORBIDDEN_SQL_KEYWORDS: Set[str] = {
    "DROP",
    "DELETE",
    "UPDATE",
    "INSERT",
    "ALTER",
    "TRUNCATE",
    "REPLACE",
    "CREATE",
    "GRANT",
    "REVOKE",
    "EXEC",
    "EXECUTE",
    "SHUTDOWN",
    "ATTACH",
    "DETACH",
}


class SQLValidationResult(NamedTuple):
    """Immutable validation result for SQL queries."""

    is_valid: bool
    reason: Optional[str]
    sanitized_sql: str

    @property
    def error(self) -> Optional[str]:
        """Returns error message if invalid, or None if valid."""
        return None if self.is_valid else self.reason


def check_keyword_not_allowed(
    sql: str,
    forbidden_keywords: Optional[Set[str]] = None,
) -> Optional[str]:
    """
    Layer 1: Scans SQL for destructive keywords using regex word boundaries.
    
    Replaces string literals with empty strings first to prevent false positives
    on literal values (e.g. WHERE title = 'Drop the beat').
    Returns an error message if a forbidden word is detected, otherwise None.
    """
    forbidden = forbidden_keywords or FORBIDDEN_SQL_KEYWORDS
    # Strip string literals ('...' or "...") to avoid false positives on literal values
    stripped_sql = re.sub(r"'(?:''|[^'])*'", "''", sql)
    stripped_sql = re.sub(r'"(?:""|[^"])*"', '""', stripped_sql)

    pattern = r"\b(" + "|".join(sorted(forbidden, key=len, reverse=True)) + r")\b"
    match = re.search(pattern, stripped_sql, re.IGNORECASE)

    if match:
        forbidden_word = match.group(1).upper()
        return f"Security Violation: Forbidden keyword '{forbidden_word}' detected."

    return None


def check_ast_and_multi_query(
    sql: str,
    dialect: str = "sqlite",
) -> Tuple[Optional[exp.Expression], Optional[str]]:
    """
    Layers 2 & 3: Parses SQL with sqlglot into an Abstract Syntax Tree (AST).
    
    - Blocks multi-query chained attacks (e.g. 'SELECT 1; DROP TABLE users;').
    - Verifies that the root expression is strictly a SELECT or UNION statement.
    Returns: (parsed_expression, error_message)
    """
    try:
        parsed_statements = sqlglot.parse(sql, read=dialect)
    except Exception as e:
        return None, f"SQL Syntax Error: Unable to parse query ({str(e)})"

    # Layer 3: Block multiple / chained queries
    if len(parsed_statements) > 1:
        return None, "Security Violation: Multi-statement / chained queries are forbidden."

    if not parsed_statements or parsed_statements[0] is None:
        return None, "SQL Error: Empty query provided."

    statement = parsed_statements[0]

    # Layer 2: Must be strictly a SELECT or UNION expression
    if not isinstance(statement, (exp.Select, exp.Union)):
        return None, f"Security Violation: Only SELECT/UNION queries are permitted (got {type(statement).__name__})."

    return statement, None


def check_table_allowlist(
    statement: exp.Expression,
    allowed_tables: Optional[Iterable[str]] = None,
) -> Optional[str]:
    """
    Layer 4: Extracts all table names from parsed AST and ensures they exist
    in the database schema allowlist.
    
    Automatically recognizes and permits local CTE (WITH ...) aliases so subquery
    references are not falsely flagged.
    """
    if allowed_tables is None:
        return None

    allowed_set = {t.strip().lower() for t in allowed_tables if t and t.strip()}
    if not allowed_set:
        return None

    # Detect CTE aliases (e.g. WITH my_cte AS (...) SELECT * FROM my_cte)
    cte_names = {
        cte.alias.lower()
        for cte in statement.find_all(exp.CTE)
        if cte.alias
    }

    for table_node in statement.find_all(exp.Table):
        table_name = table_node.name.strip().lower()
        if not table_name:
            continue
        if table_name in cte_names:
            continue
        if table_name not in allowed_set:
            return f"Schema Violation: Table '{table_node.name}' does not exist in database allowlist."

    return None


def validate_sql(
    raw_sql: str,
    allowed_tables: Optional[Iterable[str]] = None,
    dialect: str = "sqlite",
) -> SQLValidationResult:
    """
    Master SQL Guardrail: Runs incoming SQL through all 4 security layers.
    
    Returns:
        SQLValidationResult(is_valid: bool, reason: Optional[str], sanitized_sql: str)
    """
    sql = raw_sql.strip() if raw_sql else ""
    if not sql:
        return SQLValidationResult(False, "SQL Error: Empty query provided.", "")

    # Normalize trailing semicolon for clean processing
    if sql.endswith(";"):
        sql = sql[:-1].strip()

    # Layer 1: Keyword Denylist
    keyword_error = check_keyword_not_allowed(sql)
    if keyword_error:
        return SQLValidationResult(False, keyword_error, "")

    # Layers 2 & 3: AST & Multi-Query Blocker
    statement, ast_error = check_ast_and_multi_query(sql, dialect=dialect)
    if ast_error:
        return SQLValidationResult(False, ast_error, "")

    # Layer 4: Schema Allowlist
    allowlist_error = check_table_allowlist(statement, allowed_tables)
    if allowlist_error:
        return SQLValidationResult(False, allowlist_error, "")

    # All 4 layers passed successfully
    sanitized_sql = sql + ";"
    return SQLValidationResult(True, "Passed all security guardrails.", sanitized_sql)


class SQLInjectionGuardrail:
    """
    Backward-compatible adapter matching legacy F03_guardrails.SQLInjectionGuardrail.
    Delegates all checks directly to pure functions.
    """

    FORBIDDEN_KEYWORDS = FORBIDDEN_SQL_KEYWORDS

    def __init__(
        self,
        db_engine: Optional[object] = None,
        allowed_tables: Optional[Iterable[str]] = None,
    ):
        if allowed_tables is not None:
            self.allowed_tables = {t.lower() for t in allowed_tables}
        elif db_engine is not None and hasattr(db_engine, "get_table_names"):
            self.allowed_tables = {t.lower() for t in db_engine.get_table_names()}
        else:
            self.allowed_tables = None

    def check_keyword_not_allowed(self, sql: str) -> Optional[str]:
        return check_keyword_not_allowed(sql, self.FORBIDDEN_KEYWORDS)

    def check_ast_and_multi_query(self, sql: str):
        return check_ast_and_multi_query(sql)

    def check_table_allowlist(self, statement: exp.Expression) -> Optional[str]:
        return check_table_allowlist(statement, self.allowed_tables)

    def validate_sql(self, raw_sql: str):
        return validate_sql(raw_sql, allowed_tables=self.allowed_tables)


# ==============================================================================
# 2. Path Resolution & Introspection (Stateless Pure Functions)
# ==============================================================================
def resolve_sqlite_path(db_target: Optional[Path | str] = None) -> Path:
    """
    Resolves various representations of a database path (relative, absolute, or URI)
    into a canonical, existing Path object. Defaults to Chinook if None.
    """
    return resolve_dataset_file(
        target_path=db_target,
        default_path=DEFAULT_CHINOOK_PATH,
        search_directories=[
            DEFAULT_DATA_DIR,
            DEFAULT_DB_DIR,
            UPLOADS_DIR,
            UPLOADS_DIR / "db",
            UPLOADS_DIR / "sqlite",
            DATA_DIR,
            BACKEND_DIR,
        ],
        default_alias_names=["chinook"],
    )


# Backward-compatible alias for universal scalar normalizer
_sanitize_value = sanitize_scalar


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
    Returns a comprehensive structured schema catalog.
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
# 3. Query Execution (Stateless Pure Function)
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

        results = [dict(row) for row in rows]
        return sanitize_records_for_json(results)
    finally:
        conn.close()


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

