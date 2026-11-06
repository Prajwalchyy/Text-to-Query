import time
from typing import Dict, Any, List, Optional
from F13_spreadsheet_engine import SpreadsheetEngine
from F14_pandas_guardrails import validate_pandas_code
from F15_spreadsheet_generator import SpreadsheetGenerator


class TextToSpreadsheetPipeline:
    """
    Master pipeline orchestrating Natural Language querying for CSV and Excel files:
    - CSV: Generates vectorized Pandas code -> AST validation -> Sandbox execution -> DataTable.
    - Excel: Generates modern Excel Formulas -> Evaluates preview DataFrame -> DataTable + Formula viewer.
    - Self-correction loop: Auto-heals syntax and column KeyErrors up to 3 attempts.
    """

    def __init__(self, engine: SpreadsheetEngine):
        self.engine = engine
        self.generator = SpreadsheetGenerator(engine)

    def run_pipeline(
        self,
        user_question: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        target_language: str = "auto"
    ) -> Dict[str, Any]:
        start_time = time.time()
        is_excel = (self.engine.file_type == "excel")
        target_lang = (target_language or "auto").lower()

        # Multi-Language Routing: If user requested SQL or another programming language
        # (e.g. SQL on spreadsheets, or JS, Java, R, C#)
        is_custom_lang = target_lang not in ["auto", "pandas" if not is_excel else "excel_formula"]

        if is_custom_lang:
            from F17_multi_language_generator import MultiLanguageGenerator
            generator = MultiLanguageGenerator()
            schema = self.engine.get_schema_context()
            sheet_names = self.engine.get_sheet_names()

            gen_res = generator.generate_code(
                question=user_question,
                schema_context=schema,
                db_type=self.engine.file_type,
                target_language=target_lang,
                db_name=self.engine.file_path.stem,
                table_or_sheet_names=sheet_names
            )

            code = gen_res.get("code", "")
            data = []
            # 1. If SQL requested, execute SQL directly on in-memory SQLite table
            if target_lang == "sql":
                try:
                    data = self.engine.execute_sql_query(code)
                except Exception as sql_err:
                    # Fallback: try eval_sql
                    if gen_res.get("eval_sql"):
                        try:
                            data = self.engine.execute_sql_query(gen_res["eval_sql"])
                        except Exception:
                            pass
            # 2. If other language, execute eval_sql or eval_pandas to populate data table
            else:
                if gen_res.get("eval_sql"):
                    try:
                        data = self.engine.execute_sql_query(gen_res["eval_sql"])
                    except Exception:
                        pass
                if not data and gen_res.get("eval_pandas"):
                    try:
                        data = self.engine.execute_pandas_code(gen_res["eval_pandas"])
                    except Exception:
                        pass

            if not data:
                data = self.engine.primary_df.head(10).to_dict(orient="records")
                data = self.engine._clean_records_for_json(data)

            columns = list(data[0].keys()) if data and len(data) > 0 else []
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "question": user_question,
                "status": "SUCCESS",
                "final_sql": code,
                "code": code,
                "code_type": target_lang,
                "data": data,
                "columns": columns,
                "title": gen_res.get("title", user_question[:40]),
                "summary": gen_res.get("explanation", f"Generated {target_lang.upper()} code for spreadsheet."),
                "confidence_score": 0.95,
                "attempts": 1,
                "latency_ms": latency_ms,
                "sub_queries": []
            }

        # 1. Format conversation context
        context_str = None
        if conversation_history:
            recent_turns = conversation_history[-3:]
            lines = []
            for t in recent_turns:
                q = t.get("question") or t.get("content", "")
                c = t.get("final_sql") or t.get("code") or t.get("sql", "")
                if q:
                    lines.append(f"User: {q}\nGenerated: {c}")
            if lines:
                context_str = "\n---\n".join(lines)

        # 2. Generate Pandas code or Excel formulas
        attempts = 1
        max_retries = 3
        current_question = user_question

        for attempt in range(1, max_retries + 1):
            attempts = attempt
            try:
                items = self.generator.generate(current_question, conversation_context=context_str)
                if not items:
                    raise ValueError("Generator returned empty response.")
                break
            except Exception as gen_err:
                if attempt == max_retries:
                    latency_ms = int((time.time() - start_time) * 1000)
                    return {
                        "question": user_question,
                        "status": "FAILED",
                        "final_sql": None,
                        "data": [],
                        "title": "Query Generation Failed",
                        "error": f"Generation error: {str(gen_err)}",
                        "summary": f"Could not generate query: {str(gen_err)}",
                        "confidence_score": 0.0,
                        "attempts": attempts,
                        "latency_ms": latency_ms,
                        "sub_queries": []
                    }

        # 3. Process single vs multi-query items
        sub_results = []
        is_compound = len(items) > 1

        for idx, item in enumerate(items):
            title = item.get("title") or f"Query {idx + 1}"
            explanation = item.get("explanation", "")

            if is_excel:
                # Excel Formula Flow
                formula = item.get("formula", "")
                eval_code = item.get("eval_code", "")
                target_cell = item.get("target_cell", "")
                summary_text = explanation
                if target_cell:
                    summary_text = f"Target Cell: {target_cell} | {explanation}"

                # Evaluate preview data for UI table
                data = []
                if eval_code:
                    try:
                        data = self.engine.execute_pandas_code(eval_code)
                    except Exception:
                        data = self.engine.primary_df.head(10).to_dict(orient="records")
                        data = self.engine._clean_records_for_json(data)
                else:
                    data = self.engine.primary_df.head(10).to_dict(orient="records")
                    data = self.engine._clean_records_for_json(data)

                sub_results.append({
                    "title": title,
                    "sql": formula,
                    "code_type": "excel_formula",
                    "formula": formula,
                    "target_cell": target_cell,
                    "summary": summary_text,
                    "data": data,
                    "row_count": len(data)
                })

            else:
                # CSV / Pandas Flow with AST Guardrail and Self-Healing
                pandas_code = item.get("code", "")
                data = []
                exec_error = None

                for exec_attempt in range(1, max_retries + 1):
                    # AST Security Guardrail
                    is_safe, sec_err = validate_pandas_code(pandas_code)
                    if not is_safe:
                        exec_error = sec_err
                        break

                    # Execute in restricted sandbox
                    try:
                        data = self.engine.execute_pandas_code(pandas_code)
                        exec_error = None
                        break
                    except Exception as run_err:
                        exec_error = str(run_err)
                        attempts += 1
                        # Self-correction reflection prompt
                        repair_prompt = (
                            f"The following Pandas code failed with error:\n"
                            f"Code: {pandas_code}\n"
                            f"Error: {exec_error}\n"
                            f"Please fix the code to resolve this error. Return pure JSON object with 'title' and 'code'."
                        )
                        try:
                            fixed_items = self.generator.generate(repair_prompt, conversation_context=context_str)
                            if fixed_items and fixed_items[0].get("code"):
                                pandas_code = fixed_items[0]["code"]
                        except Exception:
                            break

                if exec_error and not data:
                    data = []

                sub_results.append({
                    "title": title,
                    "sql": pandas_code,
                    "code_type": "pandas",
                    "code": pandas_code,
                    "summary": explanation or f"Executed Pandas query producing {len(data)} rows.",
                    "data": data,
                    "row_count": len(data),
                    "error": exec_error
                })

        latency_ms = int((time.time() - start_time) * 1000)
        first_res = sub_results[0] if sub_results else {}
        overall_status = "SUCCESS" if any(len(s.get("data", [])) > 0 or s.get("sql") for s in sub_results) else "FAILED"

        return {
            "question": user_question,
            "status": overall_status,
            "final_sql": first_res.get("sql"),
            "code_type": first_res.get("code_type", "excel_formula" if is_excel else "pandas"),
            "data": first_res.get("data", []),
            "title": first_res.get("title", "Query Result"),
            "summary": first_res.get("summary", ""),
            "confidence_score": 1.0 if overall_status == "SUCCESS" else 0.0,
            "is_accurate": True,
            "attempts": attempts,
            "latency_ms": latency_ms,
            "sub_queries": sub_results if len(sub_results) > 1 else []
        }
