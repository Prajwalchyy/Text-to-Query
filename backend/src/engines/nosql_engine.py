"""
NoSQL Document Database Execution Engine.

Provides pure functional MongoDB MQL query execution, collection loading,
BSON primitive normalization, recursive schema inference, and LLM prompt context
formatting for document datasets (.json, .jsonl, .bson).

Zero OOP classes; 100% stateless functions with clean, typed inputs and outputs.
"""

import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from config import DATA_DIR, NOSQL_DIR, NOSQL_DEFAULT_DIR, DEFAULT_NOSQL_PATH, BACKEND_DIR


# ==============================================================================
# Path Resolution & Type Normalization
# ==============================================================================
def resolve_nosql_path(target_path: Optional[Union[Path, str]] = None) -> Path:
    """
    Resolves various representations of a NoSQL dataset path (relative, absolute, or alias)
    into a canonical Path object. Defaults to DEFAULT_NOSQL_PATH if None or empty.
    """
    if target_path is None or target_path == "" or str(target_path).strip() == "ecommerce_store":
        return DEFAULT_NOSQL_PATH.resolve()

    p = Path(str(target_path).strip())
    if p.is_absolute() and p.exists():
        return p.resolve()

    filename = p.name
    for base in [DATA_DIR, NOSQL_DIR, NOSQL_DEFAULT_DIR, BACKEND_DIR]:
        candidate_file = (base / filename).resolve()
        if candidate_file.exists():
            return candidate_file

    for base in [DATA_DIR, NOSQL_DIR, NOSQL_DEFAULT_DIR, BACKEND_DIR]:
        try:
            candidate = (base / p).resolve()
            if candidate.exists():
                return candidate
        except Exception:
            pass

    return p.resolve()


def normalize_bson_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively converts BSON specific types (ObjectId, datetime, Decimal, bytes)
    and complex Python primitives to clean JSON-serializable primitives.
    """
    normalized: Dict[str, Any] = {}
    for k, v in doc.items():
        if hasattr(v, "__str__") and type(v).__name__.endswith("ObjectId"):
            normalized[k] = str(v)
        elif isinstance(v, (datetime, date)):
            normalized[k] = v.isoformat()
        elif hasattr(v, "isoformat"):
            normalized[k] = v.isoformat()
        elif isinstance(v, Decimal):
            normalized[k] = float(v)
        elif isinstance(v, bytes):
            try:
                normalized[k] = v.decode("utf-8")
            except UnicodeDecodeError:
                normalized[k] = v.hex()
        elif isinstance(v, dict):
            normalized[k] = normalize_bson_doc(v)
        elif isinstance(v, list):
            normalized[k] = [
                normalize_bson_doc(item)
                if isinstance(item, dict)
                else (
                    str(item)
                    if hasattr(item, "__str__") and type(item).__name__.endswith("ObjectId")
                    else (
                        item.isoformat()
                        if isinstance(item, (datetime, date)) or hasattr(item, "isoformat")
                        else (float(item) if isinstance(item, Decimal) else item)
                    )
                )
                for item in v
            ]
        else:
            normalized[k] = v
    return normalized


# ==============================================================================
# Collection Loaders & Compilers
# ==============================================================================
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

    # 2. JSON Lines Format (.jsonl)
    if ext == ".jsonl":
        try:
            docs: List[Dict[str, Any]] = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if line_str:
                        docs.append(normalize_bson_doc(json.loads(line_str)))
            col_name = path.stem.lower().replace("-", "_").replace(" ", "_")
            return {col_name: docs}
        except Exception:
            return {}

    # 3. Standard JSON Format (.json)
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}

            parsed = json.loads(content)
            collections: Dict[str, List[Dict[str, Any]]] = {}

            if isinstance(parsed, dict):
                # Multi-Collection format: { "orders": [...], "customers": [...], "products": [...] }
                for k, v in parsed.items():
                    clean_k = k.lower().replace("-", "_").replace(" ", "_")
                    if isinstance(v, list):
                        collections[clean_k] = [
                            normalize_bson_doc(d) if isinstance(d, dict) else {"value": d}
                            for d in v
                        ]
                    elif isinstance(v, dict):
                        collections[clean_k] = [normalize_bson_doc(v)]
                return collections

            elif isinstance(parsed, list):
                # Single Collection format: [ { ... }, { ... } ]
                col_name = path.stem.lower().replace("-", "_").replace(" ", "_")
                clean_docs = [
                    normalize_bson_doc(d) if isinstance(d, dict) else {"value": d}
                    for d in parsed
                ]
                return {col_name: clean_docs}
            else:
                return {}
    except Exception:
        return {}


def parse_collection_file(filename: str, content: bytes) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Parses an individual .json, .jsonl, or .bson collection file from raw bytes into (collection_name, documents).
    Uses sanitized file stem as the collection name (e.g. 'customers.json' -> 'customers').
    """
    path = Path(filename)
    col_name = path.stem.lower().replace("-", "_").replace(" ", "_")
    ext = path.suffix.lower()

    if ext == ".bson":
        try:
            import bson  # type: ignore
            raw_docs = bson.decode_all(content)
            safe_docs = [normalize_bson_doc(d) for d in raw_docs]
            return col_name, safe_docs
        except Exception:
            return col_name, []

    if ext == ".jsonl":
        text = content.decode("utf-8", errors="ignore")
        docs: List[Dict[str, Any]] = []
        for line in text.splitlines():
            l = line.strip()
            if l:
                try:
                    docs.append(normalize_bson_doc(json.loads(l)))
                except Exception:
                    continue
        return col_name, docs

    # Default .json
    text = content.decode("utf-8", errors="ignore")
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            clean_list = [normalize_bson_doc(d) if isinstance(d, dict) else {"value": d} for d in parsed]
            return col_name, clean_list
        elif isinstance(parsed, dict):
            has_nested_lists = any(isinstance(v, list) for v in parsed.values())
            if has_nested_lists:
                if col_name in parsed and isinstance(parsed[col_name], list):
                    return col_name, [normalize_bson_doc(d) if isinstance(d, dict) else {"value": d} for d in parsed[col_name]]
                for k, v in parsed.items():
                    if isinstance(v, list):
                        return k.lower().replace("-", "_").replace(" ", "_"), [
                            normalize_bson_doc(d) if isinstance(d, dict) else {"value": d} for d in v
                        ]
            return col_name, [normalize_bson_doc(parsed)]
    except Exception:
        pass

    return col_name, []


def compile_collections_to_dataset(collection_files: List[Tuple[str, bytes]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Compiles multiple individual collection files into a single multi-collection dictionary.
    """
    dataset: Dict[str, List[Dict[str, Any]]] = {}
    for filename, content in collection_files:
        col_name, docs = parse_collection_file(filename, content)
        if col_name and docs:
            dataset[col_name] = docs
    return dataset


# ==============================================================================
# Schema Introspection & Context
# ==============================================================================
def get_collection_names(
    collections: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    file_path: Optional[Union[Path, str]] = None,
) -> List[str]:
    """Returns the list of all collection names in this database."""
    if collections is None:
        collections = load_nosql_collections(file_path)
    return list(collections.keys())


def get_total_document_count(collections: Dict[str, List[Dict[str, Any]]]) -> int:
    """Returns the total document count across all collections."""
    return sum(len(docs) for docs in collections.values())


def get_collection_documents(
    collections: Dict[str, List[Dict[str, Any]]],
    collection_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Returns documents for a specific collection or the first available collection."""
    if not collections:
        return []
    if collection_name is not None and collection_name in collections:
        return collections[collection_name]
    # Fallback to case-insensitive match
    if collection_name is not None:
        for k, v in collections.items():
            if k.lower() == collection_name.lower():
                return v
    first_key = list(collections.keys())[0]
    return collections[first_key]


def get_schema_fields(docs: List[Dict[str, Any]], sample_limit: int = 25) -> List[Dict[str, str]]:
    """
    Recursively scans documents to discover all nested field paths and types.
    Returns sorted list of dicts: [{"path": "items[].price", "type": "FLOAT"}].
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
                current_path = f"{prefix}.{k}" if prefix else k
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

    return [{"path": path, "type": dtype} for path, dtype in sorted(field_types.items())]


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
    col_stems_map: Dict[str, set[str]] = {}

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

                if not is_match and target_pk and target_pk.lower() not in ("_id", "id") and f_base == target_pk.lower():
                    is_match = True

                if is_match:
                    target_col_name = (
                        target_pk
                        if target_pk in target_fields
                        else ("_id" if "_id" in target_fields else f_path)
                    )
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
    collections: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    file_path: Optional[Union[Path, str]] = None,
) -> Dict[str, Any]:
    """
    Returns full schema representation matching relational SQL tables structure:
    {"tables": [...], "relationships": [...]}
    """
    if collections is None:
        collections = load_nosql_collections(file_path)

    schema_tables = []
    for col_name in collections.keys():
        fields = get_schema_fields(collections[col_name])
        col_list = [f"{f['path']} ({f['type']})" for f in fields]
        schema_tables.append({
            "name": col_name,
            "cols": col_list,
            "count": len(collections[col_name]),
        })

    relationships = infer_nosql_relationships(collections)
    return {
        "tables": schema_tables,
        "relationships": relationships,
    }


def format_nosql_schema_context(
    collections: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    file_path: Optional[Union[Path, str]] = None,
) -> str:
    """
    Builds a formatted text description of all collections for LLM prompt context,
    including document counts, discovered schema fields, and sample JSON documents.
    """
    if collections is None:
        collections = load_nosql_collections(file_path)

    lines: List[str] = []
    for col_name, docs in collections.items():
        fields = get_schema_fields(docs)
        field_lines = [f"    - {f['path']} ({f['type']})" for f in fields]
        sample = json.dumps(docs[0], indent=2, default=str) if docs else "{}"
        lines.append(f"COLLECTION: {col_name} ({len(docs)} documents)")
        lines.append("  Fields:\n" + "\n".join(field_lines))
        lines.append(f"  Sample Document:\n{sample}\n")

    return "\n".join(lines)


# ==============================================================================
# Pure Functional MQL In-Memory Execution Engine
# ==============================================================================
def get_nested_val(doc: Dict[str, Any], path: str) -> Any:
    """
    Extracts nested value from document using dot notation (e.g. 'address.city' or '$total_amount').
    Gracefully traverses nested dictionaries and lists.
    """
    clean_path = path.lstrip("$")
    parts = clean_path.split(".")
    curr: Any = doc
    for i, p in enumerate(parts):
        if isinstance(curr, dict) and p in curr:
            curr = curr[p]
        elif isinstance(curr, list):
            remaining_path = ".".join(parts[i:])
            return [
                get_nested_val(item, remaining_path)
                for item in curr
                if isinstance(item, dict)
            ]
        else:
            return None
    return curr


def matches_document(doc: Dict[str, Any], filter_spec: Dict[str, Any]) -> bool:
    """
    Evaluates whether a single document satisfies MongoDB MQL filter specifications.
    Supports equality, $eq, $ne, $gt, $gte, $lt, $lte, $in, $nin, $regex, $elemMatch, $and, $or.
    """
    for key, condition in filter_spec.items():
        if key == "$and" and isinstance(condition, list):
            if not all(matches_document(doc, c) for c in condition if isinstance(c, dict)):
                return False
            continue
        elif key == "$or" and isinstance(condition, list):
            if not any(matches_document(doc, c) for c in condition if isinstance(c, dict)):
                return False
            continue

        val = get_nested_val(doc, key)

        if not isinstance(condition, dict):
            if isinstance(val, list):
                if condition not in val:
                    return False
            elif val != condition:
                return False
        else:
            for op, target in condition.items():
                if op == "$eq" and val != target:
                    return False
                elif op == "$ne" and val == target:
                    return False
                elif op == "$gt" and (val is None or val <= target):
                    return False
                elif op == "$gte" and (val is None or val < target):
                    return False
                elif op == "$lt" and (val is None or val >= target):
                    return False
                elif op == "$lte" and (val is None or val > target):
                    return False
                elif op == "$in":
                    if isinstance(val, list):
                        if not any(x in target for x in val):
                            return False
                    elif val not in target:
                        return False
                elif op == "$nin":
                    if isinstance(val, list):
                        if any(x in target for x in val):
                            return False
                    elif val in target:
                        return False
                elif op == "$regex":
                    pattern = str(target)
                    if val is None or not re.search(pattern, str(val), re.IGNORECASE):
                        return False
                elif op == "$elemMatch" and isinstance(val, list):
                    if not any(matches_document(item, target) for item in val if isinstance(item, dict)):
                        return False

    return True


def apply_match(docs: List[Dict[str, Any]], filter_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Filters documents according to MQL filter specification."""
    return [d for d in docs if matches_document(d, filter_spec)]


def apply_group(docs: List[Dict[str, Any]], group_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Executes MongoDB $group stage in memory.
    Supports _id grouping, $sum, $avg, $min, $max, and $count accumulators.
    """
    id_spec = group_spec.get("_id")
    groups: Dict[Any, List[Dict[str, Any]]] = {}

    for d in docs:
        if id_spec is None:
            group_key: Any = None
        elif isinstance(id_spec, str):
            group_key = get_nested_val(d, id_spec)
        else:
            group_key = str(id_spec)

        if isinstance(group_key, list):
            group_key = tuple(group_key)
        if group_key not in groups:
            groups[group_key] = []
        groups[group_key].append(d)

    results: List[Dict[str, Any]] = []
    for g_key, g_docs in groups.items():
        res_doc: Dict[str, Any] = {"_id": list(g_key) if isinstance(g_key, tuple) else g_key}
        for out_field, accum in group_spec.items():
            if out_field == "_id":
                continue
            if isinstance(accum, dict):
                for acc_op, acc_expr in accum.items():
                    if acc_op == "$sum":
                        if isinstance(acc_expr, (int, float)):
                            res_doc[out_field] = len(g_docs) * acc_expr
                        else:
                            raw_vals = [get_nested_val(doc, acc_expr) for doc in g_docs]
                            num_vals: List[Union[int, float]] = []
                            for rv in raw_vals:
                                if isinstance(rv, (int, float)):
                                    num_vals.append(rv)
                                elif isinstance(rv, list):
                                    num_vals.extend([x for x in rv if isinstance(x, (int, float))])
                            res_doc[out_field] = round(sum(num_vals), 2)
                    elif acc_op == "$avg":
                        raw_vals = [get_nested_val(doc, acc_expr) for doc in g_docs]
                        num_vals = []
                        for rv in raw_vals:
                            if isinstance(rv, (int, float)):
                                num_vals.append(rv)
                            elif isinstance(rv, list):
                                num_vals.extend([x for x in rv if isinstance(x, (int, float))])
                        res_doc[out_field] = (
                            round(sum(num_vals) / len(num_vals), 2) if num_vals else 0
                        )
                    elif acc_op == "$min":
                        raw_vals = [get_nested_val(doc, acc_expr) for doc in g_docs]
                        num_vals = [v for v in raw_vals if isinstance(v, (int, float))]
                        res_doc[out_field] = min(num_vals) if num_vals else None
                    elif acc_op == "$max":
                        raw_vals = [get_nested_val(doc, acc_expr) for doc in g_docs]
                        num_vals = [v for v in raw_vals if isinstance(v, (int, float))]
                        res_doc[out_field] = max(num_vals) if num_vals else None
                    elif acc_op == "$count":
                        res_doc[out_field] = len(g_docs)

        results.append(res_doc)
    return results


def _sort_safe_key(val: Any) -> Tuple[int, Any]:
    """Helper to ensure homogeneous tuple comparisons for Python sort."""
    if val is None:
        return (0, "")
    if isinstance(val, (int, float)):
        return (1, val)
    if isinstance(val, str):
        return (2, val)
    return (3, str(val))


def apply_sort(docs: List[Dict[str, Any]], sort_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Executes MongoDB $sort stage in memory with type-safe ordering."""
    if not sort_spec:
        return docs

    sorted_docs = list(docs)
    for field, direction in reversed(list(sort_spec.items())):
        reverse = direction == -1
        sorted_docs.sort(
            key=lambda d: _sort_safe_key(get_nested_val(d, field)),
            reverse=reverse,
        )
    return sorted_docs


def apply_project(docs: List[Dict[str, Any]], project_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Executes MongoDB $project stage in memory."""
    projected: List[Dict[str, Any]] = []
    for d in docs:
        p_doc: Dict[str, Any] = {}
        for field, include in project_spec.items():
            if include == 1 or include is True:
                val = get_nested_val(d, field)
                p_doc[field] = val
        projected.append(p_doc if p_doc else d)
    return projected


def apply_unwind(docs: List[Dict[str, Any]], path_expr: Any) -> List[Dict[str, Any]]:
    """Executes MongoDB $unwind stage in memory."""
    path = path_expr.lstrip("$") if isinstance(path_expr, str) else str(path_expr)
    unwound: List[Dict[str, Any]] = []
    for d in docs:
        arr = get_nested_val(d, path)
        if isinstance(arr, list):
            for item in arr:
                new_d = dict(d)
                new_d[path] = item
                unwound.append(new_d)
        else:
            unwound.append(d)
    return unwound


def execute_mql(
    collections: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    query: Any = None,
    target_collection: Optional[str] = None,
    file_path: Optional[Union[Path, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Executes MongoDB MQL against the specified collection (or first available) in memory.

    Accepts:
    - query: Dict (find filter), List of Dicts (aggregation pipeline), or raw string MQL.
    - target_collection: Collection name to query against.
    """
    if collections is None:
        collections = load_nosql_collections(file_path)

    if not collections:
        return []

    # Parse query if string was provided
    payload: Any = query
    extracted_target: Optional[str] = None

    if isinstance(query, str):
        clean_q = query.strip()
        # Clean markdown fences
        if clean_q.startswith("```"):
            clean_q = re.sub(r"^```(?:json|mql|javascript|js)?\n?", "", clean_q)
            clean_q = re.sub(r"\n?```$", "", clean_q).strip()

        # Extract target collection if db.<col>.(find|aggregate)
        col_match = re.search(r"db\.([a-zA-Z0-9_-]+)\.", clean_q)
        if col_match:
            extracted_target = col_match.group(1)

        # Extract aggregation pipeline db.col.aggregate([ ... ])
        agg_match = re.search(r"db\.[a-zA-Z0-9_-]+\.aggregate\s*\(\s*(\[.*\])\s*\)", clean_q, re.DOTALL)
        if agg_match:
            try:
                payload = json.loads(agg_match.group(1))
            except Exception:
                fixed = re.sub(r'([{\s,])([a-zA-Z0-9_$]+)\s*:', r'\1"\2":', agg_match.group(1)).replace("'", '"')
                payload = json.loads(fixed)
        else:
            # Extract find payload db.col.find({ ... })
            find_match = re.search(r"db\.[a-zA-Z0-9_-]+\.find\s*\(\s*(\{.*\})\s*\)", clean_q, re.DOTALL)
            if find_match:
                try:
                    payload = json.loads(find_match.group(1))
                except Exception:
                    fixed = re.sub(r'([{\s,])([a-zA-Z0-9_$]+)\s*:', r'\1"\2":', find_match.group(1)).replace("'", '"')
                    payload = json.loads(fixed)
            else:
                # Raw JSON array or object
                try:
                    payload = json.loads(clean_q)
                except Exception:
                    pass

    # Resolve target collection
    target = target_collection or extracted_target
    available_cols = list(collections.keys())

    if target is None or target not in collections:
        # Check case-insensitive match
        matched_target = None
        if target is not None:
            for k in available_cols:
                if k.lower() == target.lower():
                    matched_target = k
                    break
        target = matched_target or (available_cols[0] if available_cols else "default")

    docs = [dict(d) for d in collections.get(target, [])]

    if isinstance(payload, dict):
        return apply_match(docs, payload)[:100]

    elif isinstance(payload, list):
        current_docs = docs
        for stage in payload:
            if not isinstance(stage, dict):
                continue
            for op, params in stage.items():
                if op == "$match" and isinstance(params, dict):
                    current_docs = apply_match(current_docs, params)
                elif op == "$group" and isinstance(params, dict):
                    current_docs = apply_group(current_docs, params)
                elif op == "$sort" and isinstance(params, dict):
                    current_docs = apply_sort(current_docs, params)
                elif op == "$project" and isinstance(params, dict):
                    current_docs = apply_project(current_docs, params)
                elif op == "$limit" and isinstance(params, int):
                    current_docs = current_docs[:params]
                elif op == "$unwind":
                    current_docs = apply_unwind(current_docs, params)
                elif op == "$count":
                    count_field = params if isinstance(params, str) else "count"
                    current_docs = [{count_field: len(current_docs)}]

        return current_docs[:100]

    return docs[:10]
