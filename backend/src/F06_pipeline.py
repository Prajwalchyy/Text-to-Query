import time
from F00_imports import *
from F01_db_engine import DatabaseEngine
from F02_generator import SQLGenerator
from F03_guardrails import SQLInjectionGuardrail
from F04_self_correction import CorrectionEngine
from F05_evaluator import SQLEvaluator


class TextToSQLPipeline:
    def __init__(self, db_engine: DatabaseEngine = None):
        # 1. Single shared database engine
        self.db_engine = db_engine or DatabaseEngine()

        # 2. Connect all 5 pipeline modules
        self.generator = SQLGenerator(self.db_engine)
        self.guardrail = SQLInjectionGuardrail(self.db_engine)
        self.correction_engine = CorrectionEngine(self.db_engine)
        self.evaluator = SQLEvaluator()

    def run_pipeline(
        self,
        user_question: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> dict:
        """
        Runs the full end-to-end Text-to-SQL pipeline with multi-query decomposition:
        Generate/Decompose -> Guardrail -> Execute/Auto-Repair -> Evaluate -> Telemetry
        """
        start_time = time.time()

        # 1. Generate SQL or decompose compound query
        raw_output = self.generator.generate_sql(
            user_question, conversation_history=conversation_history
        )
        parsed_result = self.generator.parse_queries(raw_output)

        # Intercept Out-of-Domain / Schema Relevancy Mismatches
        if isinstance(parsed_result, dict) and parsed_result.get("is_relevant") is False:
            latency_ms = int((time.time() - start_time) * 1000)
            existing_tables = self.db_engine.get_table_names()
            return {
                "question": user_question,
                "status": "OUT_OF_DOMAIN",
                "final_sql": None,
                "data": [],
                "summary": parsed_result.get(
                    "reason", 
                    "This database does not contain the tables or entities requested."
                ),
                "is_relevant": False,
                "needed_tables": parsed_result.get("needed_tables", []),
                "available_tables": existing_tables,
                "suggested_questions": parsed_result.get("suggested_questions", []),
                "confidence_score": 1.0,
                "is_accurate": True,
                "attempts": 1,
                "latency_ms": latency_ms,
                "sub_queries": []
            }

        query_items = parsed_result

        # 2. Single Query Path (Standard Execution)
        if len(query_items) <= 1:
            initial_sql = query_items[0]["sql"] if query_items else None
            success, data_or_error, final_sql, attempts = (
                self.correction_engine.run_with_self_correction(
                    user_question, initial_sql=initial_sql, conversation_history=conversation_history
                )
            )

            latency_ms = int((time.time() - start_time) * 1000)
            if success == False:
                return {
                    "question": user_question,
                    "status": "FAILED",
                    "final_sql": final_sql,
                    "data": [],
                    "error": str(data_or_error),
                    "summary": f"Query execution failed: {data_or_error}",
                    "confidence_score": 0.0,
                    "is_accurate": False,
                    "attempts": attempts,
                    "latency_ms": latency_ms,
                    "sub_queries": []
                }

            eval_result = self.evaluator.evaluate(user_question, final_sql, data_or_error)
            return {
                "question": user_question,
                "status": "SUCCESS",
                "final_sql": final_sql,
                "data": data_or_error,
                "summary": eval_result.get("summary", ""),
                "confidence_score": eval_result.get("confidence_score", 0.90),
                "is_accurate": eval_result.get("is_accurate", True),
                "attempts": attempts,
                "latency_ms": latency_ms,
                "sub_queries": [{
                    "title": query_items[0].get("title", "Result"),
                    "sql": final_sql,
                    "data": data_or_error,
                    "status": "SUCCESS"
                }]
            }

        # 3. Multi-Query Decomposition Path (Compound Requests)
        executed_sub_queries = []
        overall_success = True
        total_attempts = 0

        for i, item in enumerate(query_items, 1):
            sub_title = item.get("title", f"Query {i}")
            sub_sql = item.get("sql", "").strip()

            sub_success, sub_data, safe_sql, attempts = (
                self.correction_engine.run_with_self_correction(
                    user_question=f"{user_question} - Part {i}: {sub_title}",
                    initial_sql=sub_sql,
                    conversation_history=conversation_history
                )
            )
            total_attempts += attempts
            if not sub_success:
                overall_success = False

            executed_sub_queries.append({
                "title": sub_title,
                "sql": safe_sql,
                "data": sub_data if sub_success else [],
                "error": str(sub_data) if not sub_success else None,
                "status": "SUCCESS" if sub_success else "FAILED"
            })

        latency_ms = int((time.time() - start_time) * 1000)
        first_successful = next(
            (sq for sq in executed_sub_queries if sq["status"] == "SUCCESS"),
            executed_sub_queries[0]
        )

        return {
            "question": user_question,
            "status": "SUCCESS" if overall_success else "PARTIAL",
            "is_multi_query": True,
            "final_sql": first_successful["sql"],
            "data": first_successful["data"],
            "sub_queries": executed_sub_queries,
            "summary": f"Executed {len(executed_sub_queries)} distinct sub-queries successfully.",
            "confidence_score": 0.95 if overall_success else 0.70,
            "is_accurate": overall_success,
            "attempts": total_attempts,
            "latency_ms": latency_ms,
        }


if __name__ == "__main__":
    pipeline = TextToSQLPipeline()

    print("==================================================")
    print("      TEST 1: Complex Business Query Test        ")
    print("==================================================")
    question = "Which 3 artists have the most albums in the catalog?"
    result = pipeline.run_pipeline(question)

    print(f"\n[Status]:     {result['status']}")
    print(f"[SQL]:        {result['final_sql']}")
    print(f"[Rows]:       {len(result['data'])} rows returned")
    print(f"[Confidence]: {result['confidence_score'] * 100:.0f}%")
    print(f"[Attempts]:   {result['attempts']}")
    print(f"[Latency]:    {result['latency_ms']} ms")
    print(f"[Summary]:    {str(result['summary']).encode('ascii', 'replace').decode('ascii')}")

    print("\n==================================================")
    print("      TEST 2: Attack Query Security Test          ")
    print("==================================================")
    attack_q = "DROP TABLE Customer;"
    attack_res = pipeline.run_pipeline(attack_q)
    print(f"[Status]:     {attack_res['status']}")
    print(f"[Summary]:    {attack_res['summary']}")
    print(f"[Latency]:    {attack_res['latency_ms']} ms")