import time
from typing import Dict, Any, Optional
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

    def run_pipeline(self, question: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Executes natural language question across available NoSQL collections.
        Includes a 3-attempt self-repair loop for syntax errors or invalid collection/field references.
        """
        start_time = time.time()
        feedback: Optional[str] = None
        last_mql: str = ""
        last_error: str = ""

        schemas_context = self.engine.get_all_schemas_context()
        collection_names = self.engine.get_collection_names()

        for attempt in range(1, max_retries + 1):
            try:
                # 1. Generate MQL query
                raw_mql = self.generator.generate_mql(
                    question=question,
                    schemas_context=schemas_context,
                    collection_names=collection_names,
                    feedback=feedback
                )
                last_mql = raw_mql

                # 2. Guardrail Safety, Collection Extraction & JSON Parsing
                is_valid, guard_error, parsed_payload, target_col = self.guardrail.validate_and_parse(
                    raw_mql=raw_mql,
                    available_collections=collection_names
                )
                if is_valid == False:
                    last_error = guard_error or "Guardrail validation failed."
                    feedback = f"Guardrail Error on attempt {attempt}: {last_error}"
                    continue

                # 3. Execute in-memory MQL against target collection
                data = self.engine.execute_mql(
                    query_payload=parsed_payload,
                    target_collection=target_col
                )

                latency = round((time.time() - start_time) * 1000, 2)
                col_display = target_col if target_col else "database"
                return {
                    "status": "SUCCESS",
                    "final_query": raw_mql,
                    "final_sql": raw_mql,
                    "data": data,
                    "latency_ms": latency,
                    "attempts": attempt,
                    "confidence_score": 0.95,
                    "error": None,
                    "summary": f"Found {len(data)} matching records from {col_display}."
                }

            except Exception as e:
                last_error = str(e)
                feedback = f"Execution Error on attempt {attempt}: {last_error}"

        latency = round((time.time() - start_time) * 1000, 2)
        return {
            "status": "FAILED",
            "final_query": last_mql,
            "final_sql": last_mql,
            "data": [],
            "latency_ms": latency,
            "attempts": max_retries,
            "confidence_score": 0.0,
            "error": f"Failed after {max_retries} attempts: {last_error}",
            "summary": "NoSQL query execution failed."
        }
