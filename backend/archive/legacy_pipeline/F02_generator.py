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
1. OUTPUT FORMAT:
   - For standard single-question requests: Output a strict JSON object without markdown fences containing a concise, exact title summarizing what the query does, and the raw SQL:
     {{
       "title": "Top Customers Ranked by Total Spending",
       "sql": "SELECT ...;"
     }}
   - For compound or multi-part questions requiring separate reports (e.g. "1. List all customers, 2. Total orders per customer"):
     Output a strict JSON array of objects without markdown fences:
     [
       {{"title": "1. All Customers", "sql": "SELECT ...;"}},
       {{"title": "2. Total Orders Per Customer", "sql": "SELECT ...;"}}
     ]
   - (If raw SQL without JSON is ever generated, it will be handled as fallback).
2. Do NOT wrap queries in markdown backticks (no ```sql or ```).
3. Do NOT provide explanations, commentary, or conversational text outside the JSON.
4. Only use tables and columns defined in the schema above.
5. Use proper SQLite syntax and correct JOIN conditions.
6. When asked to find BOTH highest and lowest (or top and bottom) records in a single query, use UNION ALL combining two subqueries formatted strictly as:
   SELECT * FROM (SELECT ..., 'Highest' AS Category FROM ... ORDER BY ... DESC LIMIT N)
   UNION ALL
   SELECT * FROM (SELECT ..., 'Lowest' AS Category FROM ... ORDER BY ... ASC LIMIT N);
   (In SQLite, any ORDER BY with LIMIT preceding a UNION ALL MUST be wrapped inside `SELECT * FROM (...)`).
7. For aggregation queries counting records per parent entity (e.g. orders per customer), use LEFT JOIN with COUNT(child.id) and GROUP BY so entities with zero records are accurately included.
8. MULTI-TURN CONVERSATION & PRONOUN RESOLUTION:
   - When a "PREVIOUS CONVERSATION CONTEXT" block is provided, use it to understand what the user is referring to.
   - If the current question contains pronouns or coreferences (e.g. "their", "them", "those", "that customer", "the first one", "the same ones"), resolve them using the prior questions and generated SQL.
   - If the current question refines, filters, or sorts the previous result (e.g. "now sort by date", "filter for only 2024", "include their email too"), modify the previous SQL query appropriately.
   - If the question is an independent, new topic, ignore previous context and generate a clean standalone query.
9. SCHEMA RELEVANCY & OUT-OF-DOMAIN QUESTIONS:
    - Carefully check if the entities, tables, or business concepts requested by the user physically exist in the Database Schema above.
    - If the user asks about concepts or tables completely absent from this schema (e.g. asking for e-commerce products, shopping cart, shipping, or inventory when connected to a music database; or asking for hospital patients on a sales database; or general chit-chat):
      DO NOT force an unrelated query.
      DO NOT substitute tables (e.g. do NOT substitute 'Track' for 'Product').
      Instead, output a strict JSON object without markdown fences:
      {{
        "is_relevant": false,
        "reason": "Clear explanation of what was requested and why this database cannot answer it.",
        "needed_tables": ["Products", "Inventory"],
        "suggested_questions": [
          "Relevant question 1 that CAN be answered by this database",
          "Relevant question 2 that CAN be answered by this database",
          "Relevant question 3 that CAN be answered by this database"
        ]
      }}
"""
        return prompt

    @staticmethod
    def parse_queries(raw_output: str) -> Union[List[Dict[str, str]], Dict[str, Any]]:
        """
        Parses generator output into a structured list of query tasks:
        [{"title": "...", "sql": "..."}], or an out-of-domain rejection dict.
        Handles single raw SQL queries, JSON objects, JSON arrays for compound prompts,
        and JSON objects for out-of-domain schema mismatch rejections.
        """
        cleaned = raw_output.strip()
        # Remove markdown code fences if present
        if "```" in cleaned:
            parts = cleaned.split("```")
            cleaned = parts[1] if len(parts) > 1 else parts[0]
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
            elif cleaned.lower().startswith("sql"):
                cleaned = cleaned[3:].strip()

        # 1. Check if output is a JSON object (out-of-domain rejection OR structured single query)
        if cleaned.startswith("{") and cleaned.endswith("}"):
            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    if parsed.get("is_relevant") is False:
                        return parsed
                    elif "sql" in parsed or "query" in parsed:
                        sql_str = (parsed.get("sql") or parsed.get("query") or "").strip()
                        title_str = parsed.get("title") or "Query Objective"
                        if sql_str:
                            return [{"title": title_str, "sql": sql_str}]
            except Exception:
                pass

        # 2. Check if output is a JSON array for compound multi-part questions
        if cleaned.startswith("[") and cleaned.endswith("]"):
            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict) and "sql" in parsed[0]:
                    return [
                        {
                            "title": item.get("title", f"Query {i + 1}"),
                            "sql": item.get("sql", "").strip()
                        }
                        for i, item in enumerate(parsed)
                        if item.get("sql")
                    ]
            except Exception:
                pass

        # 3. Fallback to single SQL query
        return [{"title": "Query Objective", "sql": cleaned}]

    def generate_sql(self, question: str, conversation_history: Optional[List[Dict[str, Any]]] = None) -> str:
        """sql generate by llm with optional multi-turn conversation memory"""
        System_Prompt = self.System_Prompts()

        # Build context-aware prompt if previous history is available
        if conversation_history and len(conversation_history) > 0:
            history_blocks = ["PREVIOUS CONVERSATION CONTEXT (for pronoun & reference resolution):"]
            for msg in conversation_history:
                role = "User" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "").strip()
                sql = msg.get("sql")
                if role == "User" and content:
                    history_blocks.append(f'User asked: "{content}"')
                elif role == "Assistant":
                    if sql:
                        history_blocks.append(f'Generated SQL: {sql}')
                    if content:
                        history_blocks.append(f'Answer Summary: {content}')
            user_content = "\n".join(history_blocks) + f'\n\nCURRENT QUESTION TO ANSWER:\n"{question}"'
        else:
            user_content = question

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": System_Prompt},
                {"role": "user", "content": user_content}
            ]
        )

        sql_query_result = response.choices[0].message.content.strip()
        return sql_query_result


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
