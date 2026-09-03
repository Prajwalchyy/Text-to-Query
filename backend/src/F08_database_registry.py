import json
import sqlite3
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RELATIONAL_DIR = DATA_DIR / "relational"
NOSQL_DIR = DATA_DIR / "nosql"
CSV_DIR = DATA_DIR / "csv"
EXCEL_DIR = DATA_DIR / "excel"
UPLOADS_DIR = DATA_DIR / "uploads"  # legacy compatibility

MANAGED_UPLOAD_DIRS = [RELATIONAL_DIR, NOSQL_DIR, CSV_DIR, EXCEL_DIR, UPLOADS_DIR]
REGISTRY_FILE = DATA_DIR / "databases.json"
DEFAULT_CHINOOK = DATA_DIR / "chinook.db"
DEFAULT_NOSQL = DATA_DIR / "nosql_default" / "ecommerce_store.json"


def get_upload_dir_for_type(dataset_type: Optional[str] = None, file_ext: str = "") -> Path:
    """
    Returns the appropriate categorized storage directory under data/:
    - 'sql' (.db, .sqlite, .sqlite3, .sql) -> data/relational
    - 'nosql' (.json, .jsonl) -> data/nosql
    - 'csv' (.csv) -> data/csv
    - 'excel' (.xlsx, .xls) -> data/excel
    """
    ext = file_ext.lower()
    if dataset_type == "sql" or ext in [".db", ".sqlite", ".sqlite3", ".sql"]:
        target = RELATIONAL_DIR
    elif dataset_type == "nosql" or ext in [".json", ".jsonl"]:
        target = NOSQL_DIR
    elif dataset_type == "csv" or ext == ".csv":
        target = CSV_DIR
    elif dataset_type == "excel" or ext in [".xlsx", ".xls"]:
        target = EXCEL_DIR
    else:
        target = RELATIONAL_DIR

    target.mkdir(parents=True, exist_ok=True)
    return target


class DatabaseRegistry:
    """
    Manages multi-format data sources (Relational SQLite Databases, NoSQL JSON Collections, CSV, Excel).
    Enables users to upload, name, and switch between SQL and NoSQL data sources.
    """
    def __init__(self, registry_file: Path = REGISTRY_FILE):
        self.registry_file = registry_file
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        for d in MANAGED_UPLOAD_DIRS:
            d.mkdir(parents=True, exist_ok=True)
        self._init_registry()

    def _init_registry(self):
        """Initializes the databases registry with default Chinook SQL and E-Commerce NoSQL datasets."""
        dbs = self._read_registry()
        existing_ids = [d["id"] for d in dbs]
        updated = False

        # 1. Default Chinook SQL DB
        if "chinook" not in existing_ids and DEFAULT_CHINOOK.exists() == True:
            table_count = self._count_tables(DEFAULT_CHINOOK)
            dbs.append({
                "id": "chinook",
                "name": "Chinook (Music)",
                "type": "sql",
                "filename": "chinook.db",
                "path": str(DEFAULT_CHINOOK.resolve()),
                "table_count": table_count,
                "is_default": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            updated = True

        # 2. Default NoSQL E-Commerce Store
        if "ecommerce_store" not in existing_ids and DEFAULT_NOSQL.exists() == True:
            doc_count = self._count_json_docs(DEFAULT_NOSQL)
            dbs.append({
                "id": "ecommerce_store",
                "name": "E-Commerce Store (NoSQL)",
                "type": "nosql",
                "filename": "ecommerce_store.json",
                "path": str(DEFAULT_NOSQL.resolve()),
                "doc_count": doc_count,
                "is_default": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            updated = True

        if updated == True or self.registry_file.exists() == False:
            self._write_registry(dbs)

    def _read_registry(self) -> List[Dict[str, Any]]:
        try:
            with open(self.registry_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content == "":
                    return []
                return json.loads(content)
        except (json.JSONDecodeError, OSError):
            return []

    def _write_registry(self, data: List[Dict[str, Any]]) -> None:
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _count_tables(self, db_path: Path) -> int:
        """Counts user tables in an SQLite file."""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    def _count_json_docs(self, json_path: Path) -> int:
        """Counts documents in a JSON, JSONL, or BSON file."""
        ext = json_path.suffix.lower()
        if ext == ".bson":
            try:
                import bson
                with open(json_path, "rb") as f:
                    docs = bson.decode_all(f.read())
                    return len(docs)
            except Exception:
                return 0

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content == "":
                    return 0
                if content.startswith("["):
                    return len(json.loads(content))
                elif content.startswith("{"):
                    data = json.loads(content)
                    return sum(len(v) for v in data.values() if isinstance(v, list))
                else:
                    return len([line for line in content.splitlines() if line.strip() != ""])
        except Exception:
            return 0

    def list_databases(self) -> List[Dict[str, Any]]:
        """Returns all registered data sources (SQL and NoSQL)."""
        return self._read_registry()

    def get_database(self, db_id: str) -> Optional[Dict[str, Any]]:
        """Finds a data source entry by ID."""
        dbs = self._read_registry()
        return next((d for d in dbs if d["id"] == db_id), None)

    def register_database(self, name: str, file_path: Path, filename: str) -> Dict[str, Any]:
        """
        Validates uploaded file (.db/.sqlite/.s3db/.sl3/.sql for SQL, or .json/.jsonl/.bson for NoSQL)
        and registers it with user-specified custom name and type tag.
        """
        is_nosql = filename.lower().endswith((".json", ".jsonl", ".bson"))
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', name.strip().lower())
        db_id = f"{clean_name}_{int(datetime.now(timezone.utc).timestamp())}"

        if is_nosql == True:
            # Validate JSON / BSON format
            doc_count = self._count_json_docs(file_path)
            if doc_count == 0:
                raise ValueError("The uploaded NoSQL file is empty or contains invalid JSON/BSON documents.")

            new_entry = {
                "id": db_id,
                "name": name.strip(),
                "type": "nosql",
                "filename": filename,
                "path": str(file_path.resolve()),
                "doc_count": doc_count,
                "is_default": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        else:
            # Check if this is a .sql script file
            if filename.lower().endswith(".sql"):
                # Compile .sql dump script into an SQLite database
                compiled_db_path = file_path.with_suffix(".db")
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        sql_script = f.read()
                    conn = sqlite3.connect(str(compiled_db_path.resolve()))
                    conn.executescript(sql_script)
                    conn.commit()
                    conn.close()
                    file_path = compiled_db_path
                except Exception as e:
                    raise ValueError(f"Failed to execute SQL script into database: {str(e)}")

            # Validate SQLite format
            try:
                conn = sqlite3.connect(file_path)
                cursor = conn.cursor()
                cursor.execute("PRAGMA schema_version;")
                cursor.fetchone()
                conn.close()
            except Exception as e:
                raise ValueError(f"Invalid SQLite database file: {str(e)}")

            table_count = self._count_tables(file_path)
            if table_count == 0:
                raise ValueError("The uploaded database contains 0 valid tables.")

            new_entry = {
                "id": db_id,
                "name": name.strip(),
                "type": "sql",
                "filename": file_path.name,
                "path": str(file_path.resolve()),
                "table_count": table_count,
                "is_default": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            }

        dbs = self._read_registry()
        dbs.append(new_entry)
        self._write_registry(dbs)
        return new_entry

    def delete_database(self, db_id: str) -> bool:
        """Deletes a custom user data source (cannot delete system defaults)."""
        dbs = self._read_registry()
        target = next((d for d in dbs if d["id"] == db_id), None)

        if target == None or target.get("is_default") == True:
            return False

        # Remove physical file if within managed upload directories
        file_path = Path(target["path"])
        if file_path.exists() == True and any(d in file_path.parents for d in MANAGED_UPLOAD_DIRS):
            try:
                file_path.unlink()
            except OSError:
                pass

        dbs = [d for d in dbs if d["id"] != db_id]
        self._write_registry(dbs)
        return True
