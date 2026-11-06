"""Core reusable engines and orchestration primitives."""

from src.core.decomposition import (
    decompose_question,
    is_compound_question,
    parse_query_tasks,
)
from src.core.evaluator import (
    SQLEvaluator,
    evaluate_result,
    format_data_preview,
)
from src.core.llm import (
    call_llm,
    call_llm_json,
    extract_json_payload,
    get_openai_client,
)
from src.core.polyglot import (
    LANGUAGE_CONFIG,
    MultiLanguageGenerator,
    build_polyglot_prompt,
    convert_code,
    generate_polyglot_code,
    get_supported_languages,
    is_language_supported,
)
from src.core.reflection import (
    CorrectionEngine,
    build_nosql_repair_prompt,
    build_pandas_repair_prompt,
    build_sql_repair_prompt,
    clean_repaired_code,
    run_with_reflection,
)

__all__ = [
    # LLM
    "call_llm",
    "call_llm_json",
    "extract_json_payload",
    "get_openai_client",
    # Reflection & Self-Correction
    "run_with_reflection",
    "clean_repaired_code",
    "build_sql_repair_prompt",
    "build_nosql_repair_prompt",
    "build_pandas_repair_prompt",
    "CorrectionEngine",
    # Evaluator
    "evaluate_result",
    "format_data_preview",
    "SQLEvaluator",
    # Decomposition
    "is_compound_question",
    "decompose_question",
    "parse_query_tasks",
    # Polyglot
    "LANGUAGE_CONFIG",
    "get_supported_languages",
    "is_language_supported",
    "build_polyglot_prompt",
    "generate_polyglot_code",
    "convert_code",
    "MultiLanguageGenerator",
]
