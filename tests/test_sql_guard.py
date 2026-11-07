"""
Unit tests for SQL Security Guardrail (sql_guard.py).

Validates 4-layer defense against SQL injection, DDL/DML mutation,
multi-statement injection, and unlisted table access.
"""

import sys
from pathlib import Path
import pytest

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
src_dir = backend_dir / "src"
for p in [str(root_dir), str(backend_dir), str(src_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from dialects.sql import (
    validate_sql,
    check_keyword_not_allowed,
    check_ast_and_multi_query,
    check_table_allowlist,
    SQLInjectionGuardrail,
    FORBIDDEN_SQL_KEYWORDS,
)


def test_valid_select_queries():
    # Simple select
    res = validate_sql("SELECT * FROM Artist LIMIT 5;")
    assert res.is_valid is True
    assert res.error is None
    assert res.sanitized_sql == "SELECT * FROM Artist LIMIT 5;"

    # Join query
    join_sql = "SELECT c.FirstName, i.Total FROM Customer c JOIN Invoice i ON c.CustomerId = i.CustomerId"
    res2 = validate_sql(join_sql)
    assert res2.is_valid is True
    assert res2.sanitized_sql == join_sql + ";"


def test_valid_union_query():
    union_sql = "SELECT ArtistId, Name FROM Artist UNION SELECT AlbumId, Title FROM Album;"
    res = validate_sql(union_sql)
    assert res.is_valid is True
    assert res.sanitized_sql == union_sql


def test_cte_and_table_allowlist():
    allowed = {"artist", "album"}

    # Allowed table passes
    res1 = validate_sql("SELECT * FROM Artist;", allowed_tables=allowed)
    assert res1.is_valid is True

    # CTE alias should not be flagged as missing table
    cte_sql = "WITH LocalArtists AS (SELECT ArtistId, Name FROM Artist) SELECT * FROM LocalArtists;"
    res2 = validate_sql(cte_sql, allowed_tables=allowed)
    assert res2.is_valid is True

    # Non-allowed table triggers Layer 4 schema violation
    res3 = validate_sql("SELECT * FROM Customer;", allowed_tables=allowed)
    assert res3.is_valid is False
    assert "Schema Violation" in res3.error
    assert "Customer" in res3.error


def test_string_literal_with_forbidden_word():
    # 'Drop' inside string literal should NOT trigger Layer 1 keyword block
    sql = "SELECT * FROM Track WHERE Name = 'Drop the beat';"
    res = validate_sql(sql)
    assert res.is_valid is True


def test_forbidden_keywords_blocked():
    attacks = [
        "DROP TABLE Customer;",
        "DELETE FROM Invoice WHERE Total > 10;",
        "UPDATE Customer SET Email = 'hacked@hack.com';",
        "INSERT INTO Artist (Name) VALUES ('Evil');",
        "ALTER TABLE Album ADD COLUMN hacked TEXT;",
        "TRUNCATE TABLE Invoice;",
    ]
    for attack in attacks:
        res = validate_sql(attack)
        assert res.is_valid is False
        assert "Security Violation: Forbidden keyword" in res.error


def test_multi_statement_injection_blocked():
    attacks = [
        "SELECT * FROM Track; DROP TABLE Album;",
        "SELECT 1; SELECT 2;",
        "SELECT * FROM Artist; DELETE FROM Customer;",
    ]
    for attack in attacks:
        res = validate_sql(attack)
        assert res.is_valid is False
        assert (
            "Multi-statement" in res.error
            or "Forbidden keyword" in res.error
        )


def test_empty_and_malformed_sql():
    res_empty = validate_sql("")
    assert res_empty.is_valid is False
    assert "Empty query" in res_empty.error

    res_syntax = validate_sql("SELECT FROM WHERE ;")
    assert res_syntax.is_valid is False
    assert "SQL Syntax Error" in res_syntax.error


def test_backward_compatible_class():
    class DummyEngine:
        def get_table_names(self):
            return ["Artist", "Album"]

    guard = SQLInjectionGuardrail(db_engine=DummyEngine())
    is_valid, reason, safe_sql = guard.validate_sql("SELECT * FROM Artist LIMIT 10")
    assert is_valid is True
    assert safe_sql == "SELECT * FROM Artist LIMIT 10;"

    is_valid_bad, reason_bad, _ = guard.validate_sql("DROP TABLE Artist;")
    assert is_valid_bad is False
    assert "Forbidden keyword" in reason_bad

