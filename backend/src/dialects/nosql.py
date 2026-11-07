"""
Unified Document / NoSQL Dialect.

Combines pure functional MongoDB MQL query validation guardrails, collection loading,
BSON primitive normalization, recursive schema inference, in-memory MQL aggregation,
and LLM prompt context formatting for document datasets (.json, .jsonl, .bson).
"""

import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple, Union

from config import (
    BACKEND_DIR,
    DATA_DIR,
    DEFAULT_DATA_DIR,
    DEFAULT_JSON_DIR,
    DEFAULT_NOSQL_PATH,
    NOSQL_DEFAULT_DIR,
    NOSQL_DIR,
    UPLOADS_DIR,
)

# Shared Base Foundation
try:
    from dialects.base import (
        ValidationResult,
        normalize_doc_tree,
        resolve_dataset_file,
        sanitize_records_for_json,
        sanitize_scalar,
    )
except ImportError:
    from src.dialects.base import (
        ValidationResult,
        normalize_doc_tree,
        resolve_dataset_file,
        sanitize_records_for_json,
        sanitize_scalar,
    )


# ==============================================================================
# 1. NoSQL Security Guardrails (Stateless Pure Functional)
# ==============================================================================
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

    # 5. Handle db.<collection>.find( ... )
    find_match = re.search(
        r"db\.[a-zA-Z0-9_-]+\.find\s*\(\s*(\{.*?\})?\s*\)",
        clean,
        re.DOTALL,
    )
    if find_match:
        json_str = find_match.group(1)
        if not json_str or not json_str.strip():
            filter_obj = {}
        else:
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


# ==============================================================================
# 2. Path Resolution & Collection Loaders
# ==============================================================================
def resolve_nosql_path(target_path: Optional[Union[Path, str]] = None) -> Path:
    """
    Resolves various representations of a NoSQL dataset path (relative, absolute, or alias)
    into a canonical Path object. Defaults to DEFAULT_NOSQL_PATH if None or empty.
    """
    return resolve_dataset_file(
        target_path=target_path,
        default_path=DEFAULT_NOSQL_PATH,
        search_directories=[
            DEFAULT_DATA_DIR,
            DEFAULT_JSON_DIR,
            UPLOADS_DIR,
            UPLOADS_DIR / "json",
            UPLOADS_DIR / "bson",
            DATA_DIR,
            NOSQL_DIR,
            NOSQL_DEFAULT_DIR,
            BACKEND_DIR,
        ],
        default_alias_names=["ecommerce_store"],
    )


# Backward-compatible alias for universal BSON document normalizer
normalize_bson_doc = normalize_doc_tree


def load_nosql_collections(file_path: Optional[Union[Path, str]] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Loads and parses JSON, JSONL, or BSON collections from disk into a dictionary
    mapping collection_name -> list of document dictionaries.
    """
    path = resolve_nosql_path(file_path)
    if not path.exists():
        return {}

    ext = path.suffix.lower()

    # 1. Native MongoDB BSON Format (.bson)
    if ext == ".bson":
        try:
            import bson  # type: ignore
            with open(path, "rb") as f:
                raw_bytes = f.read()
                if not raw_bytes:
                    return {}
                docs = bson.decode_all(raw_bytes)
                safe_docs = [normalize_bson_doc(d) for d in docs]
                col_name = path.stem.lower().replace("-", "_").replace(" ", "_")
                return {col_name: safe_docs}
        except Exception:
            return {}

    # 2. Standard JSON Lines Format (.jsonl)
    if ext == ".jsonl":
        docs = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line_s = line.strip()
                    if line_s:
                        try:
                            docs.append(normalize_bson_doc(json.loads(line_s)))
                        except Exception:
                            continue
            col_name = path.stem.lower().replace("-", "_").replace(" ", "_")
            return {col_name: docs}
        except Exception:
            return {}

    # 3. Standard JSON Format (.json)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        collections: Dict[str, List[Dict[str, Any]]] = {}

        if isinstance(data, dict):
            # Check if this is a dictionary of collections: {"users": [...], "orders": [...]}
            all_lists_of_dicts = all(
                isinstance(v, list) and (len(v) == 0 or isinstance(v[0], dict))
                for v in data.values()
            )
            if all_lists_of_dicts and len(data) > 0:
                for k, v in data.items():
                    collections[str(k).lower()] = [normalize_bson_doc(d) for d in v if isinstance(d, dict)]
            else:
                # Single document or generic object -> wrap as single collection
                col_name = path.stem.lower().replace("-", "_").replace(" ", "_")
                collections[col_name] = [normalize_bson_doc(data)]

        elif isinstance(data, list):
            # Array of documents -> single collection named after the file stem
            col_name = path.stem.lower().replace("-", "_").replace(" ", "_")
            collections[col_name] = [normalize_bson_doc(d) for d in data if isinstance(d, dict)]

        return collections
    except Exception:
        return {}


def parse_collection_file(filename: str, content: bytes) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Parses raw bytes of an uploaded collection file (.json, .jsonl, .bson)
    into a tuple of (collection_name, list_of_documents).
    """
    clean_name = Path(filename).stem.lower().replace("-", "_").replace(" ", "_")
    ext = Path(filename).suffix.lower()

    if ext == ".bson":
        try:
            import bson  # type: ignore
            docs = bson.decode_all(content)
            return clean_name, [normalize_bson_doc(d) for d in docs]
        except Exception as e:
            raise ValueError(f"Failed to parse BSON file '{filename}': {str(e)}")

    if ext == ".jsonl":
        docs = []
        try:
            text = content.decode("utf-8")
            for idx, line in enumerate(text.splitlines()):
                line_s = line.strip()
                if line_s:
                    try:
                        docs.append(normalize_bson_doc(json.loads(line_s)))
                    except Exception as err:
                        raise ValueError(f"Invalid JSON at line {idx + 1} of '{filename}': {str(err)}")
            return clean_name, docs
        except UnicodeDecodeError:
            raise ValueError(f"File '{filename}' is not valid UTF-8 text.")

    # Default to .json
    try:
        text = content.decode("utf-8")
        data = json.loads(text)
        if isinstance(data, list):
            docs = [normalize_bson_doc(d) for d in data if isinstance(d, dict)]
            return clean_name, docs
        elif isinstance(data, dict):
            # If it's a dict containing a single collection or array of docs
            if len(data) == 1 and isinstance(list(data.values())[0], list):
                key = list(data.keys())[0]
                docs = [normalize_bson_doc(d) for d in data[key] if isinstance(d, dict)]
                return key.lower(), docs
            return clean_name, [normalize_bson_doc(data)]
        else:
            raise ValueError(f"File '{filename}' does not contain a JSON object or array.")
    except UnicodeDecodeError:
        raise ValueError(f"File '{filename}' is not valid UTF-8 text.")
    except json.JSONDecodeError as err:
        raise ValueError(f"Invalid JSON in '{filename}': {str(err)}")


def compile_collections_to_dataset(collection_files: List[Tuple[str, bytes]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Compiles multiple uploaded collection files into a unified in-memory dataset mapping:
    { collection_name: [doc1, doc2, ...] }
    """
    dataset: Dict[str, List[Dict[str, Any]]] = {}
    for filename, content in collection_files:
        col_name, docs = parse_collection_file(filename, content)
        if col_name in dataset:
            dataset[col_name].extend(docs)
        else:
            dataset[col_name] = docs
    return dataset


# ==============================================================================
# 3. Schema Introspection & Relationship Inference
# ==============================================================================
def get_collection_names(
    collections_or_path: Optional[Union[Dict[str, List[Dict[str, Any]]], Path, str]] = None
) -> List[str]:
    """Returns sorted list of collection names."""
    if isinstance(collections_or_path, dict):
        return sorted(list(collections_or_path.keys()))
    cols = load_nosql_collections(collections_or_path)
    return sorted(list(cols.keys()))


def get_total_document_count(collections: Dict[str, List[Dict[str, Any]]]) -> int:
    """Returns the total number of documents across all collections."""
    return sum(len(docs) for docs in collections.values())


def get_collection_documents(
    collections: Dict[str, List[Dict[str, Any]]],
    collection_name: str,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Retrieves document records for a specific collection, up to limit."""
    target = collection_name.lower()
    for col, docs in collections.items():
        if col.lower() == target:
            selected = docs[:limit] if limit is not None else docs
            return [normalize_bson_doc(d) for d in selected]
    return []


def get_schema_fields(docs: List[Dict[str, Any]], sample_limit: int = 25) -> List[Dict[str, str]]:
    """
    Recursively scans documents to discover all nested field paths and types.
    Returns sorted list of dicts: [{"path": "items[].price", "name": "items[].price", "type": "FLOAT"}].
    """
    field_types: Dict[str, str] = {}

    def _infer_type(val: Any) -> str:
        if isinstance(val, bool):
            return "BOOLEAN"
        elif isinstance(val, int):
            return "INTEGER"
        elif isinstance(val, float):
            return "FLOAT"
        elif isinstance(val, str):
            return "STRING"
        elif isinstance(val, list):
            return "ARRAY"
        elif isinstance(val, dict):
            return "OBJECT"
        return "UNKNOWN"

    def _walk(obj: Any, prefix: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                current_path = f"{prefix}.{k}" if prefix else str(k)
                if isinstance(v, dict):
                    _walk(v, current_path)
                elif isinstance(v, list):
                    if len(v) > 0 and isinstance(v[0], dict):
                        _walk(v[0], f"{current_path}[]")
                    elif len(v) > 0:
                        elem_type = _infer_type(v[0])
                        field_types[f"{current_path}[]"] = f"ARRAY<{elem_type}>"
                    else:
                        field_types[f"{current_path}[]"] = "ARRAY"
                else:
                    field_types[current_path] = _infer_type(v)

    for doc in docs[:sample_limit]:
        _walk(doc)

    return [{"path": path, "name": path, "type": dtype} for path, dtype in sorted(field_types.items())]


def infer_nosql_relationships(collections: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Dynamically infers relationships across NoSQL collections by detecting
    reference keys (e.g. customer_id -> customers._id, product_id -> products._id).
    """
    col_names = list(collections.keys())
    if len(col_names) <= 1:
        return []

    relationships: List[Dict[str, Any]] = []
    col_fields_map: Dict[str, List[str]] = {}
    col_pk_map: Dict[str, Optional[str]] = {}
    col_stems_map: Dict[str, Set[str]] = {}

    for c_name in col_names:
        fields = get_schema_fields(collections.get(c_name, []))
        field_paths = [f["path"] for f in fields]
        col_fields_map[c_name] = field_paths

        lower = c_name.lower()
        stems = {lower}
        tokens = [lower]
        if "_" in lower:
            tokens.append(lower.split("_")[-1])
        for t in tokens:
            stems.add(t)
            if t.endswith("ies"):
                stems.add(t[:-3] + "y")
            if t.endswith("es"):
                stems.add(t[:-2])
                stems.add(t[:-1])
            elif t.endswith("s"):
                stems.add(t[:-1])
        col_stems_map[c_name] = stems

        pk: Optional[str] = None
        if "_id" in field_paths:
            pk = "_id"
        else:
            for stem in stems:
                cand = f"{stem}_id"
                if cand in field_paths:
                    pk = cand
                    break
            if pk is None and "id" in field_paths:
                pk = "id"
        col_pk_map[c_name] = pk

    for c_name in col_names:
        field_paths = col_fields_map[c_name]
        own_pk = col_pk_map.get(c_name)

        for f_path in field_paths:
            if f_path == own_pk:
                continue

            f_base = f_path.split(".")[-1].lower()

            for target_col in col_names:
                if target_col == c_name:
                    continue

                target_stems = col_stems_map[target_col]
                target_fields = col_fields_map[target_col]
                target_pk = col_pk_map.get(target_col) or "_id"

                is_match = False
                for stem in target_stems:
                    if f_base in (f"{stem}_id", f"id_{stem}", stem):
                        is_match = True
                        break

                if is_match:
                    target_col_name = target_pk if target_pk in target_fields else (target_fields[0] if target_fields else "_id")
                    rel = {
                        "from_table": c_name,
                        "from_col": f_path,
                        "to_table": target_col,
                        "to_col": target_col_name,
                    }
                    if rel not in relationships:
                        relationships.append(rel)

    return relationships


def get_nosql_schema(
    collections_or_path: Optional[Union[Dict[str, List[Dict[str, Any]]], Path, str]] = None,
    file_path: Optional[Union[Path, str]] = None,
) -> Dict[str, Any]:
    """
    Returns full schema representation for NoSQL collections:
    {"tables": [...], "relationships": [...]}
    """
    if collections_or_path is not None and isinstance(collections_or_path, dict):
        collections = collections_or_path
    elif collections_or_path is not None:
        path = resolve_nosql_path(collections_or_path)
        collections = load_nosql_collections(path)
    else:
        path = resolve_nosql_path(file_path)
        collections = load_nosql_collections(path)

    schema_tables = []
    for col_name in collections.keys():
        fields = get_schema_fields(collections[col_name])
        col_list = [f"{f['path']} ({f['type']})" for f in fields]
        schema_tables.append({
            "name": col_name,
            "cols": col_list,
            "count": len(collections[col_name]),
            "fields": fields,
        })

    relationships = infer_nosql_relationships(collections)
    return {
        "tables": schema_tables,
        "collections": schema_tables,
        "relationships": relationships,
    }


def format_nosql_schema_context(
    collections_or_path: Optional[Union[Dict[str, List[Dict[str, Any]]], Path, str]] = None,
    file_path: Optional[Union[Path, str]] = None,
) -> str:
    """Builds clean schema context text for LLM prompts."""
    if collections_or_path is not None and isinstance(collections_or_path, dict):
        collections = collections_or_path
    elif collections_or_path is not None:
        path = resolve_nosql_path(collections_or_path)
        collections = load_nosql_collections(path)
    else:
        path = resolve_nosql_path(file_path)
        collections = load_nosql_collections(path)

    lines: List[str] = []
    for col_name, docs in collections.items():
        fields = get_schema_fields(docs)
        field_lines = [f"    - {f['path']} ({f['type']})" for f in fields]
        sample = json.dumps(docs[0], indent=2, default=str) if docs else "{}"
        lines.append(f"COLLECTION: {col_name} ({len(docs)} documents)")
        lines.append("  Fields:\n" + "\n".join(field_lines))
        lines.append(f"  Sample Document:\n{sample}\n")

    rels = infer_nosql_relationships(collections)
    if rels:
        lines.append("RELATIONSHIPS:")
        for r in rels:
            lines.append(f"  {r['from_table']}.{r['from_col']} -> {r['to_table']}.{r['to_col']}")

    return "\n".join(lines).strip()


# ==============================================================================
# 4. In-Memory MongoDB MQL Pipeline Execution
# ==============================================================================
def get_nested_val(doc: Dict[str, Any], path: str) -> Any:
    """Safely retrieves a value from a nested dictionary using dot notation (e.g. 'address.city')."""
    if not isinstance(doc, dict):
        return None
    if path in doc:
        return doc[path]
    parts = path.split(".")
    curr: Any = doc
    for p in parts:
        if isinstance(curr, dict) and p in curr:
            curr = curr[p]
        else:
            return None
    return curr


def matches_document(doc: Dict[str, Any], filter_spec: Dict[str, Any]) -> bool:
    """Evaluates whether a single document matches an MQL filter specification."""
    if not filter_spec:
        return True

    for key, condition in filter_spec.items():
        if key == "$and":
            if not isinstance(condition, list) or not all(matches_document(doc, sub) for sub in condition):
                return False
            continue

        if key == "$or":
            if not isinstance(condition, list) or not any(matches_document(doc, sub) for sub in condition):
                return False
            continue

        if key == "$nor":
            if not isinstance(condition, list) or any(matches_document(doc, sub) for sub in condition):
                return False
            continue

        doc_val = get_nested_val(doc, key)

        if not isinstance(condition, dict):
            if isinstance(doc_val, list):
                if condition not in doc_val:
                    return False
            elif doc_val != condition:
                return False
        else:
            for op, target in condition.items():
                if op == "$eq" and doc_val != target:
                    return False
                elif op == "$ne" and doc_val == target:
                    return False
                elif op == "$gt" and not (doc_val is not None and doc_val > target):
                    return False
                elif op == "$gte" and not (doc_val is not None and doc_val >= target):
                    return False
                elif op == "$lt" and not (doc_val is not None and doc_val < target):
                    return False
                elif op == "$lte" and not (doc_val is not None and doc_val <= target):
                    return False
                elif op == "$in":
                    if not isinstance(target, (list, tuple, set)) or doc_val not in target:
                        return False
                elif op == "$nin":
                    if isinstance(target, (list, tuple, set)) and doc_val in target:
                        return False
                elif op == "$exists":
                    exists = doc_val is not None
                    if bool(target) != exists:
                        return False
                elif op == "$regex":
                    if doc_val is None or not re.search(str(target), str(doc_val), re.IGNORECASE):
                        return False

    return True


def apply_match(docs: List[Dict[str, Any]], filter_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Applies a MongoDB $match stage filter to a document list."""
    return [d for d in docs if matches_document(d, filter_spec)]


def apply_group(docs: List[Dict[str, Any]], group_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Applies an MQL $group stage to a list of documents.
    """
    id_spec = group_spec.get("_id")
    accumulators = {k: v for k, v in group_spec.items() if k != "_id"}

    def get_group_key(d: Dict[str, Any]) -> Any:
        if id_spec is None:
            return "all"
        if isinstance(id_spec, str) and id_spec.startswith("$"):
            return get_nested_val(d, id_spec[1:])
        if isinstance(id_spec, dict):
            return tuple((k, get_nested_val(d, v[1:]) if isinstance(v, str) and v.startswith("$") else v)
                         for k, v in sorted(id_spec.items()))
        return id_spec

    grouped: Dict[Any, List[Dict[str, Any]]] = {}
    for d in docs:
        k = get_group_key(d)
        grouped.setdefault(k, []).append(d)

    output: List[Dict[str, Any]] = []
    for g_key, g_docs in grouped.items():
        res: Dict[str, Any] = {}
        if isinstance(id_spec, dict):
            res["_id"] = dict(g_key) if isinstance(g_key, tuple) else g_key
        else:
            res["_id"] = None if g_key == "all" and id_spec is None else g_key

        for acc_name, acc_spec in accumulators.items():
            if isinstance(acc_spec, dict):
                op, arg = next(iter(acc_spec.items()))
                val_fn = (lambda d: get_nested_val(d, arg[1:])) if isinstance(arg, str) and arg.startswith("$") else (lambda d: arg)

                if op == "$sum":
                    if isinstance(arg, (int, float)):
                        res[acc_name] = len(g_docs) * arg
                    else:
                        vals = [val_fn(d) for d in g_docs if val_fn(d) is not None]
                        res[acc_name] = sum(v for v in vals if isinstance(v, (int, float)))
                elif op == "$avg":
                    vals = [val_fn(d) for d in g_docs if isinstance(val_fn(d), (int, float))]
                    res[acc_name] = round(sum(vals) / len(vals), 2) if vals else None
                elif op == "$min":
                    vals = [val_fn(d) for d in g_docs if val_fn(d) is not None]
                    res[acc_name] = min(vals) if vals else None
                elif op == "$max":
                    vals = [val_fn(d) for d in g_docs if val_fn(d) is not None]
                    res[acc_name] = max(vals) if vals else None
                elif op == "$first":
                    res[acc_name] = val_fn(g_docs[0]) if g_docs else None
                elif op == "$last":
                    res[acc_name] = val_fn(g_docs[-1]) if g_docs else None
                elif op == "$push":
                    res[acc_name] = [val_fn(d) for d in g_docs]
                elif op == "$addToSet":
                    seen = []
                    for d in g_docs:
                        v = val_fn(d)
                        if v not in seen:
                            seen.append(v)
                    res[acc_name] = seen
                else:
                    res[acc_name] = None
            else:
                res[acc_name] = acc_spec

        output.append(res)

    return output


def _sort_safe_key(val: Any) -> Tuple[int, Any]:
    """Helper to ensure heterogeneous values can be sorted in Python 3 without TypeError."""
    if val is None:
        return (0, "")
    if isinstance(val, (int, float)):
        return (1, val)
    if isinstance(val, str):
        return (2, val)
    return (3, str(val))


def apply_sort(docs: List[Dict[str, Any]], sort_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Applies a multi-key MQL $sort stage to a document list."""
    if not sort_spec:
        return docs

    sort_keys = list(sort_spec.items())

    def sort_comparator(doc: Dict[str, Any]) -> Tuple:
        res = []
        for field, direction in sort_keys:
            raw_v = get_nested_val(doc, field)
            res.append(_sort_safe_key(raw_v))
        return tuple(res)

    reverse_sort = sort_keys[0][1] < 0 if sort_keys else False
    return sorted(docs, key=sort_comparator, reverse=reverse_sort)


def apply_project(docs: List[Dict[str, Any]], project_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Applies an MQL $project stage, retaining only specified fields or computed values."""
    output = []
    include_id = project_spec.get("_id", 1) != 0

    for d in docs:
        proj_doc: Dict[str, Any] = {}
        if include_id and "_id" in d:
            proj_doc["_id"] = d["_id"]

        for k, v in project_spec.items():
            if k == "_id":
                continue
            if v == 1 or v is True:
                if k in d:
                    proj_doc[k] = d[k]
            elif isinstance(v, str) and v.startswith("$"):
                proj_doc[k] = get_nested_val(d, v[1:])
            elif not isinstance(v, (int, bool)):
                proj_doc[k] = v

        output.append(proj_doc)

    return output


def apply_unwind(docs: List[Dict[str, Any]], path_expr: Any) -> List[Dict[str, Any]]:
    """Applies an MQL $unwind stage, deconstructing an array field into separate documents."""
    path = path_expr.lstrip("$") if isinstance(path_expr, str) else str(path_expr)
    output = []
    for d in docs:
        arr = get_nested_val(d, path)
        if isinstance(arr, list) and len(arr) > 0:
            for item in arr:
                new_d = dict(d)
                new_d[path] = item
                output.append(new_d)
        else:
            output.append(d)
    return output


def execute_mql(
    collections: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    query: Any = None,
    target_collection: Optional[str] = None,
    default_collection: Optional[str] = None,
    file_path: Optional[Union[Path, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Executes a parsed or raw MongoDB MQL query against in-memory document collections.
    """
    if collections is None:
        collections = load_nosql_collections(file_path)

    if not collections:
        return []

    target_col = target_collection or default_collection
    payload: Any = query
    extracted_target: Optional[str] = None

    if isinstance(query, str):
        clean_q = query.strip()
        if clean_q.startswith("```"):
            clean_q = re.sub(r"^```(?:json|mql|javascript|js)?\n?", "", clean_q)
            clean_q = re.sub(r"\n?```$", "", clean_q).strip()

        val_result = validate_mql(clean_q, list(collections.keys()))
        if val_result.is_valid:
            payload = val_result.payload
            extracted_target = val_result.collection
        else:
            raise ValueError(f"MQL Validation Error: {val_result.error}")

    resolved_target = target_col or extracted_target
    available_cols = list(collections.keys())

    if resolved_target is None or resolved_target not in collections:
        matched_target = None
        if resolved_target is not None:
            for k in available_cols:
                if k.lower() == resolved_target.lower():
                    matched_target = k
                    break
        resolved_target = matched_target or (available_cols[0] if available_cols else "default")

    docs = [dict(d) for d in collections.get(resolved_target, [])]

    if isinstance(payload, dict):
        return sanitize_records_for_json(apply_match(docs, payload)[:100])

    elif isinstance(payload, list):
        current_docs = docs
        for stage in payload:
            if not isinstance(stage, dict):
                continue
            stage_name, stage_arg = next(iter(stage.items()))
            if stage_name == "$match" and isinstance(stage_arg, dict):
                current_docs = apply_match(current_docs, stage_arg)
            elif stage_name == "$group" and isinstance(stage_arg, dict):
                current_docs = apply_group(current_docs, stage_arg)
            elif stage_name == "$sort" and isinstance(stage_arg, dict):
                current_docs = apply_sort(current_docs, stage_arg)
            elif stage_name == "$project" and isinstance(stage_arg, dict):
                current_docs = apply_project(current_docs, stage_arg)
            elif stage_name == "$limit" and isinstance(stage_arg, int):
                current_docs = current_docs[:stage_arg]
            elif stage_name == "$unwind":
                current_docs = apply_unwind(current_docs, stage_arg)
            elif stage_name == "$count":
                count_field = str(stage_arg) if stage_arg else "count"
                current_docs = [{count_field: len(current_docs)}]

        return sanitize_records_for_json(current_docs[:100])

    return sanitize_records_for_json(docs[:10])
