import os
import re
import json
from typing import Dict, Any, List, Optional
from openai import OpenAI
from F00_imports import *
from F13_spreadsheet_engine import SpreadsheetEngine


class SpreadsheetGenerator:
    """
    LLM Code & Formula Generator for Spreadsheets:
    - For CSV: Generates vectorized Python / Pandas code (`result_df = df[...]`).
    - For Excel: Generates modern Excel Formulas (`=FILTER(...)`, `=SUMIFS(...)`) with cell coordinates.
    """

    def __init__(self, engine: SpreadsheetEngine):
        self.engine = engine
        api_key = os.getenv("API_KEY")
        base_url = os.getenv("API_URL")
        model = os.getenv("MODEL")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = model

    def get_system_prompt(self) -> str:
        schema = self.engine.get_schema_context()

        if self.engine.file_type == "excel":
            return f"""You are an elite Microsoft Excel Specialist and Spreadsheet Architect.
Your task is to translate user questions into exact, copy-pasteable modern Excel formulas based on the spreadsheet schema and cell coordinate ranges provided below.

Spreadsheet Schema & Cell Ranges:
{schema}

Strict Rules:
1. OUTPUT FORMAT:
   - For single questions, return a strict JSON object without markdown fences:
     {{
       "title": "Concise Exact Business Objective",
       "formula": "=SUMIFS(C2:C7, A2:A7, \"Engineering\")",
       "target_cell": "C8 or New Cell",
       "explanation": "Computes total expenses incurred for Engineering using SUMIFS.",
       "eval_code": "result_df = df[df['Department'] == 'Engineering']"
     }}
   - For compound / multi-part questions (e.g. "1. Total budget for Marketing, 2. Over-budget departments"):
     Return a strict JSON array of objects:
     [
       {{
         "title": "1. Marketing Total Budget",
         "formula": "=SUMIFS(B2:B7, A2:A7, \"Marketing\")",
         "target_cell": "B8",
         "explanation": "Calculates total budget allocated to Marketing.",
         "eval_code": "result_df = df[df['Department'] == 'Marketing']"
       }},
       {{
         "title": "2. Over-Budget Departments",
         "formula": "=FILTER(A2:F7, E2:E7 < 0)",
         "target_cell": "H2",
         "explanation": "Filters all rows where RemainingBudget is negative.",
         "eval_code": "result_df = df[df['RemainingBudget'] < 0]"
       }}
     ]
2. EXCEL FORMULA RULES:
   - Always start the formula with `=`.
   - Use uppercase modern function names: `SUMIFS`, `COUNTIFS`, `AVERAGEIFS`, `FILTER`, `XLOOKUP`, `VLOOKUP`, `SORT`, `UNIQUE`, `LET`.
   - Use the exact sheet names and column letter ranges given in the schema (e.g. `A2:A7`, `Sheet1!B2:B10`).
   - If referencing another sheet in a multi-sheet workbook, prefix with sheet name: `DepartmentBudget!A2:A7`.
3. EVALUATION CODE (`eval_code`):
   - Provide a safe Pandas expression that produces `result_df` so the web UI can display a data table preview of the formula's calculation.
   - For scalar aggregates (like SUM/COUNT), wrap into a DataFrame: e.g. `result_df = pd.DataFrame([{{'Total': df[df['Department']=='Marketing']['BudgetAllocated'].sum()}}])`.
4. Do NOT output any markdown backticks, conversational preamble, or explanations outside the JSON.
"""
        else:
            # CSV / Pandas mode
            return f"""You are a Senior Python Data Analyst and Pandas Expert.
Your job is to translate user questions into clean, high-performance, vectorized Pandas code that operates on the provided DataFrame.

DataFrame Schema & Samples:
{schema}

Strict Rules:
1. OUTPUT FORMAT:
   - For single questions, return a strict JSON object without markdown fences:
     {{
       "title": "Concise Exact Business Objective",
       "code": "result_df = df[df['TotalAmount'] > 500].groupby('Region')['TotalAmount'].sum().reset_index()",
       "explanation": "Calculates sum of TotalAmount by Region for orders above 500."
     }}
   - For compound / multi-part questions (e.g. "1. Top 5 orders, 2. Total revenue by category"):
     Return a strict JSON array of objects:
     [
       {{
         "title": "1. Top 5 Orders",
         "code": "result_df = df.sort_values('TotalAmount', ascending=False).head(5)",
         "explanation": "Sorts orders descending by TotalAmount and takes top 5."
       }},
       {{
         "title": "2. Total Revenue by Category",
         "code": "result_df = df.groupby('ProductCategory')['TotalAmount'].sum().reset_index()",
         "explanation": "Groups by ProductCategory and sums TotalAmount."
       }}
     ]
2. PANDAS CODE CONSTRAINTS:
   - Always assign the final output to `result_df` (must be a pandas `DataFrame`).
   - Do NOT use `import` statements (pandas is pre-loaded as `pd`, numpy as `np`, active DataFrame as `df`).
   - Do NOT access file systems, network, or OS functions.
   - Use vectorized methods: `.groupby()`, `.agg()`, `.sort_values()`, `.head()`, `.loc[]`, `.query()`.
   - Reset index when grouping: `.reset_index()`.
3. Do NOT output markdown backticks (```python or ```) or conversational commentary outside the JSON.
"""

    def generate(self, question: str, conversation_context: Optional[str] = None) -> List[Dict[str, Any]]:
        """Calls the LLM to generate Pandas code or Excel formulas."""
        system_prompt = self.get_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]

        if conversation_context:
            messages.append({
                "role": "system",
                "content": f"PREVIOUS CONVERSATION CONTEXT:\n{conversation_context}"
            })

        messages.append({"role": "user", "content": question})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.0
        )

        raw_content = response.choices[0].message.content.strip()
        return self.parse_response(raw_content)

    def parse_response(self, raw_text: str) -> List[Dict[str, Any]]:
        """Parses JSON response into a standardized list of sub-queries."""
        text = raw_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        text = text.strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            pass

        # Fallback extraction if JSON parsing failed
        if self.engine.file_type == "excel":
            # Extract formula starting with =
            formula_match = re.search(r"(=[A-Z0-9_]+\([^)]*\))", text)
            formula = formula_match.group(1) if formula_match else text
            return [{
                "title": "Excel Formula",
                "formula": formula,
                "explanation": "Generated formula",
                "eval_code": "result_df = df.head(10)"
            }]
        else:
            return [{
                "title": "Pandas Data Extraction",
                "code": text,
                "explanation": "Generated Pandas code"
            }]
