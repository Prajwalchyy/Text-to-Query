"""
Central Configuration Module for OmniData AI Backend.

Provides single-source-of-truth constants, directory paths, environment resolution,
and LLM credentials across all engines, pipelines, and API endpoints.
Pure functional design with zero OOP overhead.
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv

# ==============================================================================
# Base Directory Paths
# ==============================================================================
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
SRC_DIR = BACKEND_DIR / "src"
DATA_DIR = BACKEND_DIR / "data"

# Auto-register BACKEND_DIR and SRC_DIR in sys.path
for directory in [str(BACKEND_DIR), str(SRC_DIR)]:
    if directory not in sys.path:
        sys.path.insert(0, directory)

# Load environment variables (.env file in backend/ preferred, fallback to root)
ENV_PATH = BACKEND_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv(PROJECT_ROOT / ".env")

# ==============================================================================
# Data Storage Directories & Persistent Files
# ==============================================================================
RELATIONAL_DIR = DATA_DIR / "relational"
NOSQL_DIR = DATA_DIR / "nosql"
CSV_DIR = DATA_DIR / "csv"
EXCEL_DIR = DATA_DIR / "excel"
UPLOADS_DIR = DATA_DIR / "uploads"
CUSTOM_DB_DIR = DATA_DIR / "custom_db"
NOSQL_DEFAULT_DIR = DATA_DIR / "nosql_default"

# Default datasets categorized by file extension under data/default/<ext>/
DEFAULT_DATA_DIR = DATA_DIR / "default"
DEFAULT_DB_DIR = DEFAULT_DATA_DIR / "db"
DEFAULT_JSON_DIR = DEFAULT_DATA_DIR / "json"
DEFAULT_CSV_DIR = DEFAULT_DATA_DIR / "csv"
DEFAULT_XLSX_DIR = DEFAULT_DATA_DIR / "xlsx"

# Chat storage directory and session store files
CHAT_STORAGE_DIR = DATA_DIR / "chat-storage"
CHAT_HISTORY_FILE = CHAT_STORAGE_DIR / "chat_history.json"
LEGACY_CHAT_HISTORY_FILE = DATA_DIR / "chat_history.json"

# System-level Registry File
REGISTRY_FILE = DATA_DIR / "databases.json"

ALL_MANAGED_DIRS = [
    DATA_DIR,
    UPLOADS_DIR,
    DEFAULT_DATA_DIR,
    DEFAULT_DB_DIR,
    DEFAULT_JSON_DIR,
    DEFAULT_CSV_DIR,
    DEFAULT_XLSX_DIR,
    CHAT_STORAGE_DIR,
]

# Protected Default Datasets (saved under backend/data/default/<extension>/)
DEFAULT_CHINOOK_PATH = (
    DEFAULT_DB_DIR / "chinook.db"
    if (DEFAULT_DB_DIR / "chinook.db").exists()
    else DATA_DIR / "chinook.db"
)
DEFAULT_NOSQL_PATH = (
    DEFAULT_JSON_DIR / "ecommerce_store.json"
    if (DEFAULT_JSON_DIR / "ecommerce_store.json").exists()
    else NOSQL_DEFAULT_DIR / "ecommerce_store.json"
)
DEFAULT_CSV_PATH = (
    DEFAULT_CSV_DIR / "sales_performance.csv"
    if (DEFAULT_CSV_DIR / "sales_performance.csv").exists()
    else CSV_DIR / "sales_performance.csv"
)
DEFAULT_EXCEL_PATH = (
    DEFAULT_XLSX_DIR / "financial_budget.xlsx"
    if (DEFAULT_XLSX_DIR / "financial_budget.xlsx").exists()
    else EXCEL_DIR / "financial_budget.xlsx"
)


# ==============================================================================
# Helper Functions
# ==============================================================================
def ensure_directories() -> None:
    """Ensures all managed data directories exist on the filesystem and defaults are seeded."""
    for directory in ALL_MANAGED_DIRS:
        directory.mkdir(parents=True, exist_ok=True)

    # Seed default/<ext>/ datasets and chat storage from legacy locations if not present
    pairs = [
        (DATA_DIR / "chinook.db", DEFAULT_DB_DIR / "chinook.db"),
        (NOSQL_DEFAULT_DIR / "ecommerce_store.json", DEFAULT_JSON_DIR / "ecommerce_store.json"),
        (CSV_DIR / "sales_performance.csv", DEFAULT_CSV_DIR / "sales_performance.csv"),
        (EXCEL_DIR / "financial_budget.xlsx", DEFAULT_XLSX_DIR / "financial_budget.xlsx"),
        (LEGACY_CHAT_HISTORY_FILE, CHAT_HISTORY_FILE),
    ]
    for src, dst in pairs:
        if src.exists() and not dst.exists():
            import shutil
            shutil.copy2(src, dst)


def get_llm_settings() -> Dict[str, str]:
    """
    Returns sanitized LLM credentials and configuration from environment variables.
    Single source of truth for OpenAI-compatible client callers.
    """
    api_key = (
        os.getenv("API_KEY")
        or os.getenv("GROQ_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    ).strip()

    base_url = (
        os.getenv("API_URL")
        or os.getenv("OPENAI_BASE_URL")
        or "https://api.groq.com/openai/v1"
    ).strip()

    model = (
        os.getenv("MODEL")
        or "llama-3.3-70b-versatile"
    ).strip()

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
    }


def get_upload_dir(
    dataset_type: Optional[str] = None,
    file_ext: str = "",
    upload_mode: str = "single",
    group_folder: str = ""
) -> Path:
    """
    Resolves the standardized target directory for uploads:
    - Single mode: data/{type}/single/
    - Multiple / merged mode: data/{type}/multiple/{group_folder}/
    """
    ext = file_ext.lower().strip()
    norm_type = (dataset_type or "").lower().strip()

    if norm_type == "sql" or ext in [".db", ".sqlite", ".sqlite3", ".sql"]:
        base_dir = RELATIONAL_DIR
    elif norm_type == "nosql" or ext in [".json", ".jsonl"]:
        base_dir = NOSQL_DIR
    elif norm_type == "csv" or ext in [".csv", ".tsv", ".parquet"]:
        base_dir = CSV_DIR
    elif norm_type == "excel" or ext in [".xlsx", ".xls"]:
        base_dir = EXCEL_DIR
    else:
        base_dir = RELATIONAL_DIR

    if upload_mode == "multiple" and group_folder.strip():
        clean_folder = re.sub(r'[^a-zA-Z0-9_\-]', '_', group_folder.strip().lower())
        target = base_dir / "multiple" / clean_folder
    else:
        target = base_dir / "single"

    target.mkdir(parents=True, exist_ok=True)
    return target

