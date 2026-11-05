import time
from typing import Dict, Any, Optional, List
from F09_nosql_engine import NoSQLEngine
from F10_nosql_generator import NoSQLGenerator
from F11_nosql_guardrails import NoSQLGuardrail


class TextToNoSQLPipeline:
    """
    End-to-End Enterprise Text-to-NoSQL Pipeline:
    Natural Language ➔ Multi-Collection MQL Generation ➔ Security Guardrails ➔ In-Memory Execution ➔ 3-Step Self-Correction.
    """

    def __init__(self, engine: Optional[NoSQLEngine] = None):
        self.engine = engine if engine != None else NoSQLEngine()
        self.generator = NoSQLGenerator()
        self.guardrail = NoSQLGuardrail()

    def run_pipeline(
        self,
        question: str,
        max_retries: int = 3,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        target_language: str = "auto"
    ) -> Dict[str, Any]:
        """
        Executes natural language question across available NoSQL collections with multi-turn memory.
        Includes a 3-attempt self-repair loop for syntax errors or invalid collection/field references.
        """
        start_time = time.time()
        feedback: Optional[str] = None
        last_mql: str = ""
        last_error: str = ""

        # Multi-Language Routing: If user requested Python (PyMongo), JS, Java, R, C#
        target_lang = (target_language or "auto").lower()
        if target_lang not in ["auto", "nosql", "mongodb", "mql"]:
            from F17_multi_language_generator import MultiLanguageGenerator
            generator = MultiLanguageGenerator()
            schema = self.engine.get_all_schemas_context()
            gen_res = generator.generate_code(
                question=question,
                schema_context=schema,
                db_type="nosql",
                target_language=target_lang,
                db_name="nosql_store",
                table_or_sheet_names=self.engine.get_collection_names()
            )

            data = []
            if gen_res.get("eval_mql"):
                try:
                    is_valid, _, parsed_payload, target_col = self.guardrail.validate_and_parse(
                        raw_mql=gen_res["eval_mql"],
                        available_collections=self.engine.get_collection_names()
                    )
                    if is_valid:
                        data = self.engine.execute_mql(parsed_payload, target_col)
                except Exception:
                    pass

            if not data:
                try:
                    fallback_mql = self.generator.generate_mql(
                        question=question,
                        schemas_context=schema,
                        collection_names=self.engine.get_collection_names()
                    )
                    parsed_fallback = self.generator.parse_queries(fallback_mql)
                    single_mql = parsed_fallback[0]["mql"] if isinstance(parsed_fallback, list) and parsed_fallback else fallback_mql
                    is_valid, _, parsed_payload, target_col = self.guardrail.validate_and_parse(
                        raw_mql=single_mql,
                        available_collections=self.engine.get_collection_names()
                    )
                    if is_valid:
                        data = self.engine.execute_mql(parsed_payload, target_col)
                except Exception:
                    pass

            latency = round((time.time() - start_time) * 1000, 2)
            code = gen_res.get("code", "")
            return {
                "status": "SUCCESS",
                "title": gen_res.get("title", question[:40]),
                "final_query": code,
                "final_sql": code,
                "code": code,
                "code_type": target_lang,
                "data": data,
                "latency_ms": latency,
                "attempts": 1,
                "confidence_score": 0.95,
                "error": None,
                "summary": gen_res.get("explanation", f"Generated {target_lang.upper()} query code for NoSQL store."),
                "sub_queries": [{
                    "title": gen_res.get("title", question[:40]),
                    "sql": code,
                    "data": data,
                    "status": "SUCCESS"
                }]
            }

        schemas_context = self.engine.get_all_schemas_context()
        collection_names = self.engine.get_collection_names()

        # 1. Generate MQL query or decompose compound queries
        raw_mql = self.generator.generate_mql(
            question=question,
            schemas_context=schemas_context,
            collection_names=collection_names,
            feedback=feedback,
            conversation_history=conversation_history
        )
        parsed_result = self.generator.parse_queries(raw_mql)

        # Intercept Out-of-Domain / Schema Relevancy Mismatches
        if isinstance(parsed_result, dict) and parsed_result.get("is_relevant") is False:
            latency = round((time.time() - start_time) * 1000, 2)
            return {
                "status": "OUT_OF_DOMAIN",
                "final_sql": None,
                "data": [],
                "summary": parsed_result.get(
                    "reason", 
                    "This NoSQL database does not contain the requested collections or entities."
                ),
                "is_relevant": False,
                "needed_tables": parsed_result.get("needed_tables", []),
                "available_tables": collection_names,
                "suggested_questions": parsed_result.get("suggested_questions", []),
                "confidence_score": 1.0,
                "latency_ms": latency,
                "sub_queries": []
            }

        query_items = parsed_result

        # 2. Single Query Path (Standard Execution)
        if len(query_items) <= 1:
            single_mql = query_items[0]["mql"] if query_items else raw_mql
            for attempt in range(1, max_retries + 1):
                try:
                    is_valid, guard_error, parsed_payload, target_col = self.guardrail.validate_and_parse(
                        raw_mql=single_mql,
                        available_collections=collection_names
                    )
                    if is_valid == False:
                        last_error = guard_error or "Guardrail validation failed."
                        feedback = f"Guardrail Error on attempt {attempt}: {last_error}"
                        single_mql = self.generator.generate_mql(
                            question=question,
                            schemas_context=schemas_context,
                            collection_names=collection_names,
                            feedback=feedback,
                            conversation_history=conversation_history
                        )
                        continue

                    data = self.engine.execute_mql(
                        query_payload=parsed_payload,
                        target_collection=target_col
                    )
                    latency = round((time.time() - start_time) * 1000, 2)
                    col_display = target_col if target_col else "database"
                    single_title = query_items[0].get("title", "Query Objective") if query_items else "Query Objective"
                    return {
                        "status": "SUCCESS",
                        "title": single_title,
                        "final_query": single_mql,
                        "final_sql": single_mql,
                        "data": data,
                        "latency_ms": latency,
                        "attempts": attempt,
                        "confidence_score": 0.95,
                        "error": None,
                        "summary": f"Found {len(data)} matching records from {col_display}.",
                        "sub_queries": [{
                            "title": single_title,
                            "sql": single_mql,
                            "data": data,
                            "status": "SUCCESS"
                        }]
                    }
                except Exception as e:
                    last_error = str(e)
                    feedback = f"Runtime Error on attempt {attempt}: {last_error}"

            latency = round((time.time() - start_time) * 1000, 2)
            return {
                "status": "FAILED",
                "final_query": single_mql,
                "final_sql": single_mql,
                "data": [],
                "latency_ms": latency,
                "attempts": max_retries,
                "confidence_score": 0.0,
                "error": last_error,
                "summary": f"Query execution failed: {last_error}",
                "sub_queries": []
            }

        # 3. Multi-Query Decomposition Path (Compound Requests)
        executed_sub_queries = []
        overall_success = True

        for i, item in enumerate(query_items, 1):
            sub_title = item.get("title", f"Query {i}")
            sub_mql = item.get("mql", "").strip()

            is_valid, guard_error, parsed_payload, target_col = self.guardrail.validate_and_parse(
                raw_mql=sub_mql,
                available_collections=collection_names
            )
            if not is_valid:
                executed_sub_queries.append({
                    "title": sub_title,
                    "sql": sub_mql,
                    "data": [],
                    "error": guard_error,
                    "status": "FAILED"
                })
                overall_success = False
                continue

            sub_data = self.engine.execute_mql(
                query_payload=parsed_payload,
                target_collection=target_col
            )
            executed_sub_queries.append({
                "title": sub_title,
                "sql": sub_mql,
                "data": sub_data,
                "error": None,
                "status": "SUCCESS"
            })

        latency = round((time.time() - start_time) * 1000, 2)
        first_successful = next(
            (sq for sq in executed_sub_queries if sq["status"] == "SUCCESS"),
            executed_sub_queries[0]
        )
        return {
            "status": "SUCCESS" if overall_success else "PARTIAL",
            "is_multi_query": True,
            "final_query": first_successful["sql"],
            "final_sql": first_successful["sql"],
            "data": first_successful["data"],
            "latency_ms": latency,
            "attempts": 1,
            "confidence_score": 0.95 if overall_success else 0.70,
            "error": None,
            "summary": f"Executed {len(executed_sub_queries)} distinct NoSQL sub-queries successfully.",
            "sub_queries": executed_sub_queries
        }
