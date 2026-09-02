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
        feedback: Optional[str] = None
    ) -> str:
        """
        Synthesizes a MongoDB MQL query using the configured LLM.
        """
        available_cols = ", ".join(collection_names)

        system_prompt = f"""You are an Expert MongoDB and NoSQL Database Engineer.
Your task is to translate natural language user questions into high-performance, valid MongoDB MQL queries.

AVAILABLE COLLECTIONS IN THIS DATABASE:
[{available_cols}]

DATABASE SCHEMAS & SAMPLE DOCUMENTS:
{schemas_context}

RULES & CONSTRAINTS:
1. Always output either a MongoDB aggregation pipeline:
   db.<collection_name>.aggregate([ ... ])
   OR a standard find filter:
   db.<collection_name>.find({{ ... }})
   (Replace <collection_name> with the correct collection such as 'orders', 'customers', 'products', etc.)
2. Use valid dot-notation for nested fields (e.g. "address.city", "items.category").
3. For array filtering or matching items, use standard MongoDB operators ($elemMatch, $in, $eq, $gt, etc.).
4. For aggregations ($group, $sum, $avg, $min, $max), ensure field references have a leading '$' (e.g. "$total_amount").
5. Do NOT include Markdown formatting like ```javascript or ```json, return ONLY the raw JavaScript query starting with db.<collection>.
6. NEVER generate destructive mutations ($drop, $deleteMany, $deleteOne, $updateMany, $out). Strictly Read-Only queries.
"""

        user_content = f"User Question: {question}"
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
