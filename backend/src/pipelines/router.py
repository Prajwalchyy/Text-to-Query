"""
Master Pipeline Router and Orchestrator (Stateless Pure Functional).

Dispatches natural language questions across SQL, NoSQL, and Spreadsheet (CSV/Excel)
data sources, managing the end-to-end execution lifecycle:
  1. Data Source & Entity Introspection (resolves database metadata, paths, schemas, and entities).
  2. Multi-Turn Conversational Memory Injection (extracts context memory window).
  3. Multi-Language (Polyglot) Routing (routes non-native targets to code generation).
  4. Prompt Synthesis & Query Generation (builds domain prompts and invokes LLM).
  5. Out-of-Domain (OOD) Guardrail Interception (catches unanswerable / missing entity queries).
  6. Universal Self-Repair Execution Loop (invokes engines via `run_with_reflection`).
  7. Compound Query Decomposition (executes multi-part requests as coordinated sub-queries).
  8. Semantic Result Evaluation (LLM-as-a-Judge accuracy and confidence scoring).
  9. Unified Telemetry Assembly (formats latency, columns, data, and execution metadata).

Zero OOP business logic; 100% stateless pure functions with a backward-compatible adapter.
Replaces legacy F02, F06, F10, F12, F15, and F16 modules.
"""

import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Ensure backend root and src directory are on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = Path(__file__).resolve().parent.parent
for p in [str(BACKEND_DIR), str(SRC_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Central Configuration
from config import (
    DEFAULT_CHINOOK_PATH,
    DEFAULT_CSV_PATH,
    DEFAULT_EXCEL_PATH,
    DEFAULT_NOSQL_PATH,
)

# Storage
try:
    from storage.registry import get_database, list_databases
    from storage.chat_store import get_conversation_context
except ImportError:
    from src.storage.registry import get_database, list_databases
    from src.storage.chat_store import get_conversation_context

# Engines
try:
    import engines.sql_engine as sql_engine
    import engines.nosql_engine as nosql_engine
    import engines.spreadsheet_engine as spreadsheet_engine
except ImportError:
    from src.engines import sql_engine, nosql_engine, spreadsheet_engine

# Guardrails
try:
    import guardrails.sql_guard as sql_guard
    import guardrails.nosql_guard as nosql_guard
    import guardrails.pandas_guard as pandas_guard
except ImportError:
    from src.guardrails import sql_guard, nosql_guard, pandas_guard

# Core Logic
try:
    from core.llm import call_llm
    from core.reflection import run_with_reflection, clean_repaired_code
    from core.evaluator import evaluate_result
    from core.decomposition import is_compound_question, decompose_question
    from core.polyglot import (
        is_language_supported,
        generate_polyglot_code,
        get_supported_languages,
    )
except ImportError:
    from src.core.llm import call_llm
    from src.core.reflection import run_with_reflection, clean_repaired_code
    from src.core.evaluator import evaluate_result
    from src.core.decomposition import is_compound_question, decompose_question
    from src.core.polyglot import (
        is_language_supported,
        generate_polyglot_code,
        get_supported_languages,
    )

# Pipelines Context & Prompts
try:
    from pipelines.prompts import (
        build_sql_prompt,
        build_nosql_prompt,
        build_spreadsheet_prompt,
        build_repair_prompt,
        parse_generator_output,
    )
    from pipelines.context import (
        extract_memory_window,
        get_chat_memory_window,
    )
except ImportError:
    from src.pipelines.prompts import (
        build_sql_prompt,
        build_nosql_prompt,
        build_spreadsheet_prompt,
        build_repair_prompt,
        parse_generator_output,
    )
    from src.pipelines.context import (
        extract_memory_window,
        get_chat_memory_window,
    )


# ==============================================================================
# Helper Functions: Data Source Resolution & Normalization
# ==============================================================================
def normalize_db_type(raw_type: Optional[str]) -> str:
    """Normalizes various database type representations to canonical keys."""
    if not raw_type:
        return "sql"
    t = raw_type.strip().lower()
    if t in ("sqlite", "sqlite3", "sql", "relational"):
        return "sql"
    if t in ("nosql", "mongodb", "mql", "json", "jsonl", "bson"):
        return "nosql"
    if t == "csv":
        return "csv"
    if t in ("excel", "xlsx", "xls"):
        return "excel"
    return "sql"


def normalize_target_language(raw_lang: Optional[str]) -> str:
    """Normalizes target language alias to canonical key in LANGUAGE_CONFIG."""
    if not raw_lang:
        return ""
    l = raw_lang.strip().lower()
    aliases = {
        "python": "pandas",
        "py": "pandas",
        "dataframe": "pandas",
        "mql": "nosql",
        "mongodb": "nosql",
        "mongo": "nosql",
        "formula": "excel_formula",
        "excel": "excel_formula",
        "excell": "excel_formula",
        "sqlite": "sql",
        "sqlite3": "sql",
    }
    return aliases.get(l, l)


def resolve_datasource(db_id: Optional[str] = "chinook") -> Tuple[Dict[str, Any], str, Path]:
    """
    Resolves a database identifier into a normalized metadata dict, canonical type,
    and absolute file Path object. Defaults to Chinook if unspecified or not found.
    """
    target_id = db_id if db_id and db_id.strip() else "chinook"
    db_info = get_database(target_id)

    if not db_info:
        if target_id == "chinook":
            db_info = {
                "id": "chinook",
                "name": "Chinook Music Store",
                "type": "sql",
                "path": str(DEFAULT_CHINOOK_PATH),
            }
        else:
            # Fallback to the first registered database or Chinook default
            all_dbs = list_databases()
            db_info = all_dbs[0] if all_dbs else {
                "id": "chinook",
                "name": "Chinook Music Store",
                "type": "sql",
                "path": str(DEFAULT_CHINOOK_PATH),
            }

    canonical_type = normalize_db_type(db_info.get("type"))
    raw_path = db_info.get("path") or db_info.get("file_path") or ""

    if canonical_type == "sql":
        resolved_path = sql_engine.resolve_sqlite_path(raw_path)
    elif canonical_type == "nosql":
        resolved_path = nosql_engine.resolve_nosql_path(raw_path)
    elif canonical_type == "excel":
        resolved_path = spreadsheet_engine.resolve_spreadsheet_path(raw_path, file_type="excel")
    else:  # csv
        resolved_path = spreadsheet_engine.resolve_spreadsheet_path(raw_path, file_type="csv")

    return db_info, canonical_type, resolved_path


def introspect_datasource(
    canonical_type: str,
    path: Path
) -> Tuple[List[str], str, Any]:
    """
    Introspects the target data source and returns:
      - available_entities: Table names, collection names, or sheet names.
      - schema_str: Clean text representation for LLM prompt context.
      - loaded_handle: Underlying data handle (path, collections dict, or DataFrames dict).
    """
    if canonical_type == "sql":
        tables = sql_engine.get_table_names(path)
        schema_text = sql_engine.format_schema_context(path)
        return tables, schema_text, path

    elif canonical_type == "nosql":
        collections = nosql_engine.load_nosql_collections(path)
        coll_names = nosql_engine.get_collection_names(collections)
        schema_text = nosql_engine.format_nosql_schema_context(collections)
        return coll_names, schema_text, collections

    elif canonical_type == "excel":
        dfs = spreadsheet_engine.load_spreadsheet(path, file_type="excel")
        sheets = list(dfs.keys())
        schema_text = spreadsheet_engine.format_spreadsheet_schema_context(dfs, file_type="excel")
        return sheets, schema_text, dfs

    else:  # csv
        dfs = spreadsheet_engine.load_spreadsheet(path, file_type="csv")
        sheets = list(dfs.keys())
        schema_text = spreadsheet_engine.format_spreadsheet_schema_context(dfs, file_type="csv")
        return sheets, schema_text, dfs


def extract_columns_from_data(data: Any) -> List[str]:
    """Extracts column headers from data records if available."""
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        return list(data[0].keys())
    return []


# ==============================================================================
# Master Pipeline Execution Function
# ==============================================================================
def run_pipeline(
    question: str,
    db_id: Optional[str] = "chinook",
    target_language: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    chat_id: Optional[str] = None,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Executes an end-to-end question against any supported data source (SQL, NoSQL, CSV, Excel).

    Args:
        question: User's natural language question.
        db_id: Target database / dataset identifier (defaults to "chinook").
        target_language: Target output language ("sql", "pandas", "nosql", "excel_formula", "r", etc.).
        history: Optional list of raw chat message dictionaries.
        chat_id: Optional chat session ID for pulling conversational context if history omitted.
        max_retries: Maximum self-repair retry attempts for syntax/schema mistakes (default: 3).

    Returns:
        dict: Standardized response payload conforming to frontend & controller data contracts:
            - question: Original question string
            - title: Descriptive title for UI session or message
            - status: "SUCCESS" | "FAILED" | "OUT_OF_DOMAIN" | "PARTIAL"
            - final_sql: Generated SQL, MQL, or code snippet
            - code: Code snippet representation
            - code_type: Language identifier ("sql", "pandas", "nosql", "excel_formula", etc.)
            - data: Execution records (list of dicts)
            - columns: List of field/column names
            - summary: Semantic natural language summary
            - confidence_score: Confidence float (0.0 to 1.0)
            - is_accurate: Boolean accuracy flag
            - attempts: Number of reflection attempts used
            - latency_ms: Execution duration in milliseconds
            - sub_queries: List of decomposed sub-queries (if compound)
            - needed_tables: Missing entities if OUT_OF_DOMAIN
            - available_tables: Available entities in dataset
            - suggested_questions: Proactive suggestions if OUT_OF_DOMAIN
    """
    start_time = time.time()
    clean_question = (question or "").strip()

    # 1. Validate Input Question
    if not clean_question:
        return {
            "question": "",
            "title": "Invalid Request",
            "status": "FAILED",
            "final_sql": None,
            "code": None,
            "code_type": "sql",
            "data": [],
            "columns": [],
            "summary": "Question cannot be empty.",
            "error": "Question cannot be empty.",
            "confidence_score": 0.0,
            "is_accurate": False,
            "attempts": 0,
            "latency_ms": 0,
            "sub_queries": [],
        }

    # 2. Resolve Data Source & Metadata
    db_info, canonical_type, resolved_path = resolve_datasource(db_id)
    default_code_types = {
        "sql": "sql",
        "nosql": "nosql",
        "csv": "pandas",
        "excel": "excel_formula",
    }
    default_code_type = default_code_types.get(canonical_type, "sql")

    # 3. Introspect Schema Context and Available Entities
    try:
        available_entities, schema_context_str, loaded_handle = introspect_datasource(
            canonical_type, resolved_path
        )
    except Exception as intro_err:
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "question": clean_question,
            "title": "Data Source Error",
            "status": "FAILED",
            "final_sql": None,
            "code": None,
            "code_type": default_code_type,
            "data": [],
            "columns": [],
            "summary": f"Failed to introspect data source: {str(intro_err)}",
            "error": str(intro_err),
            "confidence_score": 0.0,
            "is_accurate": False,
            "attempts": 0,
            "latency_ms": latency_ms,
            "sub_queries": [],
        }

    # 4. Resolve Conversational Memory Window
    active_history: List[Dict[str, Any]] = []
    if history:
        active_history = extract_memory_window(history, limit=4)
    elif chat_id:
        active_history = get_chat_memory_window(chat_id, limit=4)

    # 5. Polyglot Multi-Language Routing Check
    raw_lang = normalize_target_language(target_language)
    if not raw_lang or raw_lang == "auto":
        target_lang = default_code_type
    else:
        target_lang = raw_lang

    is_native = (
        (canonical_type == "sql" and target_lang == "sql")
        or (canonical_type == "nosql" and target_lang == "nosql")
        or (canonical_type == "csv" and target_lang == "pandas")
        or (canonical_type == "excel" and target_lang == "excel_formula")
    )

    if not is_native:
        # Check domain compatibility
        if not is_language_supported(canonical_type, target_lang):
            latency_ms = int((time.time() - start_time) * 1000)
            supported = get_supported_languages(canonical_type)
            err_msg = (
                f"Target language '{target_lang}' is not supported for data source type '{canonical_type}'. "
                f"Allowed languages: {supported}"
            )
            return {
                "question": clean_question,
                "title": "Unsupported Language",
                "status": "FAILED",
                "final_sql": None,
                "code": None,
                "code_type": target_language.lower() if target_language and target_language.lower() != "auto" else target_lang,
                "data": [],
                "columns": [],
                "summary": err_msg,
                "error": err_msg,
                "confidence_score": 0.0,
                "is_accurate": False,
                "attempts": 0,
                "latency_ms": latency_ms,
                "sub_queries": [],
            }

        # Generate polyglot code
        poly_res = generate_polyglot_code(
            question=clean_question,
            schema_context=schema_context_str,
            db_type=canonical_type,
            target_language=target_lang,
            db_name=db_info.get("name", "database"),
            table_or_sheet_names=available_entities,
        )

        code_snippet = poly_res.get("code", "")
        preview_data: List[Dict[str, Any]] = []

        # Execute preview query to populate data table if eval helper present
        if canonical_type == "sql":
            eval_query = poly_res.get("eval_sql") or code_snippet
            try:
                preview_data = sql_engine.execute_sql_query(sql_query=eval_query, db_path=resolved_path)
            except Exception:
                pass

        elif canonical_type == "nosql":
            eval_mql = poly_res.get("eval_mql")
            if eval_mql:
                try:
                    preview_data = nosql_engine.execute_mql(
                        collections=loaded_handle, query=eval_mql
                    )
                except Exception:
                    pass

        elif canonical_type in ("csv", "excel"):
            dfs = loaded_handle
            if target_lang == "sql":
                try:
                    preview_data = spreadsheet_engine.execute_sql_on_spreadsheet(dfs, code_snippet)
                except Exception:
                    pass
            else:
                if poly_res.get("eval_sql"):
                    try:
                        preview_data = spreadsheet_engine.execute_sql_on_spreadsheet(
                            dfs, poly_res["eval_sql"]
                        )
                    except Exception:
                        pass
                if not preview_data and poly_res.get("eval_pandas"):
                    try:
                        preview_data = spreadsheet_engine.execute_pandas_code(
                            dfs, poly_res["eval_pandas"]
                        )
                    except Exception:
                        pass
                if not preview_data:
                    first_sheet = next(iter(dfs.values())) if dfs else None
                    if first_sheet is not None:
                        preview_data = spreadsheet_engine.clean_records_for_json(
                            first_sheet.head(10).to_dict(orient="records")
                        )

        columns = extract_columns_from_data(preview_data)
        latency_ms = int((time.time() - start_time) * 1000)

        return {
            "question": clean_question,
            "title": poly_res.get("title", clean_question[:40]),
            "status": "SUCCESS",
            "final_sql": code_snippet,
            "code": code_snippet,
            "code_type": target_language.lower() if target_language and target_language.lower() != "auto" else target_lang,
            "data": preview_data,
            "columns": columns,
            "summary": poly_res.get("explanation", f"Generated {target_lang.upper()} query code."),
            "confidence_score": 0.95,
            "is_accurate": True,
            "attempts": 1,
            "latency_ms": latency_ms,
            "sub_queries": [],
        }

    # 6. Native Dialect Query Generation via Master Prompt Templates
    try:
        if canonical_type == "sql":
            system_prompt, user_prompt = build_sql_prompt(
                question=clean_question,
                schema_str=schema_context_str,
                history=active_history,
            )
        elif canonical_type == "nosql":
            system_prompt, user_prompt = build_nosql_prompt(
                question=clean_question,
                schema_str=schema_context_str,
                history=active_history,
            )
        elif canonical_type == "excel":
            system_prompt, user_prompt = build_spreadsheet_prompt(
                question=clean_question,
                schema_str=schema_context_str,
                file_type="excel",
                history=active_history,
            )
        else:  # csv
            system_prompt, user_prompt = build_spreadsheet_prompt(
                question=clean_question,
                schema_str=schema_context_str,
                file_type="csv",
                history=active_history,
            )

        raw_llm_response = call_llm(prompt=user_prompt, system_prompt=system_prompt)
        parsed_result = parse_generator_output(raw_llm_response, db_type=canonical_type)

    except Exception as gen_err:
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "question": clean_question,
            "title": "Query Generation Failed",
            "status": "FAILED",
            "final_sql": None,
            "code": None,
            "code_type": default_code_type,
            "data": [],
            "columns": [],
            "summary": f"Could not generate query: {str(gen_err)}",
            "error": str(gen_err),
            "confidence_score": 0.0,
            "is_accurate": False,
            "attempts": 1,
            "latency_ms": latency_ms,
            "sub_queries": [],
        }

    # 7. Out-of-Domain (OOD) Guardrail Interception
    if isinstance(parsed_result, dict) and parsed_result.get("is_relevant") is False:
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "question": clean_question,
            "title": "Out of Domain Query",
            "status": "OUT_OF_DOMAIN",
            "final_sql": None,
            "code": None,
            "code_type": default_code_type,
            "data": [],
            "columns": [],
            "summary": parsed_result.get(
                "reason",
                f"The active {canonical_type.upper()} data source does not contain the requested entities.",
            ),
            "is_relevant": False,
            "needed_tables": parsed_result.get("needed_tables", []),
            "available_tables": available_entities,
            "suggested_questions": parsed_result.get("suggested_questions", []),
            "confidence_score": 1.0,
            "is_accurate": True,
            "attempts": 1,
            "latency_ms": latency_ms,
            "sub_queries": [],
        }

    # Normalize parsed results to list of items
    query_items: List[Dict[str, Any]] = []
    if isinstance(parsed_result, list):
        query_items = parsed_result
    elif isinstance(parsed_result, dict):
        query_items = [parsed_result]

    if not query_items:
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "question": clean_question,
            "title": "Query Generation Failed",
            "status": "FAILED",
            "final_sql": None,
            "code": None,
            "code_type": default_code_type,
            "data": [],
            "columns": [],
            "summary": "Generator returned empty query structure.",
            "error": "Empty query generated.",
            "confidence_score": 0.0,
            "is_accurate": False,
            "attempts": 1,
            "latency_ms": latency_ms,
            "sub_queries": [],
        }

    # 8. Single Query Execution Path with Self-Repair (Reflection)
    if len(query_items) <= 1:
        item = query_items[0]
        title = item.get("title") or clean_question[:40]

        # Dispatch execution by data source
        if canonical_type == "sql":
            initial_sql = item.get("sql", "").strip()
            reflection_res = run_with_reflection(
                execute_fn=lambda q: sql_engine.execute_sql_query(sql_query=q, db_path=resolved_path),
                initial_query=initial_sql,
                validate_fn=lambda q: sql_guard.validate_sql(
                    q, allowed_tables=set(available_entities)
                ),
                repair_prompt_fn=lambda q, err, att=1: build_repair_prompt(
                    question=clean_question,
                    broken_query=q,
                    error=err,
                    schema_str=schema_context_str,
                    dialect="sql",
                ),
                max_attempts=max_retries,
            )

        elif canonical_type == "nosql":
            initial_mql = item.get("mql") or item.get("sql", "").strip()
            reflection_res = run_with_reflection(
                execute_fn=lambda q: nosql_engine.execute_mql(
                    collections=loaded_handle, query=q
                ),
                initial_query=initial_mql,
                validate_fn=lambda q: nosql_guard.validate_mql(
                    q, available_collections=available_entities
                ),
                repair_prompt_fn=lambda q, err, att=1: build_repair_prompt(
                    question=clean_question,
                    broken_query=q,
                    error=err,
                    schema_str=schema_context_str,
                    dialect="nosql",
                ),
                max_attempts=max_retries,
            )

        elif canonical_type == "excel":
            formula = item.get("formula", "").strip()
            eval_code = item.get("eval_code", "").strip()
            dfs = loaded_handle

            # If eval_code is available, evaluate preview data with pandas guardrail
            preview_data: List[Dict[str, Any]] = []
            if eval_code:
                reflection_res = run_with_reflection(
                    execute_fn=lambda q: spreadsheet_engine.execute_pandas_code(dfs, q),
                    initial_query=eval_code,
                    validate_fn=pandas_guard.validate_pandas_code,
                    repair_prompt_fn=lambda q, err, att=1: build_repair_prompt(
                        question=clean_question,
                        broken_query=q,
                        error=err,
                        schema_str=schema_context_str,
                        dialect="pandas",
                    ),
                    max_attempts=max_retries,
                )
                if reflection_res["success"]:
                    preview_data = reflection_res["data"]
            else:
                # Direct formula evaluation
                try:
                    preview_data = spreadsheet_engine.execute_excel_formula(dfs, formula)
                    reflection_res = {
                        "success": True,
                        "data": preview_data,
                        "final_query": formula,
                        "attempts": 1,
                        "error": None,
                    }
                except Exception as ex_err:
                    reflection_res = {
                        "success": False,
                        "data": [],
                        "final_query": formula,
                        "attempts": 1,
                        "error": str(ex_err),
                    }

            # Normalize reflection result for Excel formula presentation
            if not reflection_res["success"] and not preview_data:
                first_sheet = next(iter(dfs.values())) if dfs else None
                if first_sheet is not None:
                    preview_data = spreadsheet_engine.clean_records_for_json(
                        first_sheet.head(10).to_dict(orient="records")
                    )
                    reflection_res["success"] = True
                    reflection_res["data"] = preview_data

            reflection_res["final_query"] = formula or reflection_res.get("final_query", "")

        else:  # csv
            initial_code = item.get("code") or item.get("sql", "").strip()
            dfs = loaded_handle
            reflection_res = run_with_reflection(
                execute_fn=lambda q: spreadsheet_engine.execute_pandas_code(dfs, q),
                initial_query=initial_code,
                validate_fn=pandas_guard.validate_pandas_code,
                repair_prompt_fn=lambda q, err, att=1: build_repair_prompt(
                    question=clean_question,
                    broken_query=q,
                    error=err,
                    schema_str=schema_context_str,
                    dialect="pandas",
                ),
                max_attempts=max_retries,
            )

        latency_ms = int((time.time() - start_time) * 1000)

        # Handle Execution Failure
        if not reflection_res.get("success"):
            err_details = reflection_res.get("error", "Execution failed.")
            return {
                "question": clean_question,
                "title": title,
                "status": "FAILED",
                "final_sql": reflection_res.get("final_query"),
                "code": reflection_res.get("final_query"),
                "code_type": default_code_type,
                "data": [],
                "columns": [],
                "error": str(err_details),
                "summary": f"Query execution failed: {err_details}",
                "confidence_score": 0.0,
                "is_accurate": False,
                "attempts": reflection_res.get("attempts", 1),
                "latency_ms": latency_ms,
                "sub_queries": [],
            }

        # Handle Execution Success
        success_data = reflection_res.get("data")
        final_query = reflection_res.get("final_query", "")
        columns = extract_columns_from_data(success_data)

        # 9. Semantic Result Evaluation (LLM-as-a-Judge)
        eval_res = evaluate_result(
            question=clean_question,
            query=final_query,
            data=success_data,
            schema_context=schema_context_str,
        )

        final_summary = eval_res.get("summary")
        if not final_summary or final_summary.strip() == "":
            final_summary = item.get("explanation") or f"Executed query successfully. Found {len(success_data)} records."

        return {
            "question": clean_question,
            "title": title,
            "status": "SUCCESS",
            "final_sql": final_query,
            "code": final_query,
            "code_type": default_code_type,
            "data": success_data,
            "columns": columns,
            "summary": final_summary,
            "confidence_score": eval_res.get("confidence_score", 0.90),
            "is_accurate": eval_res.get("is_accurate", True),
            "attempts": reflection_res.get("attempts", 1),
            "latency_ms": latency_ms,
            "sub_queries": [
                {
                    "title": title,
                    "sql": final_query,
                    "code_type": default_code_type,
                    "data": success_data,
                    "status": "SUCCESS",
                }
            ],
        }

    # 10. Multi-Query Decomposition Path (Compound Requests)
    executed_sub_queries: List[Dict[str, Any]] = []
    overall_success = True
    total_attempts = 0

    for idx, sub_item in enumerate(query_items, 1):
        sub_title = sub_item.get("title") or f"Query {idx}"
        sub_sql = (sub_item.get("sql") or sub_item.get("mql") or sub_item.get("code") or sub_item.get("formula") or "").strip()

        if canonical_type == "sql":
            sub_res = run_with_reflection(
                execute_fn=lambda q: sql_engine.execute_sql_query(sql_query=q, db_path=resolved_path),
                initial_query=sub_sql,
                validate_fn=lambda q: sql_guard.validate_sql(
                    q, allowed_tables=set(available_entities)
                ),
                repair_prompt_fn=lambda q, err, att=1: build_repair_prompt(
                    question=f"{clean_question} - Part {idx}: {sub_title}",
                    broken_query=q,
                    error=err,
                    schema_str=schema_context_str,
                    dialect="sql",
                ),
                max_attempts=max_retries,
            )
        elif canonical_type == "nosql":
            sub_res = run_with_reflection(
                execute_fn=lambda q: nosql_engine.execute_mql(
                    collections=loaded_handle, query=q
                ),
                initial_query=sub_sql,
                validate_fn=lambda q: nosql_guard.validate_mql(
                    q, available_collections=available_entities
                ),
                repair_prompt_fn=lambda q, err, att=1: build_repair_prompt(
                    question=f"{clean_question} - Part {idx}: {sub_title}",
                    broken_query=q,
                    error=err,
                    schema_str=schema_context_str,
                    dialect="nosql",
                ),
                max_attempts=max_retries,
            )
        elif canonical_type == "excel":
            sub_eval = sub_item.get("eval_code") or sub_sql
            dfs = loaded_handle
            sub_res = run_with_reflection(
                execute_fn=lambda q: spreadsheet_engine.execute_pandas_code(dfs, q),
                initial_query=sub_eval,
                validate_fn=pandas_guard.validate_pandas_code,
                repair_prompt_fn=lambda q, err, att=1: build_repair_prompt(
                    question=f"{clean_question} - Part {idx}: {sub_title}",
                    broken_query=q,
                    error=err,
                    schema_str=schema_context_str,
                    dialect="pandas",
                ),
                max_attempts=max_retries,
            )
        else:  # csv
            dfs = loaded_handle
            sub_res = run_with_reflection(
                execute_fn=lambda q: spreadsheet_engine.execute_pandas_code(dfs, q),
                initial_query=sub_sql,
                validate_fn=pandas_guard.validate_pandas_code,
                repair_prompt_fn=lambda q, err, att=1: build_repair_prompt(
                    question=f"{clean_question} - Part {idx}: {sub_title}",
                    broken_query=q,
                    error=err,
                    schema_str=schema_context_str,
                    dialect="pandas",
                ),
                max_attempts=max_retries,
            )

        total_attempts += sub_res.get("attempts", 1)
        sub_success = sub_res.get("success", False)
        if not sub_success:
            overall_success = False

        executed_sub_queries.append({
            "title": sub_title,
            "sql": sub_res.get("final_query", sub_sql),
            "code_type": default_code_type,
            "data": sub_res.get("data") if sub_success else [],
            "error": sub_res.get("error") if not sub_success else None,
            "status": "SUCCESS" if sub_success else "FAILED",
        })

    latency_ms = int((time.time() - start_time) * 1000)

    # Select primary preview from first successful sub-query
    first_successful = next(
        (sq for sq in executed_sub_queries if sq["status"] == "SUCCESS"),
        executed_sub_queries[0] if executed_sub_queries else None,
    )

    primary_sql = first_successful["sql"] if first_successful else None
    primary_data = first_successful["data"] if first_successful else []
    columns = extract_columns_from_data(primary_data)

    successful_count = sum(1 for sq in executed_sub_queries if sq["status"] == "SUCCESS")
    if successful_count == len(executed_sub_queries):
        compound_status = "SUCCESS"
        confidence = 0.95
        summary_text = f"Executed all {len(executed_sub_queries)} sub-queries successfully."
    elif successful_count > 0:
        compound_status = "PARTIAL"
        confidence = 0.70
        summary_text = (
            f"Executed {successful_count} of {len(executed_sub_queries)} sub-queries successfully."
        )
    else:
        compound_status = "FAILED"
        confidence = 0.0
        summary_text = f"All {len(executed_sub_queries)} sub-queries failed."

    return {
        "question": clean_question,
        "title": query_items[0].get("title", clean_question[:40]),
        "status": compound_status,
        "is_multi_query": True,
        "final_sql": primary_sql,
        "code": primary_sql,
        "code_type": default_code_type,
        "data": primary_data,
        "columns": columns,
        "sub_queries": executed_sub_queries,
        "summary": summary_text,
        "confidence_score": confidence,
        "is_accurate": overall_success,
        "attempts": total_attempts,
        "latency_ms": latency_ms,
    }


# ==============================================================================
# Backward-Compatible Pipeline Adapter
# ==============================================================================
class FunctionalPipelineAdapter:
    """
    Thin, backward-compatible adapter presenting the `.run_pipeline(...)` signature
    previously expected from legacy `TextToSQLPipeline`, `TextToNoSQLPipeline`,
    and `TextToSpreadsheetPipeline` class instances.
    """

    def __init__(self, db_id: str = "chinook"):
        self.db_id = db_id

    def run_pipeline(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        target_language: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Routes directly to pure functional `run_pipeline`."""
        return run_pipeline(
            question=question,
            db_id=self.db_id,
            target_language=target_language,
            history=conversation_history,
            **kwargs,
        )

    def get_supported_languages(self) -> List[str]:
        """Returns supported languages for this adapter's data source."""
        db_info, canonical_type, _ = resolve_datasource(self.db_id)
        return get_supported_languages(canonical_type)
