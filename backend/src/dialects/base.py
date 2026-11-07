"""
Universal Base Foundation for Dialects.
Enterprise Text-to-SQL API (v2.0)

Provides unified, shared infrastructure across all data dialect domains:
  1. Universal Dataset Path Resolution (searches standard databases and upload folders).
  2. Universal JSON / Primitive Normalization (cleans datetime, Decimal, NaN, inf, bytes,
     NumPy primitives, Pandas Timestamps, and BSON ObjectIds).
  3. Universal Engine Protocol & Validation Result contracts.

Zero unnecessary boilerplate; 100% reusable shared foundation.
"""

import math
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Protocol, Union

try:
    import numpy as np
except ImportError:
    np = None

try:
    import pandas as pd
except ImportError:
    pd = None


# ==============================================================================
# 1. Universal Path Resolution
# ==============================================================================
def resolve_dataset_file(
    target_path: Optional[Union[Path, str]],
    default_path: Path,
    search_directories: List[Path],
    default_alias_names: Optional[List[str]] = None,
) -> Path:
    """
    Universal dataset path resolver across all engine/dialect domains.
    Searches given bases for filename or relative path, falling back to default_path.
    """
    if target_path is None or str(target_path).strip() == "":
        return default_path.resolve()

    target_str = str(target_path).strip()
    if target_str.startswith("sqlite:///"):
        target_str = target_str.replace("sqlite:///", "")

    if default_alias_names and target_str in default_alias_names:
        return default_path.resolve()

    p = Path(target_str)
    if p.is_absolute() and p.exists():
        return p.resolve()

    filename = p.name
    if filename == default_path.name and default_path.exists():
        return default_path.resolve()

    # Priority 1: Direct filename match across search base directories
    for base in search_directories:
        candidate_file = (base / filename).resolve()
        if candidate_file.exists():
            return candidate_file

    # Priority 2: Relative path match from search bases
    for base in search_directories:
        try:
            candidate = (base / p).resolve()
            if candidate.exists():
                return candidate
        except Exception:
            pass

    return p.resolve()


# ==============================================================================
# 2. Universal Data Normalization & JSON Sanitization
# ==============================================================================
def sanitize_scalar(val: Any) -> Any:
    """
    Normalizes a single arbitrary database or driver scalar value into a standard,
    safe JSON-serializable Python primitive.
    Handles:
      - None
      - float NaN / Infinity -> None (null in JSON)
      - datetime / date / time -> ISO 8601 string
      - pd.Timestamp / np.datetime64 -> string representation
      - Decimal -> float
      - bytes -> utf-8 decoded string (fallback: hex)
      - np.generic (np.int64, np.float64, np.bool_) -> native Python int/float/bool
      - BSON ObjectId -> string
      - Recursive lists / tuples / dicts
    """
    if val is None:
        return None

    # Handle NumPy generic types (np.int64, np.float64, np.bool_, etc.) before primitive checks
    if np is not None and isinstance(val, np.generic):
        val = val.item()

    # Handle float NaN and Infinity (strictly forbidden in RFC 8259 JSON)
    if isinstance(val, (float, int)) and not isinstance(val, bool):
        if math.isnan(val) or math.isinf(val):
            return None
        return val

    # Handle pd.Timestamp and np.datetime64 before standard datetime
    if pd is not None and isinstance(val, pd.Timestamp):
        return str(val)
    if np is not None and isinstance(val, np.datetime64):
        return str(val)

    # Handle datetime, date, and objects with isoformat()
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if hasattr(val, "isoformat") and callable(getattr(val, "isoformat")):
        return val.isoformat()

    # Handle Decimal
    if isinstance(val, Decimal):
        return float(val)

    # Handle raw bytes
    if isinstance(val, bytes):
        try:
            return val.decode("utf-8")
        except UnicodeDecodeError:
            return val.hex()

    # Handle NumPy generic types
    if np is not None and isinstance(val, np.generic):
        return val.item()

    # Handle MongoDB BSON ObjectId or objects ending in ObjectId
    if hasattr(val, "__str__") and type(val).__name__.endswith("ObjectId"):
        return str(val)

    # Handle recursive nested sequences (lists, tuples)
    if isinstance(val, (list, tuple)):
        return [sanitize_scalar(x) for x in val]

    # Handle recursive nested dictionaries
    if isinstance(val, dict):
        return {str(k): sanitize_scalar(v) for k, v in val.items()}

    return val


def sanitize_records_for_json(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sanitizes an entire list of tabular row dictionaries into clean JSON-serializable primitives.
    """
    if not records:
        return []
    cleaned: List[Dict[str, Any]] = []
    for row in records:
        cleaned.append({str(k): sanitize_scalar(v) for k, v in row.items()})
    return cleaned


def normalize_doc_tree(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitizes a hierarchical document tree (e.g. MongoDB BSON doc) into clean JSON primitives.
    Backward-compatible drop-in replacement for normalize_bson_doc.
    """
    return sanitize_scalar(doc)


# ==============================================================================
# 3. Universal Architectural Contracts (Protocol & Result)
# ==============================================================================
class ValidationResult(NamedTuple):
    """
    Standardized immutable validation result across all dialects.
    """
    is_valid: bool
    error: Optional[str] = None
    sanitized_query: Optional[Any] = None


class EngineProtocol(Protocol):
    """
    Universal architectural protocol / contract for any database engine.
    New future engines (e.g. postgres, graph, parquet) only need to satisfy this contract.
    """
    def resolve_path(self, target: Optional[Union[Path, str]] = None) -> Path: ...
    def get_schema_context(self, target: Optional[Union[Path, str]] = None) -> str: ...
    def execute(self, query: str, target: Optional[Union[Path, str]] = None) -> List[Dict[str, Any]]: ...

