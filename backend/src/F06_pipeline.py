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

    def run_pipeline(self, user_question: str) -> dict:
        """
        Runs the full end-to-end Text-to-SQL pipeline:
        Generate -> Guardrail -> Execute/Auto-Repair -> Evaluate -> Telemetry
        """
        start_time = time.time()

        # 1. Execute with Self-Correction & Guardrails
        success, data_or_error, final_sql, attempts = (
            self.correction_engine.run_with_self_correction(user_question)
        )

        # If execution failed after retries:
        if success == False:
            latency_ms = int((time.time() - start_time) * 1000)
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
            }

        # 2. Evaluate with LLM-as-a-Judge & Explainer
        eval_result = self.evaluator.evaluate(user_question, final_sql, data_or_error)

        # 3. Calculate Telemetry Latency
        latency_ms = int((time.time() - start_time) * 1000)

        # 4. Return Master Response Bundle
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