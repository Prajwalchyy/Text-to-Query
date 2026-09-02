import json
import sqlite3
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
REGISTRY_FILE = DATA_DIR / "databases.json"
DEFAULT_CHINOOK = DATA_DIR / "chinook.db"


class DatabaseRegistry:
    """
    Manages custom and system SQLite databases.
    Enables users to upload, name, and switch between multiple databases in the system.
    """
    def __init__(self, registry_file: Path = REGISTRY_FILE):
        self.registry_file = registry_file
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        self._init_registry()

    def _init_registry(self):
        """Initializes the databases registry file with default Chinook database if not exists."""
        if self.registry_file.exists() == False:
            default_dbs = []
            if DEFAULT_CHINOOK.exists() == True:
                table_count = self._count_tables(DEFAULT_CHINOOK)
                default_dbs.append({
                    "id": "chinook",
                    "name": "Chinook (Music)",
                    "filename": "chinook.db",
                    "path": str(DEFAULT_CHINOOK.resolve()),
                    "table_count": table_count,
                    "is_default": True,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
            self._write_registry(default_dbs)

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

    def list_databases(self) -> List[Dict[str, Any]]:
        """Returns all registered databases."""
        return self._read_registry()

    def get_database(self, db_id: str) -> Optional[Dict[str, Any]]:
        """Finds a database entry by ID."""
        dbs = self._read_registry()
        return next((d for d in dbs if d["id"] == db_id), None)

    def register_database(self, name: str, file_path: Path, filename: str) -> Dict[str, Any]:
        """
        Validates SQLite file and registers it with a custom user-defined name.
        """
        # Validate that it is a valid SQLite database
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA schema_version;")
            cursor.fetchone()
            conn.close()
        except Exception as e:
            raise ValueError(f"Invalid SQLite database file: {str(e)}")

        table_count = self._count_tables(file_path)

        # Generate a URL-friendly ID from custom name
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', name.strip().lower())
        db_id = f"{clean_name}_{int(datetime.now(timezone.utc).timestamp())}"

        new_entry = {
            "id": db_id,
            "name": name.strip(),
            "filename": filename,
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
        """Deletes a custom database (cannot delete system default)."""
        dbs = self._read_registry()
        target = next((d for d in dbs if d["id"] == db_id), None)

        if target == None or target.get("is_default") == True:
            return False

        # Remove physical file if in uploads
        file_path = Path(target["path"])
        if file_path.exists() and UPLOADS_DIR in file_path.parents:
            try:
                file_path.unlink()
            except OSError:
                pass

        dbs = [d for d in dbs if d["id"] != db_id]
        self._write_registry(dbs)
        return True
