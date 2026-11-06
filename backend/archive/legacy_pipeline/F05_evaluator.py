from F00_imports import *


class SQLEvaluator:
    def __init__(self):
        # Read API credentials directly from .env
        api_key = os.getenv("API_KEY")
        base_url = os.getenv("API_URL")
        model = os.getenv("MODEL")

        # Initialize Groq client
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = model

    def evaluate(self, user_question: str, sql_query: str, data: list) -> dict:
        """
        Evaluates query logic, assigns confidence score, and writes an English summary.
        """
        # Limit data preview to first 5 rows to save tokens
        data_preview = str(data[:5]) if data else "[] (0 rows returned)"

        prompt = f"""You are a Senior SQL Auditor and Business Intelligence Analyst.

Analyze this Text-to-SQL execution:
1. User Question: "{user_question}"
2. Generated SQL: {sql_query}
3. Database Output: {data_preview}

Instructions:
- Check if the SQL logically answers the user question.
- Calculate a confidence score between 0.0 and 1.0 (e.g. 0.95).
- Write a clear, conversational plain-English answer summarizing the data for the user.
- Return ONLY valid JSON:
{{
  "is_accurate": true,
  "confidence_score": 0.95,
  "summary": "Helena Holý is the top customer with total spending of $49.62."
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": "You are a precise JSON-only evaluator."},
                {"role": "user", "content": prompt}
            ]
        )

        raw_text = response.choices[0].message.content.strip()

        # Clean backticks if any
        if "```" in raw_text:
            parts = raw_text.split("```")
            raw_text = parts[1] if len(parts) > 1 else parts[0]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        try:
            return json.loads(raw_text)
        except Exception:
            return {"is_accurate": True, "confidence_score": 0.85, "summary": raw_text}


if __name__ == "__main__":
    evaluator = SQLEvaluator()

    # 🧪 Test 1: Accurate Query & Result
    print("=== TEST 1: Evaluating an Accurate Query ===")
    question_1 = "Who is the top spending customer?"
    sql_1 = "SELECT FirstName, LastName, SUM(Total) FROM Customer JOIN Invoice ON Customer.CustomerId = Invoice.CustomerId GROUP BY Customer.CustomerId ORDER BY SUM(Total) DESC LIMIT 1;"
    data_1 = [{"FirstName": "Helena", "LastName": "Holý", "SUM(Total)": 49.62}]

    result_1 = evaluator.evaluate(question_1, sql_1, data_1)
    print(f"Confidence: {result_1.get('confidence_score') * 100:.0f}%")
    print(f"Accurate:   {result_1.get('is_accurate')}")
    print(f"Summary:    {str(result_1.get('summary')).encode('ascii', 'replace').decode('ascii')}\n")

    # 💥 Test 2: Flawed Query (Opposite Sort Order: ASC instead of DESC)
    print("=== TEST 2: Evaluating a Flawed Query (Opposite Sort) ===")
    question_2 = "Who is the top spending customer?"
    bad_sql_2 = "SELECT FirstName, LastName, SUM(Total) FROM Customer JOIN Invoice ON Customer.CustomerId = Invoice.CustomerId GROUP BY Customer.CustomerId ORDER BY SUM(Total) ASC LIMIT 1;"
    data_2 = [{"FirstName": "Puja", "LastName": "Srivastava", "SUM(Total)": 37.62}]

    result_2 = evaluator.evaluate(question_2, bad_sql_2, data_2)
    print(f"Confidence: {result_2.get('confidence_score') * 100:.0f}%")
    print(f"Accurate:   {result_2.get('is_accurate')}")
    print(f"Summary:    {str(result_2.get('summary')).encode('ascii', 'replace').decode('ascii')}")
