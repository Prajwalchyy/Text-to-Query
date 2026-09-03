import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class NoSQLEngine:
    """
    In-Memory Multi-Collection NoSQL Document Database Engine.
    Supports databases containing multiple collections (like SQL tables),
    dynamically introspects nested schemas for each collection, and executes
    MongoDB MQL aggregation pipelines and find() queries locally.
    """

    def __init__(self, file_path: Optional[str] = None):
        if file_path == None or file_path == "":
            default_path = PROJECT_ROOT / "data" / "nosql_default" / "ecommerce_store.json"
            self.file_path = default_path
        else:
            self.file_path = Path(file_path).resolve()

        self.collections: Dict[str, List[Dict[str, Any]]] = {}
        self._load_database()

    @staticmethod
    def _normalize_bson_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
        """Converts BSON specific types (ObjectId, datetime, bytes) to JSON-serializable primitives."""
        normalized = {}
        for k, v in doc.items():
            if hasattr(v, '__str__') and type(v).__name__ == 'ObjectId':
                normalized[k] = str(v)
            elif hasattr(v, 'isoformat'):
                normalized[k] = v.isoformat()
            elif isinstance(v, bytes):
                normalized[k] = v.hex()
            elif isinstance(v, dict):
                normalized[k] = NoSQLEngine._normalize_bson_doc(v)
            elif isinstance(v, list):
                normalized[k] = [NoSQLEngine._normalize_bson_doc(item) if isinstance(item, dict) else (str(item) if hasattr(item, '__str__') and type(item).__name__ == 'ObjectId' else item) for item in v]
            else:
                normalized[k] = v
        return normalized

    def _load_database(self):
        """Loads and parses JSON, JSONL, or BSON collections from disk."""
        if self.file_path.exists() == False:
            self.collections = {}
            return

        ext = self.file_path.suffix.lower()

        # 1. Native MongoDB BSON Format (.bson)
        if ext == ".bson":
            try:
                import bson
                with open(self.file_path, "rb") as f:
                    raw_bytes = f.read()
                    if len(raw_bytes) == 0:
                        self.collections = {}
                        return
                    docs = bson.decode_all(raw_bytes)
                    safe_docs = [self._normalize_bson_doc(d) for d in docs]
                    col_name = self.file_path.stem
                    self.collections = {col_name: safe_docs}
            except Exception:
                self.collections = {}
            return

        # 2. JSON Lines Format (.jsonl)
        if ext == ".jsonl":
            try:
                docs = []
                with open(self.file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        if line_str != "":
                            docs.append(json.loads(line_str))
                col_name = self.file_path.stem
                self.collections = {col_name: docs}
            except Exception:
                self.collections = {}
            return

        # 3. Standard JSON Format (.json)
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content == "":
                    self.collections = {}
                    return

                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    # Multi-Collection format: { "orders": [...], "customers": [...], "products": [...] }
                    self.collections = {}
                    for k, v in parsed.items():
                        if isinstance(v, list):
                            self.collections[k] = v
                        elif isinstance(v, dict):
                            self.collections[k] = [v]
                elif isinstance(parsed, list):
                    # Single Collection format: [ { ... }, { ... } ]
                    col_name = self.file_path.stem
                    self.collections = {col_name: parsed}
                else:
                    self.collections = {}
        except Exception:
            self.collections = {}

    def get_collection_names(self) -> List[str]:
        """Returns the list of all collection names in this database."""
        return list(self.collections.keys())

    def get_total_document_count(self) -> int:
        """Returns the total document count across all collections."""
        return sum(len(docs) for docs in self.collections.values())

    def get_collection_documents(self, collection_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns documents for a specific collection or first collection."""
        if collection_name != None and collection_name in self.collections:
            return self.collections[collection_name]
        if len(self.collections) > 0:
            first_key = list(self.collections.keys())[0]
            return self.collections[first_key]
        return []

    def get_schema_fields(self, collection_name: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Recursively scans documents for a specific collection to discover all nested field paths and types.
        """
        docs = self.get_collection_documents(collection_name)
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

        def _walk(obj: Any, prefix: str = ""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    current_path = f"{prefix}.{k}" if prefix != "" else k
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

        for doc in docs[:25]:
            _walk(doc)

        return [{"path": path, "type": dtype} for path, dtype in sorted(field_types.items())]

    def get_all_tables_schema(self) -> List[Dict[str, Any]]:
        """
        Returns full schema representation for all collections (matching SQL tables structure).
        """
        schema_data = []
        for col_name in self.get_collection_names():
            fields = self.get_schema_fields(col_name)
            col_list = [f"{f['path']} ({f['type']})" for f in fields]
            schema_data.append({
                "name": col_name,
                "cols": col_list,
                "count": len(self.collections.get(col_name, []))
            })
        return schema_data

    def get_all_schemas_context(self) -> str:
        """Builds a formatted text description of all collections for LLM prompt context."""
        lines = []
        for col_name in self.get_collection_names():
            docs = self.collections.get(col_name, [])
            fields = self.get_schema_fields(col_name)
            field_lines = [f"    - {f['path']} ({f['type']})" for f in fields]
            sample = json.dumps(docs[0], indent=2) if len(docs) > 0 else "{}"
            lines.append(f"COLLECTION: {col_name} ({len(docs)} documents)")
            lines.append("  Fields:\n" + "\n".join(field_lines))
            lines.append(f"  Sample Document:\n{sample}\n")
        return "\n".join(lines)

    def execute_mql(self, query_payload: Any, target_collection: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Executes MongoDB MQL against the specified collection (or first available).
        """
        target = target_collection
        if target == None or target not in self.collections:
            target = list(self.collections.keys())[0] if len(self.collections) > 0 else "default"

        docs = [dict(d) for d in self.collections.get(target, [])]

        if isinstance(query_payload, dict):
            return self._apply_match(docs, query_payload)

        elif isinstance(query_payload, list):
            current_docs = docs
            for stage in query_payload:
                if not isinstance(stage, dict):
                    continue
                for op, params in stage.items():
                    if op == "$match":
                        current_docs = self._apply_match(current_docs, params)
                    elif op == "$group":
                        current_docs = self._apply_group(current_docs, params)
                    elif op == "$sort":
                        current_docs = self._apply_sort(current_docs, params)
                    elif op == "$project":
                        current_docs = self._apply_project(current_docs, params)
                    elif op == "$limit":
                        if isinstance(params, int):
                            current_docs = current_docs[:params]
                    elif op == "$unwind":
                        current_docs = self._apply_unwind(current_docs, params)
                    elif op == "$count":
                        count_field = params if isinstance(params, str) else "count"
                        current_docs = [{count_field: len(current_docs)}]

            return current_docs[:100]

        return docs[:10]

    # --------------------------------------------------------------------------
    # MQL Helpers
    # --------------------------------------------------------------------------
    def _get_nested_val(self, doc: Dict[str, Any], path: str) -> Any:
        clean_path = path.lstrip("$")
        parts = clean_path.split(".")
        curr = doc
        for p in parts:
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            elif isinstance(curr, list):
                return [self._get_nested_val(item, ".".join(parts[parts.index(p):])) for item in curr if isinstance(item, dict)]
            else:
                return None
        return curr

    def _apply_match(self, docs: List[Dict[str, Any]], filter_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        matched = []
        for d in docs:
            if self._matches_doc(d, filter_spec) == True:
                matched.append(d)
        return matched

    def _matches_doc(self, doc: Dict[str, Any], filter_spec: Dict[str, Any]) -> bool:
        for key, condition in filter_spec.items():
            if key == "$and" and isinstance(condition, list):
                if all(self._matches_doc(doc, c) for c in condition) == False:
                    return False
                continue
            elif key == "$or" and isinstance(condition, list):
                if any(self._matches_doc(doc, c) for c in condition) == False:
                    return False
                continue

            val = self._get_nested_val(doc, key)

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
                    elif op == "$gt" and (val == None or val <= target):
                        return False
                    elif op == "$gte" and (val == None or val < target):
                        return False
                    elif op == "$lt" and (val == None or val >= target):
                        return False
                    elif op == "$lte" and (val == None or val > target):
                        return False
                    elif op == "$in" and (val not in target if not isinstance(val, list) else not any(x in target for x in val)):
                        return False
                    elif op == "$nin" and val in target:
                        return False
                    elif op == "$regex":
                        pattern = target
                        if val == None or not re.search(pattern, str(val), re.IGNORECASE):
                            return False
                    elif op == "$elemMatch" and isinstance(val, list):
                        if not any(self._matches_doc(item, target) for item in val if isinstance(item, dict)):
                            return False
        return True

    def _apply_group(self, docs: List[Dict[str, Any]], group_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        id_spec = group_spec.get("_id")
        groups: Dict[Any, List[Dict[str, Any]]] = {}

        for d in docs:
            group_key = self._get_nested_val(d, id_spec) if isinstance(id_spec, str) else str(id_spec)
            if isinstance(group_key, list):
                group_key = tuple(group_key)
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(d)

        results = []
        for g_key, g_docs in groups.items():
            res_doc: Dict[str, Any] = {"_id": g_key if not isinstance(g_key, tuple) else list(g_key)}
            for out_field, accum in group_spec.items():
                if out_field == "_id":
                    continue
                if isinstance(accum, dict):
                    for acc_op, acc_expr in accum.items():
                        if acc_op == "$sum":
                            if isinstance(acc_expr, (int, float)):
                                res_doc[out_field] = len(g_docs) * acc_expr
                            else:
                                vals = [self._get_nested_val(doc, acc_expr) for doc in g_docs]
                                num_vals = [v for v in vals if isinstance(v, (int, float))]
                                res_doc[out_field] = round(sum(num_vals), 2)
                        elif acc_op == "$avg":
                            vals = [self._get_nested_val(doc, acc_expr) for doc in g_docs]
                            num_vals = [v for v in vals if isinstance(v, (int, float))]
                            res_doc[out_field] = round(sum(num_vals) / len(num_vals), 2) if len(num_vals) > 0 else 0
                        elif acc_op == "$min":
                            vals = [self._get_nested_val(doc, acc_expr) for doc in g_docs]
                            num_vals = [v for v in vals if isinstance(v, (int, float))]
                            res_doc[out_field] = min(num_vals) if len(num_vals) > 0 else None
                        elif acc_op == "$max":
                            vals = [self._get_nested_val(doc, acc_expr) for doc in g_docs]
                            num_vals = [v for v in vals if isinstance(v, (int, float))]
                            res_doc[out_field] = max(num_vals) if len(num_vals) > 0 else None
                        elif acc_op == "$count":
                            res_doc[out_field] = len(g_docs)

            results.append(res_doc)
        return results

    def _apply_sort(self, docs: List[Dict[str, Any]], sort_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not sort_spec:
            return docs

        sorted_docs = list(docs)
        for field, direction in reversed(list(sort_spec.items())):
            reverse = True if direction == -1 else False
            sorted_docs.sort(
                key=lambda d: (self._get_nested_val(d, field) is None, self._get_nested_val(d, field)),
                reverse=reverse
            )
        return sorted_docs

    def _apply_project(self, docs: List[Dict[str, Any]], project_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        projected = []
        for d in docs:
            p_doc = {}
            for field, include in project_spec.items():
                if include == 1 or include == True:
                    val = self._get_nested_val(d, field)
                    p_doc[field] = val
            projected.append(p_doc if len(p_doc) > 0 else d)
        return projected

    def _apply_unwind(self, docs: List[Dict[str, Any]], path_expr: Any) -> List[Dict[str, Any]]:
        path = path_expr.lstrip("$") if isinstance(path_expr, str) else str(path_expr)
        unwound = []
        for d in docs:
            arr = self._get_nested_val(d, path)
            if isinstance(arr, list):
                for item in arr:
                    new_d = dict(d)
                    new_d[path] = item
                    unwound.append(new_d)
            else:
                unwound.append(d)
        return unwound
