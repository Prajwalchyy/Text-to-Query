"""
Master Catalog of Prompt Templates and Dialect Builders.

Centralizes all system prompts, few-shot rules, schema injection templates,
conversation memory formatting, and self-repair templates across SQL, NoSQL (MQL),
and Spreadsheets (Pandas & Excel formulas).

Pure functional implementation with zero side effects or OOP state.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union


# ==============================================================================
# 1. System Prompt Templates
# ==============================================================================

SQL_SYSTEM_PROMPT_TEMPLATE = """You are an expert SQL Database Engineer.
Your job is to translate user questions into valid SQLite SQL queries based on the database schema provided below.

Database Schema:
{schema_context}

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


NOSQL_SYSTEM_PROMPT_TEMPLATE = """You are an Expert MongoDB and NoSQL Database Engineer.
Your task is to translate natural language user questions into high-performance, valid MongoDB MQL queries.

AVAILABLE COLLECTIONS IN THIS DATABASE:
[{available_collections}]

DATABASE SCHEMAS & SAMPLE DOCUMENTS:
{schema_context}

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


SPREADSHEET_CSV_SYSTEM_PROMPT_TEMPLATE = """You are a Senior Python Data Analyst and Pandas Expert.
Your job is to translate user questions into clean, high-performance, vectorized Pandas code that operates on the provided DataFrame.

DataFrame Schema & Samples:
{schema_context}

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
4. SCHEMA RELEVANCY & OUT-OF-DOMAIN QUESTIONS:
   - If the user asks about data completely absent from this dataset:
     Output a strict JSON object:
     {{
       "is_relevant": false,
       "reason": "Explanation of missing columns/concepts.",
       "needed_tables": ["ColumnA", "ColumnB"],
       "suggested_questions": ["Question 1", "Question 2", "Question 3"]
     }}
"""


SPREADSHEET_EXCEL_SYSTEM_PROMPT_TEMPLATE = """You are an elite Microsoft Excel Specialist and Spreadsheet Architect.
Your task is to translate user questions into exact, copy-pasteable modern Excel formulas based on the spreadsheet schema and cell coordinate ranges provided below.

Spreadsheet Schema & Cell Ranges:
{schema_context}

Strict Rules:
1. OUTPUT FORMAT:
   - For single questions, return a strict JSON object without markdown fences:
     {{
       "title": "Concise Exact Business Objective",
       "formula": "=SUMIFS(C2:C7, A2:A7, \\"Engineering\\")",
       "target_cell": "C8 or New Cell",
       "explanation": "Computes total expenses incurred for Engineering using SUMIFS.",
       "eval_code": "result_df = df[df['Department'] == 'Engineering']"
     }}
   - For compound / multi-part questions (e.g. "1. Total budget for Marketing, 2. Over-budget departments"):
     Return a strict JSON array of objects:
     [
       {{
         "title": "1. Marketing Total Budget",
         "formula": "=SUMIFS(B2:B7, A2:A7, \\"Marketing\\")",
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
5. SCHEMA RELEVANCY & OUT-OF-DOMAIN QUESTIONS:
   - If the user asks about data completely absent from this workbook:
     Output a strict JSON object:
     {{
       "is_relevant": false,
       "reason": "Explanation of missing sheets/columns.",
       "needed_tables": ["Sheet1", "ColumnA"],
       "suggested_questions": ["Question 1", "Question 2", "Question 3"]
     }}
"""


REPAIR_SYSTEM_PROMPTS = {
    "sql": "You are an expert SQL Database Engineer fixing a failed SQLite query.",
    "sqlite": "You are an expert SQL Database Engineer fixing a failed SQLite query.",
    "nosql": "You are an expert MongoDB and NoSQL Database Engineer fixing a failed MongoDB MQL query.",
    "mql": "You are an expert MongoDB and NoSQL Database Engineer fixing a failed MongoDB MQL query.",
    "mongodb": "You are an expert MongoDB and NoSQL Database Engineer fixing a failed MongoDB MQL query.",
    "pandas": "You are an expert Data Engineer fixing failed Python Pandas data analysis code.",
    "csv": "You are an expert Data Engineer fixing failed Python Pandas data analysis code.",
    "excel": "You are an expert Microsoft Excel and Spreadsheet Architect fixing a failed Excel formula or preview script.",
}


# ==============================================================================
# 2. Conversational History Formatter
# ==============================================================================

def format_history_context(
    history: Optional[Union[List[Dict[str, Any]], str]] = None,
    query_label: str = "Query"
) -> str:
    """
    Formats multi-turn conversational history into a structured block
    for coreference and pronoun resolution.

    Args:
        history: Either a pre-formatted string or a list of message dicts:
                 [{"role": "user"|"assistant", "content": "...", "sql": "...", ...}]
        query_label: Label to display for generated queries ("SQL", "MQL Query", "Pandas Code").

    Returns:
        Formatted context string, or empty string if no history is provided.
    """
    if not history:
        return ""

    if isinstance(history, str):
        trimmed = history.strip()
        if not trimmed:
            return ""
        if "PREVIOUS CONVERSATION CONTEXT" in trimmed:
            return trimmed
        return f"PREVIOUS CONVERSATION CONTEXT (for pronoun & reference resolution):\n{trimmed}"

    if not isinstance(history, list) or len(history) == 0:
        return ""

    lines = ["PREVIOUS CONVERSATION CONTEXT (for pronoun & reference resolution):"]
    has_entries = False

    for msg in history:
        if not isinstance(msg, dict):
            continue

        role = (msg.get("role") or "").lower()
        content = (msg.get("content") or "").strip()
        summary_val = (
            msg.get("content")
            or msg.get("summary")
            or msg.get("explanation")
            or ""
        ).strip()

        # Check for various query keys: sql, mql, code, formula, query
        query_val = (
            msg.get("sql")
            or msg.get("mql")
            or msg.get("code")
            or msg.get("formula")
            or msg.get("query")
        )

        if role == "user" and content:
            lines.append(f'User asked: "{content}"')
            has_entries = True
        elif role in ["assistant", "model", "system"]:
            if query_val:
                lines.append(f"Generated {query_label}: {str(query_val).strip()}")
                has_entries = True
            if summary_val:
                lines.append(f"Answer Summary: {summary_val}")
                has_entries = True

    if not has_entries:
        return ""

    return "\n".join(lines)


# ==============================================================================
# 3. Prompt Builder Functions
# ==============================================================================

def build_sql_prompt(
    question: str,
    schema_str: str,
    history: Optional[Union[List[Dict[str, Any]], str]] = None
) -> Tuple[str, str]:
    """
    Constructs the (system_prompt, user_content) pair for SQLite Text-to-SQL generation.

    Args:
        question: User's natural language inquiry.
        schema_str: Introspected database schema context (tables, columns, types, FKs).
        history: Optional multi-turn conversation history for pronoun resolution.

    Returns:
        Tuple of (system_prompt, user_content).
    """
    system_prompt = SQL_SYSTEM_PROMPT_TEMPLATE.format(schema_context=schema_str.strip())
    hist_block = format_history_context(history, query_label="SQL")

    if hist_block:
        user_content = f"{hist_block}\n\nCURRENT QUESTION TO ANSWER:\n\"{question.strip()}\""
    else:
        user_content = question.strip()

    return system_prompt, user_content


def build_nosql_prompt(
    question: str,
    schema_str: str,
    history: Optional[Union[List[Dict[str, Any]], str]] = None,
    collection_names: Optional[List[str]] = None
) -> Tuple[str, str]:
    """
    Constructs the (system_prompt, user_content) pair for MongoDB MQL generation.

    Args:
        question: User's natural language inquiry.
        schema_str: Introspected collection schemas and sample documents.
        history: Optional multi-turn conversation history for pronoun resolution.
        collection_names: Optional list of available collections.

    Returns:
        Tuple of (system_prompt, user_content).
    """
    cols_str = ", ".join(collection_names) if collection_names else "all collections in schema"
    system_prompt = NOSQL_SYSTEM_PROMPT_TEMPLATE.format(
        available_collections=cols_str,
        schema_context=schema_str.strip()
    )
    hist_block = format_history_context(history, query_label="MQL Query")

    if hist_block:
        user_content = f"{hist_block}\n\nCURRENT QUESTION TO ANSWER:\n\"{question.strip()}\""
    else:
        user_content = question.strip()

    return system_prompt, user_content


def build_spreadsheet_prompt(
    question: str,
    schema_str: str,
    file_type: str = "csv",
    history: Optional[Union[List[Dict[str, Any]], str]] = None
) -> Tuple[str, str]:
    """
    Constructs the (system_prompt, user_content) pair for Spreadsheet querying.
    Selects between vectorized Pandas (for CSV) and modern Excel formulas (for Excel).

    Args:
        question: User's natural language inquiry.
        schema_str: Introspected sheet schema, columns, and coordinate samples.
        file_type: "csv" or "excel".
        history: Optional multi-turn conversation history.

    Returns:
        Tuple of (system_prompt, user_content).
    """
    ft = (file_type or "csv").lower().strip()
    if ft in ["excel", "xlsx", "xls"]:
        system_prompt = SPREADSHEET_EXCEL_SYSTEM_PROMPT_TEMPLATE.format(schema_context=schema_str.strip())
        hist_block = format_history_context(history, query_label="Excel Formula")
    else:
        system_prompt = SPREADSHEET_CSV_SYSTEM_PROMPT_TEMPLATE.format(schema_context=schema_str.strip())
        hist_block = format_history_context(history, query_label="Pandas Code")

    if hist_block:
        user_content = f"{hist_block}\n\nCURRENT QUESTION TO ANSWER:\n\"{question.strip()}\""
    else:
        user_content = question.strip()

    return system_prompt, user_content


def build_repair_prompt(
    question: str,
    broken_query: str,
    error: str,
    schema_str: str,
    dialect: str = "sql",
    db_type: Optional[str] = None,
    **kwargs: Any
) -> Tuple[str, str]:
    """
    Constructs the (system_prompt, user_content) pair for auto-repairing a failed query or code snippet.

    Args:
        question: Original natural language user question.
        broken_query: The failed query, formula, or Python code.
        error: Runtime database, parser, or guardrail error message.
        schema_str: Introspected schema context.
        dialect: Target dialect ("sql", "nosql", "pandas", "excel").
        db_type: Optional alias for dialect.

    Returns:
        Tuple of (system_prompt, user_content).
    """
    raw_dial = db_type or dialect or "sql"
    dial = raw_dial.lower().strip()
    system_prompt = REPAIR_SYSTEM_PROMPTS.get(dial, REPAIR_SYSTEM_PROMPTS["sql"])

    # Dialect-specific instruction blocks
    if dial in ["nosql", "mql", "mongodb"]:
        instructions = (
            "1. Inspect the error and schema above to correct collection names, field paths, and operators.\n"
            "2. Ensure field names match the schema and aggregation pipelines have proper leading '$'.\n"
            "3. Return ONLY the valid JSON or MQL expression without markdown commentary."
        )
        code_label = "Failed MQL Query / Pipeline"
    elif dial in ["pandas", "csv"]:
        instructions = (
            "1. Fix the Pandas code to resolve the error. Ensure it assigns the final result DataFrame to `result_df`.\n"
            "2. Do NOT use forbidden imports, file I/O, or infinite loops.\n"
            "3. Return ONLY the executable Python code or a JSON object with 'code'."
        )
        code_label = "Failed Pandas Code"
    elif dial in ["excel", "xlsx", "xls"]:
        instructions = (
            "1. Fix the Excel formula to resolve the error. Ensure it starts with '=' and uses valid cell ranges.\n"
            "2. Provide an updated 'eval_code' Pandas snippet that assigns to `result_df`.\n"
            "3. Return a JSON object with 'formula', 'target_cell', 'explanation', and 'eval_code'."
        )
        code_label = "Failed Excel Formula / Eval Code"
    else:
        # Default SQLite
        instructions = (
            "1. Inspect the database error and the schema above to identify and fix the mistake.\n"
            "2. Use valid SQLite syntax and proper JOIN / UNION ALL formatting.\n"
            "3. Return ONLY the single corrected SQLite SQL query or strict JSON with 'title' and 'sql'."
        )
        code_label = "Failed SQL Query"

    user_content = f"""User Question: {question.strip()}
{code_label}:
{broken_query.strip()}

Execution Error:
{error.strip()}

Database / Dataset Schema:
{schema_str.strip()}

Instructions:
{instructions}"""

    return system_prompt, user_content


# ==============================================================================
# 4. Generator Output Parser
# ==============================================================================

def parse_generator_output(
    raw_output: str,
    default_title: str = "Query Objective",
    db_type: Optional[str] = None,
    **kwargs: Any
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Parses LLM generator output across all database engines into a structured list
    of tasks or an out-of-domain rejection payload.

    Handles:
      - Out-of-domain JSON: {"is_relevant": false, ...}
      - Single JSON query: {"title": "...", "sql": "..."} or {"code": "..."} or {"mql": "..."} or {"formula": "..."}
      - Compound JSON array: [{"title": "...", "sql": "..."}, ...]
      - Raw SQL / MQL / code fallback string: [{"title": default_title, "sql": "..."}]

    Returns:
        Either a list of task dicts or an out-of-domain rejection dict.
    """
    if not raw_output:
        return [{"title": default_title, "sql": ""}]

    cleaned = raw_output.strip()

    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:[a-zA-Z0-9_\-]+)?\s*\n?(.*?)\s*```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    else:
        cleaned = re.sub(r"^```(?:[a-zA-Z0-9_\-]+)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    # 1. Check if output is a JSON object
    if cleaned.startswith("{") and cleaned.endswith("}"):
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                # Check for Out-of-Domain rejection
                if parsed.get("is_relevant") is False:
                    return parsed

                # Normalize keys into task dict
                title = parsed.get("title") or default_title
                task_dict = {"title": title}
                for key in ["sql", "mql", "code", "formula", "eval_code", "explanation", "target_cell"]:
                    if key in parsed:
                        task_dict[key] = parsed[key]

                # Ensure at least one query/code field exists
                if any(k in task_dict for k in ["sql", "mql", "code", "formula"]):
                    return [task_dict]
        except Exception:
            pass

    # 2. Check if output is a JSON array (compound multi-part questions)
    if cleaned.startswith("[") and cleaned.endswith("]"):
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list) and len(parsed) > 0:
                tasks = []
                for i, item in enumerate(parsed):
                    if isinstance(item, dict):
                        t_title = item.get("title") or f"Query {i + 1}"
                        t_dict = {"title": t_title}
                        for key in ["sql", "mql", "code", "formula", "eval_code", "explanation", "target_cell"]:
                            if key in item:
                                t_dict[key] = item[key]
                        if any(k in t_dict for k in ["sql", "mql", "code", "formula"]):
                            tasks.append(t_dict)
                if tasks:
                    return tasks
        except Exception:
            pass

    # 3. Fallback: Wrap raw code/query as a single task
    # Detect dialect hint for key
    lower_cl = cleaned.lower()
    if lower_cl.startswith("db."):
        return [{"title": default_title, "mql": cleaned}]
    elif lower_cl.startswith("result_df") or "df[" in cleaned:
        return [{"title": default_title, "code": cleaned}]
    elif cleaned.startswith("="):
        return [{"title": default_title, "formula": cleaned}]
    else:
        return [{"title": default_title, "sql": cleaned}]
