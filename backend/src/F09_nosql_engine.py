import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

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

    def get_all_relationships(self) -> List[Dict[str, Any]]:
        """
        Dynamically infers relationships across NoSQL collections by detecting
        reference keys (e.g. member_id -> members, course_id -> courses, customer_id -> customers).
        """
        relationships = []
        col_names = self.get_collection_names()
        if len(col_names) <= 1:
            return []

        # Build map of collection names to schema fields, candidate PKs, and word stems
        col_fields_map = {}
        col_pk_map = {}
        col_stems_map = {}

        for c_name in col_names:
            fields = self.get_schema_fields(c_name)
            field_paths = [f["path"] for f in fields]
            col_fields_map[c_name] = field_paths

            # Generate possible root stems for collection name
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

            # Determine primary key for this collection
            pk = None
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

        # Detect cross-collection references
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
                        if f_base == f"{stem}_id" or f_base == f"id_{stem}" or f_base == stem:
                            is_match = True
                            break

                    # Also check if field matches target's specific primary key (e.g. course_id in enrollments)
                    if not is_match and target_pk and target_pk.lower() not in ("_id", "id") and f_base == target_pk.lower():
                        is_match = True

                    if is_match:
                        target_col_name = target_pk if target_pk in target_fields else ("_id" if "_id" in target_fields else f_path)
                        rel = {
                            "from_table": c_name,
                            "from_col": f_path,
                            "to_table": target_col,
                            "to_col": target_col_name
                        }
                        if rel not in relationships:
                            relationships.append(rel)

        return relationships

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

    @staticmethod
    def parse_collection_file(filename: str, content: bytes) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Parses an individual .json, .jsonl, or .bson collection file into (collection_name, documents).
        Uses file stem as the collection name (e.g. 'customers.json' -> 'customers').
        """
        path = Path(filename)
        col_name = path.stem.lower().replace("-", "_").replace(" ", "_")
        ext = path.suffix.lower()

        if ext == ".bson":
            import bson
            raw_docs = bson.decode_all(content)
            safe_docs = [NoSQLEngine._normalize_bson_doc(d) for d in raw_docs]
            return col_name, safe_docs

        if ext == ".jsonl":
            text = content.decode("utf-8", errors="ignore")
            docs = []
            for line in text.splitlines():
                l = line.strip()
                if l != "":
                    docs.append(json.loads(l))
            return col_name, docs

        # Default .json
        text = content.decode("utf-8", errors="ignore")
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return col_name, parsed
        elif isinstance(parsed, dict):
            # If the json is a dictionary mapping collection_name -> documents
            has_nested_lists = any(isinstance(v, list) for v in parsed.values())
            if has_nested_lists == True:
                # Return the collection name matching filename or first list
                if col_name in parsed and isinstance(parsed[col_name], list):
                    return col_name, parsed[col_name]
                for k, v in parsed.items():
                    if isinstance(v, list):
                        return k, v
            return col_name, [parsed]
        return col_name, []

    @staticmethod
    def compile_collections_to_dataset(collection_files: List[Tuple[str, bytes]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Compiles multiple individual collection files into a single multi-collection dictionary.
        """
        dataset = {}
        for filename, content in collection_files:
            col_name, docs = NoSQLEngine.parse_collection_file(filename, content)
            dataset[col_name] = docs
        return dataset
