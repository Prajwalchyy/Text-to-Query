from F00_imports import *
from F01_db_engine import DatabaseEngine
from F02_generator import SQLGenerator
from F03_guardrails import SQLInjectionGuardrail


class CorrectionEngine:
    def __init__(self, db_engine: DatabaseEngine = None):
        self.db_engine = db_engine or DatabaseEngine()
        self.generator = SQLGenerator(self.db_engine)
        self.guardrail = SQLInjectionGuardrail(self.db_engine)

    def execute_safe(self, sql: str):
        """
        Executes SQL without crashing.
        Returns: (True, rows) if success, or (False, error_message) if it fails.
        """
        try:
            result = self.db_engine.execute_query(sql)
            return True, result
        except Exception as e:
            return False, str(e)

    def build_reflection_prompt(
        self, user_question: str, failed_sql: str, error_message: str
    ) -> str:
        """
        Builds the reflection prompt feeding the error and schema back to the LLM.
        """
        prompt = f"""You are an expert SQL Database Engineer fixing a failed SQLite query.

User Question: {user_question}
Failed SQL Query: {failed_sql}
Database Error: {error_message}

Database Schema:
{self.generator.get_schema_context()}

Instructions:
1. Look at the database error and the schema above to identify the mistake.
2. Return ONLY the corrected SQLite SQL query.
3. Do NOT wrap the query in markdown backticks or commentary.
"""
        return prompt

    def run_with_self_correction(
        self,
        user_question: str,
        initial_sql: str = None,
        max_retries: int = 3,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ):
        """
        End-to-end pipeline:
        1. Uses provided SQL or generates initial SQL from question (with multi-turn memory).
        2. Validates with guardrails.
        3. Executes query safely.
        4. If it fails, asks the AI to repair it (up to max_retries).
        Returns: (success: bool, data_or_error: list/str, final_sql: str, attempts: int)
        """
        current_sql = initial_sql or self.generator.generate_sql(
            user_question, conversation_history=conversation_history
        )
        last_error = ""

        for attempt in range(1, max_retries + 1):
            print(f"\n[Attempt {attempt}] Testing SQL: {current_sql}")

            # 1. Check Guardrails
            is_valid, reason, safe_sql = self.guardrail.validate_sql(current_sql)
            if is_valid == False:
                print(f"[Attempt {attempt}] Guardrail Blocked: {reason}")
                last_error = reason
            else:
                # 2. Execute on Database
                success, output = self.execute_safe(safe_sql)
                if success:
                    print(f"[Attempt {attempt}] Success! Query executed cleanly.")
                    return True, output, safe_sql, attempt
                else:
                    print(f"[Attempt {attempt}] Database Error: {output}")
                    last_error = output

            # 3. If failed and retries remain, ask AI to fix it
            if attempt < max_retries:
                print(f"[Attempt {attempt}] Asking AI to repair query...")
                prompt = self.build_reflection_prompt(
                    user_question, current_sql, last_error
                )

                response = self.generator.client.chat.completions.create(
                    model=self.generator.model,
                    temperature=0.0,
                    messages=[
                        {"role": "system", "content": prompt},
                        {
                            "role": "user",
                            "content": "Please output the corrected SQL query only.",
                        },
                    ],
                )
                fixed_sql = response.choices[0].message.content.strip()
                # Clean backticks if any
                if "```" in fixed_sql:
                    parts = fixed_sql.split("```")
                    fixed_sql = parts[1] if len(parts) > 1 else parts[0]
                    if fixed_sql.startswith("sql"):
                        fixed_sql = fixed_sql[3:]
                current_sql = fixed_sql.strip()

        return (
            False,
            f"Failed after {max_retries} attempts: {last_error}",
            current_sql,
            max_retries,
        )


if __name__ == "__main__":
    engine = CorrectionEngine()

    print("=== TEST 1: Normal Question (Instant Success) ===")
    success, data, sql, attempts = engine.run_with_self_correction(
        "How many total tracks are there?"
    )
    print(
        f"Result -> Success: {success}, Attempts: {attempts}, SQL: {sql}, Rows: {data}\n"
    )

    print("=== TEST 2: Intentionally Broken Column (Auto-Repair in Action!) ===")
    broken_sql = "SELECT NonExistentCol, Title FROM Album LIMIT 2;"
    success, data, sql, attempts = engine.run_with_self_correction(
        user_question="List 2 album titles and artist IDs.", initial_sql=broken_sql
    )
    print(f"Result -> Success: {success}, Attempts: {attempts}")
    print(f"Final Repaired SQL: {sql}")
    print(f"Returned Data: {data}")
