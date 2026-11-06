"""
SQL Security Guardrail (Stateless Pure Functional).

Implements 4-layer defense-in-depth protection for SQLite query execution:
  Layer 1: Destructive DDL/DML keyword blocker (15 forbidden keywords).
  Layer 2: AST syntax validation & single-statement enforcement (sqlglot).
  Layer 3: Root expression restriction (strictly exp.Select or exp.Union).
  Layer 4: Schema table allowlisting with CTE (WITH ...) alias detection.

Zero-state pure functional architecture replacing legacy backend/src/F03_guardrails.py.
"""

import re
from typing import Iterable, NamedTuple, Optional, Set, Tuple
import sqlglot
from sqlglot import expressions as exp


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
    Master Guardrail: Runs incoming SQL through all 4 security layers.
    
    Returns:
        SQLValidationResult(is_valid: bool, error: Optional[str], sanitized_sql: str)
        Can be unpacked as 3 items: `is_valid, reason, sanitized_sql = validate_sql(...)`.
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
