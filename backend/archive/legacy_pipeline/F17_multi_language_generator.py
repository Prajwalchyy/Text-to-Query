import os
import re
import json
from typing import Dict, Any, List, Optional
from openai import OpenAI
from F00_imports import *


# Supported languages metadata
LANGUAGE_CONFIG = {
    "sql": {
        "id": "sql",
        "name": "SQL",
        "badge": "SQLite Dialect",
        "color": "indigo",
        "supported_db_types": ["sql", "csv", "excel"]
    },
    "pandas": {
        "id": "pandas",
        "name": "Python (Pandas)",
        "badge": "Python / Pandas",
        "color": "cyan",
        "supported_db_types": ["sql", "csv", "excel", "nosql"]
    },
    "javascript": {
        "id": "javascript",
        "name": "JavaScript (Node.js)",
        "badge": "Node.js",
        "color": "amber",
        "supported_db_types": ["sql", "nosql", "csv", "excel"]
    },
    "java": {
        "id": "java",
        "name": "Java",
        "badge": "Java (JDBC / Driver)",
        "color": "orange",
        "supported_db_types": ["sql", "nosql", "csv", "excel"]
    },
    "r": {
        "id": "r",
        "name": "R",
        "badge": "R (tidyverse / DBI)",
        "color": "sky",
        "supported_db_types": ["sql", "nosql", "csv", "excel"]
    },
    "csharp": {
        "id": "csharp",
        "name": "C# (.NET)",
        "badge": "C# / .NET",
        "color": "purple",
        "supported_db_types": ["sql", "nosql", "csv", "excel"]
    },
    "nosql": {
        "id": "nosql",
        "name": "MongoDB MQL",
        "badge": "MongoDB MQL",
        "color": "emerald",
        "supported_db_types": ["nosql"]
    },
    "excel_formula": {
        "id": "excel_formula",
        "name": "Excel Formula",
        "badge": "Excel Formula",
        "color": "emerald",
        "supported_db_types": ["excel", "csv"]
    }
}


class MultiLanguageGenerator:
    """
    Universal Multi-Language Generator for OmniData AI.
    Translates user questions into production-ready, idiomatic code across:
    - SQL (SQLite)
    - Python (Pandas / Native)
    - JavaScript / TypeScript (Node.js)
    - Java (JDBC / MongoDB Driver / POI)
    - R (tidyverse / DBI)
    - C# (.NET / Dapper)
    - Excel Formula (Spreadsheets only)
    - MongoDB MQL (NoSQL only)
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

    @staticmethod
    def get_supported_languages(db_type: str) -> List[Dict[str, Any]]:
        """Returns the list of allowed languages for a specific database engine type."""
        clean_type = (db_type or "sql").lower()
        if clean_type in ["sqlite", "relational"]:
            clean_type = "sql"

        allowed = []
        for lang_id, cfg in LANGUAGE_CONFIG.items():
            if clean_type in cfg["supported_db_types"]:
                allowed.append(cfg)
        return allowed

    @staticmethod
    def is_language_supported(db_type: str, language: str) -> bool:
        """Validates if a target language is compatible with the given database type."""
        clean_type = (db_type or "sql").lower()
        if clean_type in ["sqlite", "relational"]:
            clean_type = "sql"

        cfg = LANGUAGE_CONFIG.get(language.lower())
        if not cfg:
            return False
        return clean_type in cfg["supported_db_types"]

    def generate_code(
        self,
        question: str,
        schema_context: str,
        db_type: str,
        target_language: str,
        db_name: str = "Database",
        table_or_sheet_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generates idiomatic code in the specified target language based on the database schema.
        Also returns an execution query (eval_sql or eval_pandas) so the backend can execute
        the underlying logic and return live data in the DataTable.
        """
        clean_type = (db_type or "sql").lower()
        if clean_type in ["sqlite", "relational"]:
            clean_type = "sql"

        target_lang = target_language.lower()
        if not self.is_language_supported(clean_type, target_lang):
            raise ValueError(
                f"Language '{target_language}' is not supported for '{db_type}' datasets. "
                f"Allowed languages: {[cfg['name'] for cfg in self.get_supported_languages(clean_type)]}"
            )

        system_prompt = self._build_prompt(clean_type, target_lang, schema_context, db_name, table_or_sheet_names)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0.0
        )

        raw_output = response.choices[0].message.content.strip()
        parsed = self._parse_json_response(raw_output)

        # Ensure language tag is set
        parsed["code_type"] = target_lang
        return parsed

    def convert_code(
        self,
        code: str,
        from_language: str,
        to_language: str,
        schema_context: str,
        db_type: str
    ) -> Dict[str, Any]:
        """Converts an existing query/code snippet from one language to another."""
        clean_type = (db_type or "sql").lower()
        to_lang = to_language.lower()

        if not self.is_language_supported(clean_type, to_lang):
            raise ValueError(
                f"Target language '{to_language}' is not supported for '{db_type}' datasets."
            )

        prompt = f"""You are an elite polyglot database engineer.
Convert the following {from_language.upper()} code into idiomatic {to_language.upper()} for a {clean_type.upper()} dataset.

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
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Convert this {from_language} code to {to_language}."}
            ],
            temperature=0.0
        )

        raw = response.choices[0].message.content.strip()
        parsed = self._parse_json_response(raw)
        parsed["code_type"] = to_lang
        return parsed

    def _build_prompt(
        self,
        db_type: str,
        target_lang: str,
        schema_context: str,
        db_name: str,
        table_names: Optional[List[str]]
    ) -> str:
        """Constructs the specialized system prompt for the chosen target language."""
        
        # 1. PYTHON / PANDAS
        if target_lang == "pandas":
            if db_type == "sql":
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
            elif db_type in ["csv", "excel"]:
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
            else: # nosql
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
        if target_lang == "sql" and db_type in ["csv", "excel"]:
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

        # 3. JAVASCRIPT / NODE.JS
        if target_lang == "javascript":
            driver = "better-sqlite3" if db_type == "sql" else "mongodb" if db_type == "nosql" else "danfojs-node"
            return f"""You are a Senior Full-Stack Node.js Developer.
Translate the user question into clean, modern JavaScript (Node.js) code to query this {db_type.upper()} dataset using `{driver}`.

Schema:
{schema_context}

Strict Rules:
1. Return a strict JSON object without markdown fences:
{{
  "title": "Concise Exact Goal",
  "code": "// JavaScript code with imports, connection, and console output",
  "eval_sql": "Equivalent SQL query if relational/csv/excel",
  "eval_mql": "Equivalent MQL query if nosql",
  "explanation": "Brief explanation of how the Node.js script executes the query."
}}
2. Code should be clean, modern (ES6+ async/await or arrow functions), with realistic connection handling.
"""

        # 4. JAVA
        if target_lang == "java":
            return f"""You are an Enterprise Java Developer.
Translate the user question into clean, production-grade Java code to query this {db_type.upper()} dataset using JDBC (PreparedStatement) or MongoDB Java Driver.

Schema:
{schema_context}

Strict Rules:
1. Return a strict JSON object without markdown fences:
{{
  "title": "Concise Exact Goal",
  "code": "// Clean Java class or method snippet with imports and try-with-resources",
  "eval_sql": "Equivalent SQL query if relational/csv/excel",
  "eval_mql": "Equivalent MQL query if nosql",
  "explanation": "Brief explanation of how the Java code executes the query."
}}
2. Write clean Java code with proper imports, parameter binding, and result handling.
"""

        # 5. R
        if target_lang == "r":
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

        # 6. C# (.NET)
        if target_lang == "csharp":
            return f"""You are a Senior .NET / C# Software Engineer.
Translate the user question into clean, idiomatic C# code using `Microsoft.Data.Sqlite`, Dapper, or `MongoDB.Driver`.

Schema:
{schema_context}

Strict Rules:
1. Return a strict JSON object without markdown fences:
{{
  "title": "Concise Exact Goal",
  "code": "// C# code using statements, strongly typed query execution, and Console.WriteLine",
  "eval_sql": "Equivalent SQL query if relational/csv/excel",
  "eval_mql": "Equivalent MQL query if nosql",
  "explanation": "Brief explanation of the C# code."
}}
2. Use modern C# syntax (top-level statements or clean using blocks).
"""

        # Fallback default
        return f"""You are an expert Software Engineer.
Translate the user question into valid {target_lang.upper()} code for the following schema:
{schema_context}

Return a strict JSON object without markdown fences:
{{
  "title": "Query Title",
  "code": "Code snippet in {target_lang}",
  "explanation": "Brief explanation."
}}
"""

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Safely parses JSON response, stripping markdown fences if present."""
        clean = text.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean)
            clean = clean.strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            # Fallback: regex match
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
            return {
                "title": "Generated Code",
                "code": clean,
                "explanation": "Code generated based on schema."
            }
