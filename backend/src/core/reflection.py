"""
Universal Reflection and Self-Repair Engine (Stateless Pure Functional).

Provides a centralized 3-attempt self-correction reflection loop (`run_with_reflection`)
shared across SQL, NoSQL (MQL), and Spreadsheet (Pandas/Excel) execution pipelines.
Replaces duplicate retry and self-healing loops previously scattered across
legacy F04, F12, and F16 modules.

Zero OOP required; pure functional interfaces with a thin backward-compatible adapter.
"""

import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Ensure backend root is discoverable for internal imports
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def clean_repaired_code(raw_code: str, expected_type: str = "auto") -> str:
    """
    Strips markdown code fences, conversational prose, and JSON wrappers
    from LLM-generated repaired code or queries.

    Handles:
      - ```sql ... ```, ```json ... ```, ```python ... ```, ``` ... ```
      - JSON objects containing keys like "code", "sql", "mql", "query"
      - Surrounding whitespace and stray backticks
    """
    if not raw_code:
        return ""

    cleaned = raw_code.strip()

    # If the response is a JSON dictionary containing a code field, extract it
    if cleaned.startswith("{") and cleaned.endswith("}"):
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                for candidate_key in ["code", "sql", "mql", "query", "formula"]:
                    if candidate_key in parsed and isinstance(parsed[candidate_key], str):
                        cleaned = parsed[candidate_key].strip()
                        break
        except Exception:
            pass

    # Strip markdown code blocks
    # Match ```optional_lang\n ... \n```
    code_block_match = re.search(r"```(?:[a-zA-Z0-9_\-]+)?\s*\n?(.*?)\s*```", cleaned, re.DOTALL)
    if code_block_match:
        cleaned = code_block_match.group(1).strip()
    else:
        # Strip leading or trailing fence markers if unclosed
        cleaned = re.sub(r"^```(?:[a-zA-Z0-9_\-]+)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    # Strip language prefixes if remaining (e.g. "sql\nSELECT ...")
    for prefix in ["sql\n", "json\n", "python\n", "mql\n", "excel\n"]:
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()

    return cleaned.strip()


def build_sql_repair_prompt(
    question: str,
    broken_sql: str,
    error_message: str,
    schema_context: str
) -> str:
    """
    Constructs the prompt for repairing a failed SQLite query.
    """
    return f"""You are an expert SQL Database Engineer fixing a failed SQLite query.

User Question: {question}
Failed SQL Query: {broken_sql}
Database Error: {error_message}

Database Schema:
{schema_context}

Instructions:
1. Inspect the database error and the schema above to identify and fix the mistake.
2. Return ONLY the single corrected SQLite SQL query.
3. Do NOT wrap the query in markdown backticks or commentary.
"""


def build_nosql_repair_prompt(
    question: str,
    broken_mql: str,
    error_message: str,
    schema_context: str
) -> str:
    """
    Constructs the prompt for repairing a failed MongoDB MQL query or aggregation pipeline.
    """
    return f"""You are an expert MongoDB Engineer fixing a failed MQL query or aggregation pipeline.

User Question: {question}
Failed Query / Pipeline: {broken_mql}
Execution Error: {error_message}

Available Collections & Schemas:
{schema_context}

Instructions:
1. Inspect the error and schema above to correct collection names, field paths, and operators.
2. Return ONLY the valid JSON or MQL expression.
3. Do NOT wrap in markdown commentary or conversational text.
"""


def build_pandas_repair_prompt(
    question: str,
    broken_code: str,
    error_message: str,
    schema_context: str
) -> str:
    """
    Constructs the prompt for repairing failed Python Pandas data analysis code.
    """
    return f"""You are an expert Data Engineer fixing failed Python Pandas data analysis code.

User Question: {question}
Failed Pandas Code:
{broken_code}

Runtime / Guardrail Error:
{error_message}

DataFrame Schema Context:
{schema_context}

Instructions:
1. Fix the Pandas code to resolve the error. Ensure it assigns the final result DataFrame to `result_df`.
2. Do NOT use forbidden imports, file I/O, or infinite loops.
3. Return ONLY the executable Python code.
"""


def _evaluate_validation(
    validate_fn: Optional[Callable[[str], Any]],
    query: str
) -> Tuple[bool, Optional[str]]:
    """
    Evaluates various validator return signatures safely:
      - Returns tuple (is_valid, error_msg, ...)
      - Returns bool (True/False)
      - Returns object with `.is_valid` attribute (SQLValidationResult, PandasValidationResult)
      - Returns None (assumed valid)
    """
    if validate_fn is None:
        return True, None

    try:
        res = validate_fn(query)
    except Exception as e:
        return False, f"Validation exception: {str(e)}"

    if res is None:
        return True, None

    if isinstance(res, bool):
        return res, None if res else "Guardrail validation blocked the query."

    # Objects with is_valid attribute (like NamedTuple results)
    if hasattr(res, "is_valid"):
        is_val = bool(res.is_valid)
        if not is_val:
            err = getattr(res, "error", None) or getattr(res, "reason", None) or "Validation blocked."
            return False, str(err)
        return True, None

    # Tuples / Lists like (is_valid, reason, ...)
    if isinstance(res, (tuple, list)):
        if len(res) >= 2:
            is_val = bool(res[0])
            err = res[1] if not is_val else None
            return is_val, str(err) if err else None
        elif len(res) == 1:
            is_val = bool(res[0])
            return is_val, None if is_val else "Validation failed."

    return True, None


def _evaluate_execution(
    execute_fn: Callable[[str], Any],
    query: str
) -> Tuple[bool, Any, Optional[str]]:
    """
    Executes a query safely, handling both exception-raising and tuple-returning
    execution functions (e.g. legacy (True, data) or (False, error)).
    """
    try:
        res = execute_fn(query)
        if isinstance(res, tuple) and len(res) == 2 and isinstance(res[0], bool):
            success, data_or_err = res
            if success:
                return True, data_or_err, None
            else:
                return False, None, str(data_or_err)
        return True, res, None
    except Exception as e:
        return False, None, str(e)


def _invoke_repair(
    repair_callable: Callable[..., Any],
    query: str,
    error: str,
    attempt: int
) -> Any:
    """
    Invokes repair callable with either (query, error, attempt) or (query, error)
    depending on signature.
    """
    try:
        sig = inspect.signature(repair_callable)
        params = [
            p for p in sig.parameters.values()
            if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        if len(params) >= 3:
            return repair_callable(query, error, attempt)
        return repair_callable(query, error)
    except (ValueError, TypeError):
        try:
            return repair_callable(query, error, attempt)
        except TypeError:
            return repair_callable(query, error)


def run_with_reflection(
    execute_fn: Callable[[str], Any],
    initial_query: str,
    validate_fn: Optional[Callable[[str], Any]] = None,
    repair_fn: Optional[Callable[..., str]] = None,
    repair_prompt_fn: Optional[Callable[..., Union[str, Tuple[str, str]]]] = None,
    max_attempts: int = 3,
    on_attempt: Optional[Callable[[int, str, Optional[str]], None]] = None,
) -> Dict[str, Any]:
    """
    Universal self-correction reflection loop.

    Workflow:
      1. Validates `current_query` via `validate_fn` (if provided).
      2. If valid, executes `current_query` via `execute_fn`.
      3. If either validation or execution fails, uses `repair_fn` or `repair_prompt_fn`
         to generate an amended query for the next attempt.
      4. Repeats up to `max_attempts` times.

    Args:
        execute_fn: Callable executing the query and returning data (or (bool, data/error)).
        initial_query: Starting query, MQL payload, or code to execute.
        validate_fn: Optional validator returning (is_valid, error), bool, or validation result.
        repair_fn: Optional function accepting (query, error, attempt) and returning repaired query string.
        repair_prompt_fn: Optional prompt generator returning prompt string or (system_prompt, user_prompt)
                          to be invoked via `src.core.llm.call_llm`.
        max_attempts: Maximum retry attempts (default: 3).
        on_attempt: Optional callback hook `(attempt_num, query, error)` for telemetry/logging.

    Returns:
        dict: {
            "success": bool,
            "data": Any,
            "final_query": str,
            "attempts": int,
            "error": Optional[str],
            "history": List[dict]
        }
    """
    current_query = initial_query
    last_error: Optional[str] = None
    history: List[Dict[str, Any]] = []

    for attempt in range(1, max_attempts + 1):
        step_log: Dict[str, Any] = {
            "attempt": attempt,
            "query": current_query,
            "validation_error": None,
            "execution_error": None,
            "success": False,
        }

        # 1. Validation Check (Guardrails)
        is_valid, val_error = _evaluate_validation(validate_fn, current_query)
        if not is_valid:
            last_error = val_error or "Guardrail validation blocked query."
            step_log["validation_error"] = last_error
            history.append(step_log)

            if on_attempt:
                on_attempt(attempt, current_query, last_error)

            if attempt < max_attempts:
                current_query = _perform_repair(
                    repair_fn=repair_fn,
                    repair_prompt_fn=repair_prompt_fn,
                    query=current_query,
                    error=last_error,
                    attempt=attempt,
                )
                continue
            else:
                break

        # 2. Execution on Engine
        exec_success, data, exec_error = _evaluate_execution(execute_fn, current_query)
        if exec_success:
            step_log["success"] = True
            history.append(step_log)

            if on_attempt:
                on_attempt(attempt, current_query, None)

            return {
                "success": True,
                "data": data,
                "final_query": current_query,
                "attempts": attempt,
                "error": None,
                "history": history,
            }
        else:
            last_error = exec_error or "Execution error."
            step_log["execution_error"] = last_error
            history.append(step_log)

            if on_attempt:
                on_attempt(attempt, current_query, last_error)

            if attempt < max_attempts:
                current_query = _perform_repair(
                    repair_fn=repair_fn,
                    repair_prompt_fn=repair_prompt_fn,
                    query=current_query,
                    error=last_error,
                    attempt=attempt,
                )
            else:
                break

    return {
        "success": False,
        "data": [],
        "final_query": current_query,
        "attempts": max_attempts,
        "error": f"Failed after {max_attempts} attempts: {last_error}",
        "history": history,
    }


def _perform_repair(
    repair_fn: Optional[Callable[..., str]],
    repair_prompt_fn: Optional[Callable[..., Union[str, Tuple[str, str]]]],
    query: str,
    error: str,
    attempt: int
) -> str:
    """Internal helper to dispatch repair through custom function or LLM prompt."""
    if repair_fn is not None:
        repaired = _invoke_repair(repair_fn, query, error, attempt)
        return clean_repaired_code(str(repaired))

    if repair_prompt_fn is not None:
        prompt_res = _invoke_repair(repair_prompt_fn, query, error, attempt)
        try:
            from src.core.llm import call_llm
        except ImportError:
            try:
                from core.llm import call_llm
            except ImportError:
                call_llm = None

        if call_llm is not None:
            if isinstance(prompt_res, (tuple, list)) and len(prompt_res) == 2:
                sys_prompt, user_prompt = prompt_res[0], prompt_res[1]
                raw_response = call_llm(prompt=str(user_prompt), system_prompt=str(sys_prompt))
            else:
                raw_response = call_llm(prompt=str(prompt_res))
            return clean_repaired_code(raw_response)

    # If neither repair mechanism is available, retain current query
    return query


class CorrectionEngine:
    """
    Backward-compatible OOP adapter matching legacy F04 CorrectionEngine interface.
    Delegates all operations to pure functional `run_with_reflection`.
    """

    def __init__(self, db_engine: Any = None):
        self.db_engine = db_engine
        self._generator = None
        self._guardrail = None

    @property
    def generator(self):
        if self._generator is None:
            try:
                from backend.archive.legacy_pipeline.F02_generator import SQLGenerator
                self._generator = SQLGenerator(self.db_engine)
            except ImportError:
                try:
                    from F02_generator import SQLGenerator
                    self._generator = SQLGenerator(self.db_engine)
                except ImportError:
                    self._generator = None
        return self._generator

    @property
    def guardrail(self):
        if self._guardrail is None:
            try:
                from guardrails.sql_guard import SQLInjectionGuardrail
                self._guardrail = SQLInjectionGuardrail(self.db_engine)
            except ImportError:
                try:
                    from backend.src.guardrails.sql_guard import SQLInjectionGuardrail
                except ImportError:
                    from src.guardrails.sql_guard import SQLInjectionGuardrail
                self._guardrail = SQLInjectionGuardrail(self.db_engine)
        return self._guardrail

    def execute_safe(self, sql: str) -> Tuple[bool, Any]:
        """Executes SQL query safely returning (success, data_or_error)."""
        if self.db_engine and hasattr(self.db_engine, "execute_query"):
            try:
                res = self.db_engine.execute_query(sql)
                return True, res
            except Exception as e:
                return False, str(e)

        try:
            from engines.sql_engine import execute_sql_query
            from config import DEFAULT_CHINOOK_PATH
            res = execute_sql_query(DEFAULT_CHINOOK_PATH, sql)
            return True, res
        except Exception as e:
            return False, str(e)

    def build_reflection_prompt(
        self, user_question: str, failed_sql: str, error_message: str
    ) -> str:
        schema_context = (
            self.generator.get_schema_context()
            if hasattr(self.generator, "get_schema_context")
            else ""
        )
        return build_sql_repair_prompt(
            question=user_question,
            broken_sql=failed_sql,
            error_message=error_message,
            schema_context=schema_context,
        )

    def run_with_self_correction(
        self,
        user_question: str,
        initial_sql: Optional[str] = None,
        max_retries: int = 3,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[bool, Any, str, int]:
        """
        Legacy adapter method returning (success, data_or_error, final_sql, attempts).
        """
        starting_sql = initial_sql
        if not starting_sql:
            starting_sql = self.generator.generate_sql(
                user_question, conversation_history=conversation_history
            )

        schema_context = (
            self.generator.get_schema_context()
            if hasattr(self.generator, "get_schema_context")
            else ""
        )

        def _val(q: str):
            is_valid, reason, _ = self.guardrail.validate_sql(q)
            return is_valid, reason

        def _repair_prompt(q: str, err: str):
            return self.build_reflection_prompt(user_question, q, err)

        result = run_with_reflection(
            execute_fn=self.execute_safe,
            initial_query=starting_sql,
            validate_fn=_val,
            repair_prompt_fn=_repair_prompt,
            max_attempts=max_retries,
        )

        data_or_error = result["data"] if result["success"] else result["error"]
        return (
            result["success"],
            data_or_error,
            result["final_query"],
            result["attempts"],
        )
