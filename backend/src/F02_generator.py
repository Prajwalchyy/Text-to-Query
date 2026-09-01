from F00_imports import *
from F01_db_engine import DatabaseEngine


class SQLGenerator:
    def __init__(self, db_engine: DatabaseEngine = None):
        self.db_engine = db_engine or DatabaseEngine()

        api_key = os.getenv("API_KEY")
        base_url = os.getenv("API_URL")
        model = os.getenv("MODEL")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = model

    def get_schema_context(self) -> str:
        """
        Loops through all tables and builds a text representation of the schema.
        """
        schema_lines = []
        tables = self.db_engine.get_table_names()

        for table in tables:
            columns = self.db_engine.get_table_schema(table)
            col_string = [f"{col['name']} {col['type']}" for col in columns]
            schema_lines.append(f"Table: {table}\nColumns: {', '.join(col_string)}\n")

        return "\n".join(schema_lines)

    def System_Prompts(self) -> str:
        schema = self.get_schema_context()
        prompt = f"""You are an expert SQL Database Engineer.
Your job is to translate user questions into valid SQLite SQL queries based on the database schema provided below.

Database Schema:
{schema}

Strict Rules:
1. Return ONLY the raw SQL query.
2. Do NOT wrap the query in markdown backticks (no ```sql or ```).
3. Do NOT provide explanations, commentary, or conversational text.
4. Only use tables and columns defined in the schema above.
5. Use proper SQLite syntax and correct JOIN conditions.
"""
        return prompt

    def generate_sql(self, question: str) -> str:
        """sql generate by llm"""
        System_Prompt = self.System_Prompts()
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": System_Prompt},
                {"role": "user", "content": question}
            ]
        )

        sql_query_result = response.choices[0].message.content.strip()
        if "```" in sql_query_result:
            parts = sql_query_result.split("```")
            sql_query_result = parts[1] if len(parts) > 1 else parts[0]
            if sql_query_result.startswith("sql"):
                sql_query_result = sql_query_result[3:]
        return sql_query_result.strip()


if __name__ == "__main__":
    generator = SQLGenerator()

    # 3 Real Questions to Test
    test_questions = [
        "How many total tracks are in the database?",
        "List the top 5 customers by total invoice spending.",
        "Which 3 artists have the most albums?"
    ]

    for i, question in enumerate(test_questions, 1):
        print(f"\n================ Test Question {i} ================")
        print(f"Question: {question}")

        # 1. Generate SQL from English
        sql = generator.generate_sql(question)
        print(f"\nGenerated SQL:\n{sql}")

        # 2. Execute on Database to see real data!
        print("\nQuery Results from Database:")
        results = generator.db_engine.execute_query(sql)
        for row in results[:5]:  # Show up to 5 rows
            print(row)
