"""
Guardrails package entrypoint for OmniData AI.

Provides stateless pure functional security validators across:
  - SQL: sqlglot AST parsing, keyword blocker, table allowlisting, CTE alias detection.
  - NoSQL: MQL destructive operator blocking, collection resolution, pipeline parsing.
  - Pandas: Python AST NodeVisitor sandbox, call/module restriction, result_df enforcement.
"""

from .sql_guard import (
    FORBIDDEN_SQL_KEYWORDS,
    SQLValidationResult,
    check_keyword_not_allowed,
    check_ast_and_multi_query,
    check_table_allowlist,
    validate_sql,
    SQLInjectionGuardrail,
)

from .nosql_guard import (
    FORBIDDEN_NOSQL_OPERATORS,
    NoSQLValidationResult,
    check_forbidden_nosql_operators,
    extract_collection_name,
    repair_mql_json_string,
    validate_mql,
    validate_and_parse,
    NoSQLGuardrail,
)

from .pandas_guard import (
    FORBIDDEN_PANDAS_CALLS,
    FORBIDDEN_PANDAS_MODULES,
    PandasSecurityViolation,
    PandasValidationResult,
    PandasASTGuardrail,
    clean_code_markdown,
    validate_pandas_code,
)

__all__ = [
    # SQL
    "FORBIDDEN_SQL_KEYWORDS",
    "SQLValidationResult",
    "check_keyword_not_allowed",
    "check_ast_and_multi_query",
    "check_table_allowlist",
    "validate_sql",
    "SQLInjectionGuardrail",
    # NoSQL
    "FORBIDDEN_NOSQL_OPERATORS",
    "NoSQLValidationResult",
    "check_forbidden_nosql_operators",
    "extract_collection_name",
    "repair_mql_json_string",
    "validate_mql",
    "validate_and_parse",
    "NoSQLGuardrail",
    # Pandas
    "FORBIDDEN_PANDAS_CALLS",
    "FORBIDDEN_PANDAS_MODULES",
    "PandasSecurityViolation",
    "PandasValidationResult",
    "PandasASTGuardrail",
    "clean_code_markdown",
    "validate_pandas_code",
]

