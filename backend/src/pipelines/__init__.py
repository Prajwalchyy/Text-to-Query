"""
Pipelines Module.

Contains high-level prompt builders, multi-turn conversational context windows,
and the master query routing orchestrator for SQL, NoSQL, and Spreadsheet engines.
"""

from .prompts import (
    SQL_SYSTEM_PROMPT_TEMPLATE,
    NOSQL_SYSTEM_PROMPT_TEMPLATE,
    SPREADSHEET_CSV_SYSTEM_PROMPT_TEMPLATE,
    SPREADSHEET_EXCEL_SYSTEM_PROMPT_TEMPLATE,
    REPAIR_SYSTEM_PROMPTS,
    format_history_context,
    build_sql_prompt,
    build_nosql_prompt,
    build_spreadsheet_prompt,
    build_repair_prompt,
    parse_generator_output,
    extract_memory_window,
    has_pronoun_reference,
    format_context_for_prompt,
    get_chat_memory_window,
)
from .router import (
    run_pipeline,
    FunctionalPipelineAdapter,
    resolve_datasource,
    introspect_datasource,
    normalize_db_type,
)

__all__ = [
    # Prompts
    "SQL_SYSTEM_PROMPT_TEMPLATE",
    "NOSQL_SYSTEM_PROMPT_TEMPLATE",
    "SPREADSHEET_CSV_SYSTEM_PROMPT_TEMPLATE",
    "SPREADSHEET_EXCEL_SYSTEM_PROMPT_TEMPLATE",
    "REPAIR_SYSTEM_PROMPTS",
    "format_history_context",
    "build_sql_prompt",
    "build_nosql_prompt",
    "build_spreadsheet_prompt",
    "build_repair_prompt",
    "parse_generator_output",
    # Context
    "extract_memory_window",
    "has_pronoun_reference",
    "format_context_for_prompt",
    "get_chat_memory_window",
    # Router
    "run_pipeline",
    "FunctionalPipelineAdapter",
    "resolve_datasource",
    "introspect_datasource",
    "normalize_db_type",
]
