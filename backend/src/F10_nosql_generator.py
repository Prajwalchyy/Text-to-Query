from F00_imports import *
from typing import Dict, Any, List, Optional
import json
import re


class NoSQLGenerator:
    """
    Translates Natural Language questions into MongoDB MQL Queries across multiple collections
    (orders, customers, products, reviews, etc.) based on introspected JSON document schemas.
    """

    def __init__(self):
        api_key = os.getenv("API_KEY")
        base_url = os.getenv("API_URL")
        model = os.getenv("MODEL")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = model

    def generate_mql(
        self,
        question: str,
        schemas_context: str,
        collection_names: List[str],
        feedback: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Synthesizes a MongoDB MQL query using the configured LLM with optional multi-turn memory.
        """
        available_cols = ", ".join(collection_names)

        system_prompt = f"""You are an Expert MongoDB and NoSQL Database Engineer.
Your task is to translate natural language user questions into high-performance, valid MongoDB MQL queries.

AVAILABLE COLLECTIONS IN THIS DATABASE:
[{available_cols}]

DATABASE SCHEMAS & SAMPLE DOCUMENTS:
{schemas_context}

RULES & CONSTRAINTS:
1. OUTPUT FORMAT:
   - For standard single-question requests: Output a strict JSON object without markdown fences containing a concise title and the raw MQL query:
     {{
       "title": "Top Products Ranked by Sales Volume",
       "mql": "db.products.find({{ ... }})"
     }}
   - For compound or multi-part questions requiring separate reports: Output a strict JSON array of objects without markdown fences:
     [
       {{"title": "1. All Customers", "mql": "db.customers.find({{ ... }})"}},
       {{"title": "2. Total Orders by Category", "mql": "db.orders.aggregate([ ... ])"}}
     ]
   - (If raw JavaScript query starting with db.<collection> is generated without JSON, it will be handled as fallback).
2. Use valid dot-notation for nested fields (e.g. "address.city", "items.category").
3. For array filtering or matching items, use standard MongoDB operators ($elemMatch, $in, $eq, $gt, etc.).
4. For aggregations ($group, $sum, $avg, $min, $max), ensure field references have a leading '$' (e.g. "$total_amount").
5. Do NOT include Markdown formatting like ```javascript or ```json, return ONLY the raw JSON or raw JavaScript query starting with db.<collection>.
6. NEVER generate destructive mutations ($drop, $deleteMany, $deleteOne, $updateMany, $out). Strictly Read-Only queries.
7. MULTI-TURN CONVERSATION & PRONOUN RESOLUTION:
   - When a "PREVIOUS CONVERSATION CONTEXT" block is provided, use it to understand what the user is referring to.
   - If the current question uses coreferences or pronouns (e.g. "their", "them", "those", "that product", "the first one"), resolve them from previous queries.
   - If the user asks to refine or modify the previous query (e.g. "now sort by price", "filter for only Platinum tier"), adapt the previous MQL pipeline/filter.
   - If the user asks an unrelated new question, ignore previous context and generate a clean standalone query.
8. SCHEMA RELEVANCY & OUT-OF-DOMAIN QUESTIONS:
   - Carefully verify if the requested entities or collections physically exist in this database.
   - If the user question references concepts or collections completely absent from this database (e.g. asking for music tracks, albums, hospital records on an e-commerce database, or general chit-chat):
     DO NOT force an unrelated query.
     DO NOT substitute collections.
     Instead, output a strict JSON object without markdown fences:
     {{
       "is_relevant": false,
       "reason": "Clear explanation of what was requested and why this database cannot answer it.",
       "needed_tables": ["Tracks", "Albums"],
       "suggested_questions": [
         "Relevant question 1 that CAN be answered by this database",
         "Relevant question 2 that CAN be answered by this database",
         "Relevant question 3 that CAN be answered by this database"
       ]
     }}
"""

        # Build context block from prior conversation turns if provided
        history_block = ""
        if conversation_history and len(conversation_history) > 0:
            lines = ["PREVIOUS CONVERSATION CONTEXT (for pronoun & reference resolution):"]
            for msg in conversation_history:
                role = "User" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "").strip()
                sql = msg.get("sql")
                if role == "User" and content:
                    lines.append(f'User asked: "{content}"')
                elif role == "Assistant":
                    if sql:
                        lines.append(f'Generated MQL Query: {sql}')
                    if content:
                        lines.append(f'Answer Summary: {content}')
            history_block = "\n".join(lines) + "\n\n"

        user_content = f"{history_block}CURRENT QUESTION TO ANSWER:\n\"{question}\""
        if feedback:
            user_content += f"\n\nCRITICAL FIX INSTRUCTION (Previous attempt failed):\n{feedback}\nPlease fix the query syntax and field references."

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.1
            )
            raw_text = response.choices[0].message.content.strip()
            # Clean markdown fences if present
            cleaned = re.sub(r"^```(?:javascript|json|mongodb)?\s*", "", raw_text, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            return cleaned.strip()

        except Exception as e:
            raise RuntimeError(f"NoSQL Generation failed: {str(e)}")

    @staticmethod
    def parse_queries(raw_output: str) -> Union[List[Dict[str, str]], Dict[str, Any]]:
        """
        Parses generator output into a structured list of MQL tasks:
        [{"title": "...", "mql": "..."}], or an out-of-domain rejection dict.
        Handles single raw db.<collection> queries, JSON arrays for compound prompts,
        and JSON objects for out-of-domain schema mismatch rejections.
        """
        cleaned = raw_output.strip()
        # Remove markdown code fences if present
        if "```" in cleaned:
            parts = cleaned.split("```")
            cleaned = parts[1] if len(parts) > 1 else parts[0]
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
            elif cleaned.lower().startswith("javascript") or cleaned.lower().startswith("mongodb"):
                cleaned = re.sub(r"^(?:javascript|mongodb)\s*", "", cleaned, flags=re.IGNORECASE).strip()

        # 1. Check if output is a JSON object
        if cleaned.startswith("{") and cleaned.endswith("}"):
            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    if parsed.get("is_relevant") is False:
                        return parsed
                    elif "mql" in parsed or "query" in parsed or "sql" in parsed:
                        mql_str = (parsed.get("mql") or parsed.get("query") or parsed.get("sql") or "").strip()
                        title_str = parsed.get("title") or "Query Objective"
                        if mql_str:
                            return [{"title": title_str, "mql": mql_str}]
            except Exception:
                pass

        # 2. Check if output is a JSON array
        if cleaned.startswith("[") and cleaned.endswith("]"):
            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
                    result = []
                    for i, item in enumerate(parsed):
                        mql_str = item.get("mql") or item.get("sql") or item.get("query")
                        if mql_str:
                            result.append({
                                "title": item.get("title", f"Query {i + 1}"),
                                "mql": mql_str.strip()
                            })
                    if len(result) > 0:
                        return result
            except Exception:
                pass

        # 3. Fallback to single MQL query
        return [{"title": "Query Objective", "mql": cleaned}]

