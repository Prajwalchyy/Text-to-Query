"""
Unit tests for NoSQL Dialect (backend/src/dialects/nosql.py).

Validates:
  1. NoSQL Security Guardrails: Operator blocking, collection resolution, pipeline parsing,
     and defense against destructive mutations and JavaScript injection ($where).
  2. NoSQL Schema & BSON: BSON normalization, collection loading, schema inference, context formatting.
  3. MQL Execution: In-memory aggregation pipeline ($match, $group, $sort, $limit, $unwind), $and, $or, $regex.
"""

import json
import sys
import tempfile
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
    resolve_nosql_path,
    normalize_bson_doc,
    load_nosql_collections,
    parse_collection_file,
    compile_collections_to_dataset,
    get_collection_names,
    get_total_document_count,
    get_collection_documents,
    get_schema_fields,
    infer_nosql_relationships,
    get_nosql_schema,
    format_nosql_schema_context,
    execute_mql,
)


# ==============================================================================
# 1. NoSQL Security Guardrail Tests
# ==============================================================================

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


# ==============================================================================
# 2. NoSQL Schema, BSON & Execution Tests
# ==============================================================================

def test_normalize_bson_doc():
    from datetime import datetime
    from decimal import Decimal

    class MockObjectId:
        def __str__(self):
            return "654321abcdef123456789012"

    raw = {
        "_id": MockObjectId(),
        "created_at": datetime(2026, 1, 15, 10, 30, 0),
        "amount": Decimal("129.99"),
        "raw_bytes": b"hello_world",
        "nested": {
            "sub_id": MockObjectId(),
            "tags": ["premium", "active"],
        },
        "items": [
            {"item_id": MockObjectId(), "price": Decimal("49.99")},
            {"item_id": "normal_str", "price": 10.0}
        ]
    }

    normalized = normalize_bson_doc(raw)
    assert normalized["_id"] == "654321abcdef123456789012"
    assert normalized["created_at"] == "2026-01-15T10:30:00"
    assert normalized["amount"] == 129.99
    assert normalized["raw_bytes"] == "hello_world"
    assert normalized["nested"]["sub_id"] == "654321abcdef123456789012"
    assert normalized["items"][0]["item_id"] == "654321abcdef123456789012"
    assert normalized["items"][0]["price"] == 49.99


def test_load_default_ecommerce_store():
    collections = load_nosql_collections()
    assert len(collections) >= 2
    col_names = get_collection_names(collections)
    assert "orders" in col_names or "customers" in col_names
    total_docs = get_total_document_count(collections)
    assert total_docs > 0


def test_nosql_schema_and_relationships():
    collections = load_nosql_collections()
    schema = get_nosql_schema(collections)
    assert "tables" in schema
    assert "relationships" in schema
    assert len(schema["tables"]) > 0

    context = format_nosql_schema_context(collections)
    assert "COLLECTION:" in context
    assert "Fields:" in context
    assert "Sample Document:" in context


def test_mql_match_query():
    collections = load_nosql_collections()
    orders = collections.get("orders", [])
    assert len(orders) > 0

    # Query with dict filter
    status = orders[0].get("status")
    if status:
        results = execute_mql(collections, {"status": status}, target_collection="orders")
        assert len(results) > 0
        assert all(r["status"] == status for r in results)


def test_mql_aggregation_pipeline():
    collections = load_nosql_collections()
    orders = collections.get("orders", [])
    assert len(orders) > 0

    # Pipeline: Match -> Group by status -> Sort by count desc -> Limit 5
    pipeline = [
        {"$match": {"status": {"$ne": ""}}},
        {"$group": {"_id": "$status", "count": {"$count": {}}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]

    results = execute_mql(collections, pipeline, target_collection="orders")
    assert len(results) > 0
    assert "_id" in results[0]
    assert "count" in results[0]


def test_mql_string_parsing():
    collections = load_nosql_collections()
    raw_query = 'db.orders.aggregate([{"$match": {"status": "delivered"}}, {"$limit": 2}])'
    results = execute_mql(collections, raw_query)
    assert isinstance(results, list)
    assert len(results) <= 2


def test_parse_collection_file_and_compilation():
    sample_json = json.dumps([
        {"id": 1, "name": "Alpha"},
        {"id": 2, "name": "Beta"}
    ]).encode("utf-8")

    col_name, docs = parse_collection_file("custom_items.json", sample_json)
    assert col_name == "custom_items"
    assert len(docs) == 2

    files = [
        ("products.json", json.dumps([{"id": 101, "title": "Desk"}]).encode("utf-8")),
        ("reviews.json", json.dumps([{"id": 501, "rating": 5}]).encode("utf-8")),
    ]
    dataset = compile_collections_to_dataset(files)
    assert "products" in dataset
    assert "reviews" in dataset
    assert len(dataset["products"]) == 1
    assert len(dataset["reviews"]) == 1


def test_mql_advanced_operators():
    collections = {
        "inventory": [
            {"sku": "A1", "price": 100, "tags": ["tech", "gadget"], "specs": {"weight": 1.5}},
            {"sku": "A2", "price": 250, "tags": ["furniture"], "specs": {"weight": 12.0}},
            {"sku": "B1", "price": 50, "tags": ["tech", "clearance"], "specs": {"weight": 0.5}},
        ]
    }

    # $and, $or, $regex
    query = {
        "$and": [
            {"$or": [{"price": {"$gt": 200}}, {"tags": "clearance"}]},
            {"sku": {"$regex": "^[AB]"}}
        ]
    }
    results = execute_mql(collections, query, target_collection="inventory")
    skus = [r["sku"] for r in results]
    assert "A2" in skus
    assert "B1" in skus
    assert "A1" not in skus

    # $unwind, $group with $avg, $min, $max
    pipeline = [
        {"$unwind": "$tags"},
        {
            "$group": {
                "_id": "$tags",
                "avg_price": {"$avg": "$price"},
                "min_price": {"$min": "$price"},
                "max_price": {"$max": "$price"}
            }
        },
        {"$sort": {"_id": 1}}
    ]
    grouped = execute_mql(collections, pipeline, target_collection="inventory")
    assert len(grouped) == 4
    tag_ids = [g["_id"] for g in grouped]
    assert "tech" in tag_ids
    tech_group = next(g for g in grouped if g["_id"] == "tech")
    assert tech_group["avg_price"] == 75.0
    assert tech_group["min_price"] == 50
    assert tech_group["max_price"] == 100

