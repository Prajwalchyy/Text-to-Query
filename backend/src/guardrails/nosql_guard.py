"""
NoSQL Security Guardrail (Stateless Pure Functional).

Implements defense-in-depth safety for NoSQL & MongoDB MQL queries:
  - Destructive operator blocker (blocks 14 mutation operators + $where JS injection).
  - Collection name extraction and allowlist resolution.
  - Chained helper parser (.limit(), .sort()).
  - Safe JSON parser with key quotation and single-quote repair.
  - Direct JSON pipeline or filter payload parsing.

Zero-state pure functional architecture replacing legacy backend/src/F11_nosql_guardrails.py.
"""

import json
import re
from typing import Any, List, NamedTuple, Optional, Tuple, Union


FORBIDDEN_NOSQL_OPERATORS: List[str] = [
    "$drop",
    "$delete",
    "$deleteMany",
    "$deleteOne",
    "$remove",
    "$update",
    "$updateMany",
    "$updateOne",
    "$set",
    "$unset",
    "$renameCollection",
    "$dropDatabase",
    "$out",
    "$merge",
    "$where",
    ".drop(",
    ".delete(",
    ".deleteMany(",
    ".deleteOne(",
    ".remove(",
    ".update(",
    ".updateMany(",
    ".updateOne(",
    ".dropDatabase(",
    ".renameCollection(",
]


class NoSQLValidationResult(NamedTuple):
    """Immutable validation result for NoSQL/MQL queries."""

    is_valid: bool
    error: Optional[str]
    payload: Optional[Any]
    collection: Optional[str]


def check_forbidden_nosql_operators(
    raw_mql: str,
    forbidden_operators: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Scans raw MQL for destructive or unsafe mutation operators and methods.
    Returns an error message if any forbidden operator is detected, otherwise None.
    """
    forbidden = forbidden_operators or FORBIDDEN_NOSQL_OPERATORS
    lower_mql = raw_mql.lower()
    for op in forbidden:
        clean_op = op.rstrip("(")
        if op.lower() in lower_mql or (clean_op.startswith(".") and clean_op.lower() in lower_mql):
            display_op = clean_op.lstrip(".")
            return (
                f"Security Violation: Forbidden NoSQL operator '{display_op}' detected. "
                "Only Read-Only queries are allowed."
            )
    return None


def extract_collection_name(
    raw_mql: str,
    available_collections: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Extracts collection name from db.<collection>.(aggregate|find) pattern.
    Resolves against available_collections using case-insensitive matching or fallback.
    """
    clean = raw_mql.strip()
    col_match = re.search(r"db\.([a-zA-Z0-9_-]+)\.", clean)
    target_collection = col_match.group(1) if col_match else None

    if available_collections is not None and len(available_collections) > 0:
        if target_collection is not None:
            matched = next(
                (c for c in available_collections if c.lower() == target_collection.lower()),
                None,
            )
            if matched is not None:
                target_collection = matched
            else:
                # If target collection is the database name or unknown, fallback to first collection
                target_collection = available_collections[0]
        else:
            target_collection = available_collections[0]

    return target_collection


def repair_mql_json_string(json_str: str) -> str:
    """
    Repairs common LLM JSON syntax issues like unquoted object keys and single quotes.
    """
    fixed = re.sub(r'([{\s,])([a-zA-Z0-9_$]+)\s*:', r'\1"\2":', json_str)
    fixed = fixed.replace("'", '"')
    return fixed


def validate_mql(
    raw_mql: str,
    available_collections: Optional[List[str]] = None,
    forbidden_operators: Optional[List[str]] = None,
) -> NoSQLValidationResult:
    """
    Validates MQL query string for security violations and parses it into an
    executable Python list (aggregation pipeline) or dict (find filter).
    
    Returns:
        NoSQLValidationResult(is_valid: bool, error: Optional[str], payload: Optional[Any], collection: Optional[str])
    """
    if not raw_mql or not raw_mql.strip():
        return NoSQLValidationResult(False, "Query is empty.", None, None)

    # 1. Check forbidden destructive operators
    operator_error = check_forbidden_nosql_operators(raw_mql, forbidden_operators)
    if operator_error:
        return NoSQLValidationResult(False, operator_error, None, None)

    clean = raw_mql.strip()

    # 2. Extract target collection
    target_collection = extract_collection_name(clean, available_collections)

    # 3. Extract chained .limit(N) and .sort(...)
    limit_match = re.search(r"\.limit\s*\(\s*(\d+)\s*\)", clean)
    limit_val = int(limit_match.group(1)) if limit_match else None

    sort_match = re.search(r"\.sort\s*\(\s*(\{.*\})\s*\)", clean)
    sort_val = None
    if sort_match:
        try:
            sort_json = repair_mql_json_string(sort_match.group(1))
            sort_val = json.loads(sort_json)
        except Exception:
            pass

    # 4. Handle db.<collection>.aggregate([ ... ])
    agg_match = re.search(
        r"db\.[a-zA-Z0-9_-]+\.aggregate\s*\(\s*(\[.*\])\s*\)",
        clean,
        re.DOTALL,
    )
    if agg_match:
        json_str = agg_match.group(1)
        try:
            payload = json.loads(json_str)
            return NoSQLValidationResult(True, None, payload, target_collection)
        except json.JSONDecodeError as err:
            fixed_json = repair_mql_json_string(json_str)
            try:
                payload = json.loads(fixed_json)
                return NoSQLValidationResult(True, None, payload, target_collection)
            except Exception:
                return NoSQLValidationResult(
                    False,
                    f"Invalid MongoDB aggregation pipeline JSON: {str(err)}",
                    None,
                    target_collection,
                )

    # 5. Handle db.<collection>.find({ ... })
    find_match = re.search(
        r"db\.[a-zA-Z0-9_-]+\.find\s*\(\s*(\{.*?\})\s*\)",
        clean,
        re.DOTALL,
    )
    if find_match:
        json_str = find_match.group(1)
        try:
            filter_obj = json.loads(json_str)
        except json.JSONDecodeError:
            fixed_json = repair_mql_json_string(json_str)
            try:
                filter_obj = json.loads(fixed_json)
            except Exception as err:
                return NoSQLValidationResult(
                    False,
                    f"Invalid MongoDB find() filter JSON: {str(err)}",
                    None,
                    target_collection,
                )

        # Convert find + sort + limit to equivalent aggregation pipeline if sort or limit exists
        if limit_val is not None or sort_val is not None:
            pipeline = []
            if filter_obj and len(filter_obj) > 0:
                pipeline.append({"$match": filter_obj})
            if sort_val:
                pipeline.append({"$sort": sort_val})
            if limit_val is not None:
                pipeline.append({"$limit": limit_val})
            return NoSQLValidationResult(True, None, pipeline, target_collection)

        return NoSQLValidationResult(True, None, filter_obj, target_collection)

    # 6. Handle raw JSON list or dict directly
    if clean.startswith("[") or clean.startswith("{"):
        try:
            payload = json.loads(clean)
            return NoSQLValidationResult(True, None, payload, target_collection)
        except Exception:
            fixed_json = repair_mql_json_string(clean)
            try:
                payload = json.loads(fixed_json)
                return NoSQLValidationResult(True, None, payload, target_collection)
            except Exception as err:
                return NoSQLValidationResult(
                    False,
                    f"Invalid JSON query payload: {str(err)}",
                    None,
                    target_collection,
                )

    return NoSQLValidationResult(
        False,
        "Query must follow format: db.<collection>.aggregate([ ... ]) or db.<collection>.find({ ... })",
        None,
        target_collection,
    )


# Backward-compatible alias
validate_and_parse = validate_mql


class NoSQLGuardrail:
    """Backward-compatible adapter for legacy F11_nosql_guardrails.NoSQLGuardrail."""

    FORBIDDEN_OPERATORS = FORBIDDEN_NOSQL_OPERATORS

    @staticmethod
    def validate_and_parse(
        raw_mql: str,
        available_collections: Optional[List[str]] = None,
    ) -> Tuple[bool, Optional[str], Optional[Any], Optional[str]]:
        result = validate_mql(raw_mql, available_collections)
        return result.is_valid, result.error, result.payload, result.collection
