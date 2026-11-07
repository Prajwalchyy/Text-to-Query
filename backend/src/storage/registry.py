"""
Dataset Registry Storage Module.

Provides pure functional persistence and lifecycle management for multi-format datasets:
- Relational SQLite databases (.db, .sqlite, .sql)
- NoSQL document databases (.json, .jsonl, .bson)
- Tabular spreadsheets (.csv, .xlsx, .xls)
Zero OOP classes; pure functions with immutable state where practical.
"""

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    ALL_MANAGED_DIRS,
    CSV_DIR,
    DEFAULT_CHINOOK_PATH,
    DEFAULT_CSV_PATH,
    DEFAULT_EXCEL_PATH,
    DEFAULT_NOSQL_PATH,
    EXCEL_DIR,
    NOSQL_DIR,
    REGISTRY_FILE,
    RELATIONAL_DIR,
    UPLOADS_DIR,
    ensure_directories,
)


class TableConflictError(Exception):
    """Raised when an appended SQL table script collides with an existing table."""
    def __init__(self, conflicts: List[str]):
        self.conflicts = conflicts
        super().__init__(f"Table(s) already exist: {', '.join(conflicts)}")


class CollectionConflictError(Exception):
    """Raised when an appended NoSQL collection collides with an existing collection."""
    def __init__(self, conflicts: List[str]):
        self.conflicts = conflicts
        super().__init__(f"Collection(s) already exist: {', '.join(conflicts)}")


def get_upload_dir_for_type(
    dataset_type: Optional[str] = None,
    file_ext: str = "",
    upload_mode: str = "single",
    group_folder: str = "",
) -> Path:
    """
    Returns the categorized storage directory under data/:
    - Single dataset upload: data/{type}/single/
    """
    ext = file_ext.lower()
    if dataset_type == "sql" or ext in [".db", ".sqlite", ".sqlite3", ".sql"]:
        base_dir = RELATIONAL_DIR
    elif dataset_type == "nosql" or ext in [".json", ".jsonl", ".bson"]:
        base_dir = NOSQL_DIR
    elif dataset_type == "csv" or ext in [".csv", ".tsv", ".parquet"]:
        base_dir = CSV_DIR
    elif dataset_type == "excel" or ext in [".xlsx", ".xls"]:
        base_dir = EXCEL_DIR
    else:
        base_dir = RELATIONAL_DIR

    target = base_dir / "single"
    target.mkdir(parents=True, exist_ok=True)
    return target


# ==============================================================================
# Inspection Helpers (Stateless)
# ==============================================================================
def count_sqlite_tables(db_path: Path | str) -> int:
    """Counts user-defined tables in a SQLite database file."""
    try:
        path = Path(db_path).resolve()
        conn = sqlite3.connect(str(path))
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def count_csv_rows(csv_path: Path | str) -> int:
    """Counts data rows in a CSV, TSV, or Parquet file (excluding header)."""
    try:
        path = Path(csv_path).resolve()
        ext = path.suffix.lower()
        if ext == ".parquet":
            import pyarrow.parquet as pq
            return pq.read_metadata(str(path)).num_rows
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [line for line in f if line.strip()]
            return max(0, len(lines) - 1)
    except Exception:
        return 0


def count_csv_columns(csv_path: Path | str) -> int:
    """Counts columns in a CSV, TSV, or Parquet file."""
    try:
        path = Path(csv_path).resolve()
        ext = path.suffix.lower()
        if ext == ".parquet":
            import pyarrow.parquet as pq
            return pq.read_metadata(str(path)).num_columns
        sep = "\t" if ext == ".tsv" else ","
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line:
                    import csv
                    reader = csv.reader([line], delimiter=sep)
                    row = next(reader)
                    return len(row)
        return 0
    except Exception:
        return 0


def inspect_excel_workbook(excel_path: Path | str) -> Dict[str, Any]:
    """Inspects sheet names, row counts, and column counts for an Excel workbook."""
    try:
        import openpyxl
        path = Path(excel_path).resolve()
        wb = openpyxl.load_workbook(str(path), read_only=True)
        sheets = wb.sheetnames
        total_rows = 0
        total_columns = 0
        sheet_details = []
        for name in sheets:
            ws = wb[name]
            r = ws.max_row or 0
            c = ws.max_column or 0
            data_rows = max(0, r - 1)
            total_rows += data_rows
            if len(sheets) == 1:
                total_columns = c
            sheet_details.append({"name": name, "rows": data_rows, "columns": c})
        wb.close()
        return {
            "sheets": sheets,
            "total_rows": total_rows,
            "column_count": total_columns,
            "sheet_details": sheet_details
        }
    except Exception:
        return {"sheets": [], "total_rows": 0, "column_count": 0, "sheet_details": []}


def count_json_docs(json_path: Path | str) -> int:
    """Counts documents in a JSON, JSONL, or BSON file."""
    path = Path(json_path).resolve()
    ext = path.suffix.lower()

    if ext == ".bson":
        try:
            import bson
            with open(path, "rb") as f:
                docs = bson.decode_all(f.read())
                return len(docs)
        except Exception:
            return 0

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return 0
            if content.startswith("["):
                return len(json.loads(content))
            elif content.startswith("{"):
                data = json.loads(content)
                return sum(len(v) for v in data.values() if isinstance(v, list))
            else:
                return len([line for line in content.splitlines() if line.strip()])
    except Exception:
        return 0


def count_json_tables(json_path: Path | str) -> int:
    """Counts distinct collections/tables in a JSON, JSONL, or BSON file."""
    path = Path(json_path).resolve()
    ext = path.suffix.lower()

    if ext in [".bson", ".jsonl"]:
        return 1

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return 1
            if content.startswith("{"):
                data = json.loads(content)
                tables = [k for k, v in data.items() if isinstance(v, (list, dict))]
                return len(tables) if tables else 1
            return 1
    except Exception:
        return 1


# ==============================================================================
# Low-Level File Persistence
# ==============================================================================
def read_registry() -> List[Dict[str, Any]]:
    """Reads and parses the databases.json file safely."""
    ensure_directories()
    if not REGISTRY_FILE.exists():
        return init_default_registry()

    try:
        content = REGISTRY_FILE.read_text(encoding="utf-8").strip()
        if not content:
            return init_default_registry()
        dbs = json.loads(content)
        # Ensure default datasets are always registered
        return _ensure_defaults_present(dbs)
    except (json.JSONDecodeError, OSError):
        return init_default_registry()


def write_registry(data: List[Dict[str, Any]]) -> None:
    """Safely writes formatted database metadata to databases.json."""
    ensure_directories()
    REGISTRY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _ensure_defaults_present(dbs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Guarantees protected system defaults exist in registry list."""
    existing_ids = {d["id"] for d in dbs}
    updated = False

    # 1. Chinook
    if "chinook" not in existing_ids and DEFAULT_CHINOOK_PATH.exists():
        dbs.append({
            "id": "chinook",
            "name": "Chinook (Music)",
            "type": "sql",
            "filename": "chinook.db",
            "path": str(DEFAULT_CHINOOK_PATH.resolve()),
            "table_count": count_sqlite_tables(DEFAULT_CHINOOK_PATH),
            "is_default": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        updated = True

    # 2. E-Commerce NoSQL
    if "ecommerce_store" not in existing_ids and DEFAULT_NOSQL_PATH.exists():
        dbs.append({
            "id": "ecommerce_store",
            "name": "E-Commerce Store (NoSQL)",
            "type": "nosql",
            "filename": "ecommerce_store.json",
            "path": str(DEFAULT_NOSQL_PATH.resolve()),
            "table_count": count_json_tables(DEFAULT_NOSQL_PATH),
            "doc_count": count_json_docs(DEFAULT_NOSQL_PATH),
            "row_count": count_json_docs(DEFAULT_NOSQL_PATH),
            "is_default": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        updated = True

    # 3. Sales Performance CSV
    if "sales_performance" not in existing_ids and DEFAULT_CSV_PATH.exists():
        dbs.append({
            "id": "sales_performance",
            "name": "Sales Performance (CSV)",
            "type": "csv",
            "filename": "sales_performance.csv",
            "path": str(DEFAULT_CSV_PATH.resolve()),
            "row_count": count_csv_rows(DEFAULT_CSV_PATH),
            "column_count": count_csv_columns(DEFAULT_CSV_PATH),
            "table_count": 1,
            "is_default": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        updated = True

    # 4. Financial Budget Excel
    if "financial_budget" not in existing_ids and DEFAULT_EXCEL_PATH.exists():
        sheet_info = inspect_excel_workbook(DEFAULT_EXCEL_PATH)
        dbs.append({
            "id": "financial_budget",
            "name": "Financial Budget (Excel)",
            "type": "excel",
            "filename": "financial_budget.xlsx",
            "path": str(DEFAULT_EXCEL_PATH.resolve()),
            "sheet_count": len(sheet_info.get("sheets", [])),
            "sheets": sheet_info.get("sheets", []),
            "table_count": len(sheet_info.get("sheets", [])),
            "row_count": sheet_info.get("total_rows", 0),
            "column_count": sheet_info.get("column_count", 0),
            "is_default": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        updated = True

    if updated:
        write_registry(dbs)

    return dbs


def init_default_registry() -> List[Dict[str, Any]]:
    """Initializes the database registry with all system defaults."""
    dbs: List[Dict[str, Any]] = []
    dbs = _ensure_defaults_present(dbs)
    write_registry(dbs)
    return dbs


# ==============================================================================
# Public Registry CRUD API
# ==============================================================================
def list_databases() -> List[Dict[str, Any]]:
    """Returns all registered data sources (SQL, NoSQL, CSV, Excel)."""
    return read_registry()


def get_database(db_id: str) -> Optional[Dict[str, Any]]:
    """Finds a registered data source entry by its unique ID."""
    dbs = read_registry()
    return next((d for d in dbs if d["id"] == db_id), None)


def register_database(
    name: str,
    file_path: Path,
    filename: str,
    upload_mode: str = "single",
    group_name: Optional[str] = None,
    group_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validates uploaded file (.db/.sql for SQL, .json/.bson for NoSQL, .csv/.xlsx)
    and registers it with metadata.
    """
    ext = filename.lower()
    is_csv = ext.endswith((".csv", ".tsv", ".parquet"))
    is_excel = ext.endswith((".xlsx", ".xls"))
    is_nosql = ext.endswith((".json", ".jsonl", ".bson"))
    clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', name.strip().lower())
    db_id = f"{clean_name}_{int(datetime.now(timezone.utc).timestamp())}"

    if is_csv:
        row_count = count_csv_rows(file_path)
        col_count = count_csv_columns(file_path)
        new_entry = {
            "id": db_id,
            "name": name.strip(),
            "type": "csv",
            "filename": filename,
            "path": str(file_path.resolve()),
            "upload_mode": upload_mode,
            "group_name": group_name,
            "group_id": group_id,
            "row_count": row_count,
            "column_count": col_count,
            "table_count": 1,
            "is_default": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    elif is_excel:
        sheet_info = inspect_excel_workbook(file_path)
        new_entry = {
            "id": db_id,
            "name": name.strip(),
            "type": "excel",
            "filename": filename,
            "path": str(file_path.resolve()),
            "upload_mode": upload_mode,
            "group_name": group_name,
            "group_id": group_id,
            "sheet_count": len(sheet_info.get("sheets", [])),
            "sheets": sheet_info.get("sheets", []),
            "table_count": len(sheet_info.get("sheets", [])),
            "row_count": sheet_info.get("total_rows", 0),
            "column_count": sheet_info.get("column_count", 0),
            "is_default": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    elif is_nosql:
        doc_count = count_json_docs(file_path)
        if doc_count == 0:
            raise ValueError("The uploaded NoSQL file is empty or contains invalid JSON/BSON documents.")
        table_count = count_json_tables(file_path)

        new_entry = {
            "id": db_id,
            "name": name.strip(),
            "type": "nosql",
            "filename": filename,
            "path": str(file_path.resolve()),
            "upload_mode": upload_mode,
            "group_name": group_name,
            "group_id": group_id,
            "table_count": table_count,
            "doc_count": doc_count,
            "row_count": doc_count,
            "is_default": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    else:
        # Check if this is a .sql script file
        resolved_file_path = file_path
        if filename.lower().endswith(".sql"):
            compiled_db_path = file_path.with_suffix(".db")
            try:
                sql_script = file_path.read_text(encoding="utf-8", errors="ignore")
                conn = sqlite3.connect(str(compiled_db_path.resolve()))
                conn.executescript(sql_script)
                conn.commit()
                conn.close()
                resolved_file_path = compiled_db_path
            except Exception as e:
                raise ValueError(f"Failed to execute SQL script into database: {str(e)}")

        # Validate SQLite format
        try:
            conn = sqlite3.connect(str(resolved_file_path.resolve()))
            cursor = conn.cursor()
            cursor.execute("PRAGMA schema_version;")
            cursor.fetchone()
            conn.close()
        except Exception as e:
            raise ValueError(f"Invalid SQLite database file: {str(e)}")

        table_count = count_sqlite_tables(resolved_file_path)
        if table_count == 0:
            raise ValueError("The uploaded database contains 0 valid tables.")

        new_entry = {
            "id": db_id,
            "name": name.strip(),
            "type": "sql",
            "filename": resolved_file_path.name,
            "path": str(resolved_file_path.resolve()),
            "upload_mode": upload_mode,
            "group_name": group_name,
            "group_id": group_id,
            "table_count": table_count,
            "is_default": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    dbs = read_registry()
    dbs.append(new_entry)
    write_registry(dbs)
    return new_entry


def delete_database(db_id: str) -> bool:
    """Deletes a custom user data source (cannot delete protected system defaults)."""
    dbs = read_registry()
    target = next((d for d in dbs if d["id"] == db_id), None)

    if not target or target.get("is_default") is True:
        return False

    # Safely remove physical file if located in managed upload directories
    file_path = Path(target["path"])
    managed_parents = [RELATIONAL_DIR, NOSQL_DIR, CSV_DIR, EXCEL_DIR, UPLOADS_DIR]
    if file_path.exists() and any(p in file_path.parents for p in managed_parents):
        try:
            file_path.unlink()
        except OSError:
            pass

    dbs = [d for d in dbs if d["id"] != db_id]
    write_registry(dbs)
    return True


def check_table_conflict(db_path: Path | str, sql_script: str) -> List[str]:
    """Detects table name collisions in an SQLite database against a CREATE TABLE script."""
    path = Path(db_path).resolve()
    pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?["`]?([a-zA-Z0-9_]+)["`]?'
    tables_to_create = list(set(re.findall(pattern, sql_script, re.IGNORECASE)))

    conn = sqlite3.connect(str(path))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    existing_tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    conflicts = []
    for t in tables_to_create:
        for existing in existing_tables:
            if t.lower() == existing.lower():
                conflicts.append(existing)
                break
    return conflicts


def append_table_to_database(db_id: str, sql_script: str, overwrite: bool = False) -> Dict[str, Any]:
    """
    Executes an additional .sql table script into an existing custom SQL database.
    Checks for collisions; raises TableConflictError if overwrite is False.
    """
    entry = get_database(db_id)
    if not entry:
        raise ValueError(f"Database with ID '{db_id}' not found.")
    if entry.get("is_default") is True:
        raise ValueError("Cannot modify system default databases.")
    if entry.get("type") != "sql":
        raise ValueError("Tables can only be appended to SQL relational databases.")

    db_path = Path(entry["path"]).resolve()
    if not db_path.exists():
        raise ValueError(f"Database file '{db_path.name}' does not exist on disk.")

    conflicts = check_table_conflict(db_path, sql_script)
    if conflicts and not overwrite:
        raise TableConflictError(conflicts=conflicts)

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        if conflicts and overwrite:
            for conflict in conflicts:
                cursor.execute(f'DROP TABLE IF EXISTS "{conflict}";')
            conn.commit()

        conn.executescript(sql_script)
        conn.commit()
    except Exception as e:
        raise ValueError(f"Failed to execute SQL table script into database: {str(e)}")
    finally:
        conn.close()

    new_table_count = count_sqlite_tables(db_path)
    entry["table_count"] = new_table_count

    dbs = read_registry()
    for i, d in enumerate(dbs):
        if d["id"] == db_id:
            dbs[i]["table_count"] = new_table_count
            break
    write_registry(dbs)
    return entry


def append_collection_to_database(
    db_id: str,
    collection_name: str,
    documents: List[Dict[str, Any]],
    overwrite: bool = False,
) -> Dict[str, Any]:
    """
    Appends an additional collection to an existing custom NoSQL database.
    Checks for collisions; raises CollectionConflictError if overwrite is False.
    """
    entry = get_database(db_id)
    if not entry:
        raise ValueError(f"Database with ID '{db_id}' not found.")
    if entry.get("is_default") is True:
        raise ValueError("Cannot modify system default databases.")
    if entry.get("type") != "nosql":
        raise ValueError("Collections can only be appended to NoSQL document databases.")

    db_path = Path(entry["path"]).resolve()
    if not db_path.exists():
        raise ValueError(f"Database file '{db_path.name}' does not exist on disk.")

    # Load existing collections
    collections: Dict[str, List[Dict[str, Any]]] = {}
    content = db_path.read_text(encoding="utf-8").strip()
    if content:
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                collections = {k: (v if isinstance(v, list) else [v]) for k, v in parsed.items()}
            elif isinstance(parsed, list):
                collections = {entry.get("name", "main"): parsed}
        except json.JSONDecodeError:
            collections = {}

    matched_key = next((k for k in collections.keys() if k.lower() == collection_name.lower()), None)

    if matched_key and not overwrite:
        raise CollectionConflictError(conflicts=[matched_key])

    target_key = matched_key if matched_key else collection_name
    collections[target_key] = documents

    db_path.write_text(json.dumps(collections, indent=2, ensure_ascii=False), encoding="utf-8")
    new_doc_count = sum(len(docs) for docs in collections.values())
    entry["doc_count"] = new_doc_count

    dbs = read_registry()
    for i, d in enumerate(dbs):
        if d["id"] == db_id:
            dbs[i]["doc_count"] = new_doc_count
            break
    write_registry(dbs)
    return entry


def check_collection_conflict(db_path: Path | str, collection_name: str) -> List[str]:
    """Checks whether a collection already exists in a NoSQL database file."""
    path = Path(db_path).resolve()
    if not path.exists():
        return []
    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return []
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            for k in parsed.keys():
                if k.lower() == collection_name.lower():
                    return [k]
    except Exception:
        pass
    return []


# ==============================================================================
# Backward-Compatible Function Aliases
# ==============================================================================
list_registered_databases = list_databases
get_database_by_id = get_database
delete_registered_database = delete_database


