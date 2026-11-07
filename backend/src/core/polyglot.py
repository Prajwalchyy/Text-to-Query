"""
Polyglot Multi-Language Code Generator & Cross-Dialect Converter (Stateless Pure Functional).

Translates natural language questions or existing database queries into 5 production-ready
dialects with language badges, colors, and execution targets:
  - SQL (SQLite / ANSI)
  - Python (Pandas / Native / PyMongo)
  - R (tidyverse / DBI)
  - MongoDB MQL (NoSQL)
  - Excel Formulas (Spreadsheets)

Zero OOP required; pure functional interfaces with a thin backward-compatible adapter.
Replaces legacy backend/src/F17_multi_language_generator.py.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure backend root is discoverable for internal imports
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from src.core.llm import call_llm, call_llm_json
except ImportError:
    try:
        from core.llm import call_llm, call_llm_json
    except ImportError:
        call_llm = None
        call_llm_json = None


# Supported languages metadata catalog
LANGUAGE_CONFIG: Dict[str, Dict[str, Any]] = {
    "sql": {
        "id": "sql",
        "name": "SQL",
        "badge": "SQL",
        "color": "indigo",
        "supported_db_types": ["sql"],
    },
    "excel_formula": {
        "id": "excel_formula",
        "name": "Excel",
        "badge": "Excel",
        "color": "emerald",
        "supported_db_types": ["excel", "csv"],
    },
    "pandas": {
        "id": "pandas",
        "name": "Python (Pandas)",
        "badge": "Python (Pandas)",
        "color": "cyan",
        "supported_db_types": ["sql", "csv", "excel", "nosql"],
    },
    "r": {
        "id": "r",
        "name": "R",
        "badge": "R",
        "color": "sky",
        "supported_db_types": ["sql", "nosql", "csv", "excel"],
    },
    "nosql": {
        "id": "nosql",
        "name": "MongoDB MQL",
        "badge": "MongoDB MQL",
        "color": "emerald",
        "supported_db_types": ["nosql"],
    },
}


def normalize_db_type(db_type: str) -> str:
    """Normalizes database engine alias to standard type ('sql', 'nosql', 'csv', 'excel')."""
    clean_type = (db_type or "sql").lower().strip()
    if clean_type in ["sqlite", "relational", "database"]:
        return "sql"
    if clean_type in ["mongodb", "json", "jsonl", "bson"]:
        return "nosql"
    return clean_type


def get_supported_languages(db_type: str) -> List[Dict[str, Any]]:
    """Returns the list of allowed language configurations for a specific database engine type."""
    norm_type = normalize_db_type(db_type)
    return [cfg for cfg in LANGUAGE_CONFIG.values() if norm_type in cfg["supported_db_types"]]


def is_language_supported(db_type: str, language: str) -> bool:
    """Validates if a target language is compatible with the given database type."""
    norm_type = normalize_db_type(db_type)
    cfg = LANGUAGE_CONFIG.get((language or "").lower().strip())
    if not cfg:
        return False
    return norm_type in cfg["supported_db_types"]


def build_polyglot_prompt(
    db_type: str,
    target_lang: str,
    schema_context: str,
    db_name: str = "Database",
    table_names: Optional[List[str]] = None,
) -> str:
    """Constructs the specialized system prompt for the chosen target dialect."""
    norm_type = normalize_db_type(db_type)
    lang = target_lang.lower().strip()

    # 1. PYTHON / PANDAS
    if lang == "pandas":
        if norm_type == "sql":
            return f"""You are a Senior Python Data Engineer.
Translate user questions into idiomatic Python code using Pandas and SQLAlchemy or sqlite3 to query the database.

Database Schema:
{schema_context}

Strict Rules:
1. Return a strict JSON object without markdown fences:
{{
  "title": "Concise Exact Goal",
  "code": "import sqlite3\\nimport pandas as pd\\n\\nconn = sqlite3.connect('{db_name}.db')\\nquery = '''SELECT ...'''\\ndf = pd.read_sql_query(query, conn)\\nconn.close()\\nprint(df)",
  "eval_sql": "SELECT ...",
  "explanation": "Brief explanation of how the query and DataFrame processing works."
}}
2. `eval_sql` MUST be the pure, valid SQLite SQL query equivalent that can be executed directly to fetch the exact same data.
3. Use proper column names and table joins.
"""
        elif norm_type in ["csv", "excel"]:
            return f"""You are an expert Python Data Analyst.
Translate user questions into vectorized Python / Pandas code operating on the existing DataFrame `df`.

Spreadsheet Schema:
{schema_context}

Strict Rules:
1. Return a strict JSON object without markdown fences:
{{
  "title": "Concise Exact Goal",
  "code": "result_df = df[df['Column'] > 100].groupby('Category')['Revenue'].sum().reset_index()",
  "eval_pandas": "result_df = df[df['Column'] > 100].groupby('Category')['Revenue'].sum().reset_index()",
  "explanation": "Brief 1-sentence explanation."
}}
2. Output vectorized pandas operations assigning the final result to `result_df`.
"""
        else:  # nosql
            return f"""You are a Python NoSQL Engineer.
Translate user questions into idiomatic Python code using PyMongo or dict filtering.

NoSQL Schema:
{schema_context}

Strict Rules:
Return a strict JSON object without markdown fences:
{{
  "title": "Concise Exact Goal",
  "code": "from pymongo import MongoClient\\n\\nclient = MongoClient('mongodb://localhost:27017/')\\ndb = client['{db_name}']\\nresults = list(db['collection'].find(...))\\nfor doc in results:\\n    print(doc)",
  "eval_mql": "{{\\"collection\\": \\"collection_name\\", \\"query\\": {{...}}}}",
  "explanation": "Brief explanation."
}}
"""

    # 2. SQL ON SPREADSHEETS
    if lang == "sql" and norm_type in ["csv", "excel"]:
        tables_str = ", ".join(table_names) if table_names else "sheet1"
        return f"""You are an expert SQL Database Engineer querying a Spreadsheet (CSV/Excel) treated as a Relational SQL Table.
Available Table(s): {tables_str}

Spreadsheet Table Schema:
{schema_context}

Strict Rules:
1. Return a strict JSON object without markdown fences:
{{
  "title": "Concise Exact Goal",
  "code": "SELECT Column1, SUM(Column2) FROM {table_names[0] if table_names else 'table'} GROUP BY Column1;",
  "eval_sql": "SELECT Column1, SUM(Column2) FROM {table_names[0] if table_names else 'table'} GROUP BY Column1;",
  "explanation": "Executes standard ANSI SQL query directly over the spreadsheet table."
}}
2. Do NOT wrap in markdown fences.
3. Only use table names and columns defined in the schema above.
"""

    # 3. R
    if lang == "r":
        return f"""You are an expert R Data Scientist and Statistician.
Translate the user question into idiomatic R code using `tidyverse` (`dplyr`) or `DBI`/`RSQLite`.

Schema:
{schema_context}

Strict Rules:
1. Return a strict JSON object without markdown fences:
{{
  "title": "Concise Exact Goal",
  "code": "# R code using tidyverse piping (%>%) or DBI queries\\nlibrary(dplyr)\\n...",
  "eval_sql": "Equivalent SQL query if relational/csv/excel",
  "eval_mql": "Equivalent MQL query if nosql",
  "explanation": "Brief explanation of the R data manipulation."
}}
2. Use idiomatic R piping and clean functional style.
"""

    # 4. EXCEL FORMULA
    if lang in ["excel_formula", "excel"]:
        return f"""You are an expert Excel Formula and Spreadsheet Architect.
Translate the user question into an idiomatic Excel calculation formula (e.g. SUMIFS, COUNTIF, VLOOKUP, XLOOKUP, AVERAGEIFS, INDEX/MATCH).

Schema:
{schema_context}

Strict Rules:
1. Return a strict JSON object without markdown fences:
{{
  "title": "Concise Exact Goal",
  "code": "=SUMIFS(D:D, A:A, \\">100\\")",
  "eval_sql": "SELECT ... equivalent SQL query if relational/csv/excel",
  "eval_mql": "Equivalent MQL query if nosql",
  "explanation": "Brief explanation of how the Excel formula calculates the result."
}}
2. `code` must be a valid, capitalized Excel formula starting with `=`.
3. Provide `eval_sql` (if relational/csv/excel) or `eval_mql` (if nosql) so the system can display a live data preview.
"""

    # Default fallback
    return f"""You are an expert Software Engineer.
Translate the user question into valid {lang.upper()} code for the following schema:
{schema_context}

Return a strict JSON object without markdown fences:
{{
  "title": "Query Title",
  "code": "Code snippet in {lang}",
  "explanation": "Brief explanation."
}}
"""


def generate_polyglot_code(
    question: str,
    schema_context: str,
    db_type: str,
    target_language: str,
    db_name: str = "Database",
    table_or_sheet_names: Optional[List[str]] = None,
    model_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generates idiomatic code in the specified target language based on the database schema.
    Also includes execution query (`eval_sql`, `eval_mql`, or `eval_pandas`) for backend data execution.
    """
    norm_type = normalize_db_type(db_type)
    target_lang = (target_language or "sql").lower().strip()

    if not is_language_supported(norm_type, target_lang):
        allowed_names = [cfg["name"] for cfg in get_supported_languages(norm_type)]
        raise ValueError(
            f"Language '{target_language}' is not supported for '{db_type}' datasets. "
            f"Allowed languages: {allowed_names}"
        )

    system_prompt = build_polyglot_prompt(
        db_type=norm_type,
        target_lang=target_lang,
        schema_context=schema_context,
        db_name=db_name,
        table_names=table_or_sheet_names,
    )

    if call_llm_json is not None:
        try:
            parsed = call_llm_json(
                prompt=question,
                system_prompt=system_prompt,
                model_override=model_override,
            )
            if isinstance(parsed, dict):
                parsed["code_type"] = target_lang
                return parsed
        except Exception:
            pass

    return {
        "title": f"{target_lang.upper()} Query",
        "code": f"// Generated {target_lang} code for: {question}",
        "explanation": f"Generated {target_lang.upper()} query code based on schema.",
        "code_type": target_lang,
    }


def convert_code(
    code: str,
    from_language: str,
    to_language: str,
    schema_context: str,
    db_type: str,
    model_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Translates an existing query or code snippet from one dialect into another.
    """
    norm_type = normalize_db_type(db_type)
    to_lang = (to_language or "").lower().strip()

    if not is_language_supported(norm_type, to_lang):
        raise ValueError(
            f"Target language '{to_language}' is not supported for '{db_type}' datasets."
        )

    prompt = f"""You are an elite polyglot database engineer.
Convert the following {from_language.upper()} code into idiomatic {to_language.upper()} for a {norm_type.upper()} dataset.

Schema Context:
{schema_context}

Original Code ({from_language}):
{code}

Strict Output Format:
Return a JSON object without markdown fences:
{{
  "title": "Converted query description",
  "code": "The converted code in {to_language}",
  "explanation": "Brief 1-sentence explanation of the conversion"
}}
"""
    system_prompt = "You are a polyglot database code converter. Output valid JSON only."

    if call_llm_json is not None:
        try:
            parsed = call_llm_json(
                prompt=f"Convert this {from_language} code to {to_language}.",
                system_prompt=prompt,
                model_override=model_override,
            )
            if isinstance(parsed, dict):
                parsed["code_type"] = to_lang
                return parsed
        except Exception:
            pass

    return {
        "title": f"Converted to {to_lang.upper()}",
        "code": code,
        "explanation": f"Converted code snippet to {to_lang}.",
        "code_type": to_lang,
    }


class MultiLanguageGenerator:
    """
    Backward-compatible adapter matching legacy F17_multi_language_generator.py.
    Delegates all operations to pure functional interfaces.
    """

    @staticmethod
    def get_supported_languages(db_type: str) -> List[Dict[str, Any]]:
        return get_supported_languages(db_type)

    @staticmethod
    def is_language_supported(db_type: str, language: str) -> bool:
        return is_language_supported(db_type, language)

    def generate_code(
        self,
        question: str,
        schema_context: str,
        db_type: str,
        target_language: str,
        db_name: str = "Database",
        table_or_sheet_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return generate_polyglot_code(
            question=question,
            schema_context=schema_context,
            db_type=db_type,
            target_language=target_language,
            db_name=db_name,
            table_or_sheet_names=table_or_sheet_names,
        )

    def convert_code(
        self,
        code: str,
        from_language: str,
        to_language: str,
        schema_context: str,
        db_type: str,
    ) -> Dict[str, Any]:
        return convert_code(
            code=code,
            from_language=from_language,
            to_language=to_language,
            schema_context=schema_context,
            db_type=db_type,
        )

