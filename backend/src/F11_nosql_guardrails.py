import json
import re
from typing import Tuple, Any, List, Optional

FORBIDDEN_NOSQL_OPERATORS = [
    "$drop", "$delete", "$deleteMany", "$deleteOne", "$remove",
    "$update", "$updateMany", "$updateOne", "$set", "$unset",
    "$renameCollection", "$dropDatabase", "$out", "$merge"
]


class NoSQLGuardrail:
    """
    Defense-in-Depth Safety Guardrail for NoSQL & MongoDB MQL Queries.
    Blocks destructive mutations, extracts target collection name, parses raw MQL
    into executable Python objects, and validates query structure.
    """

    @staticmethod
    def validate_and_parse(raw_mql: str, available_collections: Optional[List[str]] = None) -> Tuple[bool, Optional[str], Optional[Any], Optional[str]]:
        """
        Validates the MQL query string for security violations and parses
        it into an executable Python list (aggregation) or dict (find filter).
        
        Returns:
            (is_valid: bool, error_message: Optional[str], parsed_payload: Optional[Any], target_collection: Optional[str])
        """
        if raw_mql.strip() == "":
            return False, "Query is empty.", None, None

        # 1. Keyword / Operator Blocklist
        for forbidden in FORBIDDEN_NOSQL_OPERATORS:
            if forbidden.lower() in raw_mql.lower():
                return False, f"Security Violation: Forbidden NoSQL operator '{forbidden}' detected. Only Read-Only queries are allowed.", None, None

        clean = raw_mql.strip()

        # Extract collection name: db.<collection>.(aggregate|find)
        col_match = re.search(r"db\.([a-zA-Z0-9_-]+)\.", clean)
        target_collection = col_match.group(1) if col_match else None

        if available_collections != None and target_collection != None:
            # Case-insensitive collection matching
            matched = next((c for c in available_collections if c.lower() == target_collection.lower()), None)
            if matched != None:
                target_collection = matched

        # Handle db.<collection>.aggregate([ ... ])
        agg_match = re.search(r"db\.[a-zA-Z0-9_-]+\.aggregate\s*\(\s*(\[.*\])\s*\)", clean, re.DOTALL)
        if agg_match:
            json_str = agg_match.group(1)
            try:
                payload = json.loads(json_str)
                return True, None, payload, target_collection
            except json.JSONDecodeError as e:
                fixed_json = re.sub(r'([{\s,])([a-zA-Z0-9_$]+)\s*:', r'\1"\2":', json_str)
                fixed_json = fixed_json.replace("'", '"')
                try:
                    payload = json.loads(fixed_json)
                    return True, None, payload, target_collection
                except Exception:
                    return False, f"Invalid MongoDB aggregation pipeline JSON: {str(e)}", None, target_collection

        # Handle db.<collection>.find({ ... })
        find_match = re.search(r"db\.[a-zA-Z0-9_-]+\.find\s*\(\s*(\{.*\})\s*\)", clean, re.DOTALL)
        if find_match:
            json_str = find_match.group(1)
            try:
                payload = json.loads(json_str)
                return True, None, payload, target_collection
            except json.JSONDecodeError as e:
                fixed_json = re.sub(r'([{\s,])([a-zA-Z0-9_$]+)\s*:', r'\1"\2":', json_str)
                fixed_json = fixed_json.replace("'", '"')
                try:
                    payload = json.loads(fixed_json)
                    return True, None, payload, target_collection
                except Exception:
                    return False, f"Invalid MongoDB find() filter JSON: {str(e)}", None, target_collection

        # Handle raw JSON list or dict directly
        if clean.startswith("[") or clean.startswith("{"):
            try:
                payload = json.loads(clean)
                return True, None, payload, target_collection
            except Exception as e:
                return False, f"Invalid JSON query payload: {str(e)}", None, target_collection

        return False, "Query must follow format: db.<collection>.aggregate([ ... ]) or db.<collection>.find({ ... })", None, target_collection
