"""
Dialects package entrypoint for OmniData AI.

Provides vertical domain packages per dialect (SQL, NoSQL, Tabular)
combining security guardrails, schema introspection, and execution engines:
  - base: Universal scalar normalization, dataset path resolution, and engine protocols.
  - sql: SQLite guardrails, PRAGMA schema introspection, and query execution.
  - nosql: MongoDB MQL operator guardrails, schema inference, and in-memory aggregation.
  - tabular: Python/Pandas AST guardrails, spreadsheet loaders, and multi-paradigm execution.
"""

from dialects.base import (
    EngineProtocol,
    ValidationResult,
    normalize_doc_tree,
    resolve_dataset_file,
    sanitize_records_for_json,
    sanitize_scalar,
)

from dialects import sql
from dialects import nosql
from dialects import tabular

__all__ = [
    # Base Foundation & Contracts
    "EngineProtocol",
    "ValidationResult",
    "normalize_doc_tree",
    "resolve_dataset_file",
    "sanitize_records_for_json",
    "sanitize_scalar",
    # Dialect Modules
    "sql",
    "nosql",
    "tabular",
]

