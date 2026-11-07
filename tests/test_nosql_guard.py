"""
Unit tests for NoSQL Security Guardrail (nosql_guard.py).

Validates operator blocking, collection resolution, pipeline parsing,
and defense against destructive mutations and JavaScript injection ($where).
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

from dialects.nosql import (
    validate_mql,
    validate_and_parse,
    check_forbidden_nosql_operators,
    extract_collection_name,
    NoSQLGuardrail,
    FORBIDDEN_NOSQL_OPERATORS,
)


def test_valid_aggregate_query():
    mql = 'db.orders.aggregate([{"$match": {"status": "shipped"}}, {"$limit": 5}])'
    res = validate_mql(mql, available_collections=["orders", "products"])
    assert res.is_valid is True
    assert res.error is None
    assert res.collection == "orders"
    assert isinstance(res.payload, list)
    assert len(res.payload) == 2
    assert res.payload[0]["$match"]["status"] == "shipped"


def test_valid_find_query():
    mql = 'db.products.find({"category": "Electronics"})'
    res = validate_mql(mql, available_collections=["orders", "products"])
    assert res.is_valid is True
    assert res.error is None
    assert res.collection == "products"
    assert isinstance(res.payload, dict)
    assert res.payload["category"] == "Electronics"


def test_find_with_sort_and_limit_conversion():
    mql = 'db.products.find({"price": {"$gt": 50}}).sort({"price": -1}).limit(10)'
    res = validate_mql(mql, available_collections=["products"])
    assert res.is_valid is True
    assert res.collection == "products"
    assert isinstance(res.payload, list)  # Converted to aggregation pipeline
    assert any("$match" in stage for stage in res.payload)
    assert any("$sort" in stage for stage in res.payload)
    assert any("$limit" in stage for stage in res.payload)


def test_case_insensitive_and_fallback_collection():
    collections = ["sales_data", "users"]

    # Case-insensitive resolution
    res1 = validate_mql('db.SALES_DATA.find({"year": 2026})', collections)
    assert res1.is_valid is True
    assert res1.collection == "sales_data"

    # Fallback to first collection if unknown name
    res2 = validate_mql('db.unknown_collection.find({})', collections)
    assert res2.is_valid is True
    assert res2.collection == "sales_data"


def test_llm_unquoted_and_single_quoted_json():
    # LLM returning single quotes or unquoted keys
    mql = "db.customers.find({'age': {'$gte': 21}})"
    res = validate_mql(mql, ["customers"])
    assert res.is_valid is True
    assert res.payload == {"age": {"$gte": 21}}


def test_forbidden_operators_blocked():
    attacks = [
        'db.users.updateMany({}, {"$set": {"admin": True}})',
        'db.orders.aggregate([{"$match": {}}, {"$out": "hacked_collection"}])',
        'db.products.deleteOne({"_id": 123})',
        'db.orders.aggregate([{"$merge": {"into": "backup"}}])',
        'db.users.find({"$where": "this.password.length > 0"})',
        'db.users.drop()',
        'db.dropDatabase()',
    ]
    for attack in attacks:
        res = validate_mql(attack, ["users", "orders", "products"])
        assert res.is_valid is False
        assert "Security Violation: Forbidden NoSQL operator" in res.error


def test_empty_and_invalid_mql():
    res_empty = validate_mql("")
    assert res_empty.is_valid is False
    assert "empty" in res_empty.error.lower()

    res_invalid = validate_mql("SELECT * FROM table")
    assert res_invalid.is_valid is False
    assert "Query must follow format" in res_invalid.error


def test_backward_compatible_class():
    mql = 'db.orders.aggregate([{"$count": "total_orders"}])'
    is_valid, err, payload, col = NoSQLGuardrail.validate_and_parse(mql, ["orders"])
    assert is_valid is True
    assert err is None
    assert col == "orders"
    assert payload == [{"$count": "total_orders"}]

