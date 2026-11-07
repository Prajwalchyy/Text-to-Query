"""
Unified Spreadsheet & Tabular Dialect (CSV & Excel).

Combines pure functional Python/Pandas AST security guardrails, spreadsheet loading,
schema generation, sandboxed Pandas vector execution, virtual in-memory SQLite ANSI SQL querying,
and modern Excel formula evaluation for tabular datasets (.csv, .xlsx, .xls).
"""

import ast
import json
import math
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd

from config import (
    BACKEND_DIR,
    CSV_DIR,
    DATA_DIR,
    DEFAULT_CSV_DIR,
    DEFAULT_CSV_PATH,
    DEFAULT_DATA_DIR,
    DEFAULT_EXCEL_PATH,
    DEFAULT_XLSX_DIR,
    EXCEL_DIR,
    UPLOADS_DIR,
)

# Shared Base Foundation
try:
    from dialects.base import (
        ValidationResult,
        resolve_dataset_file,
        sanitize_records_for_json,
        sanitize_scalar,
    )
except ImportError:
    from src.dialects.base import (
        ValidationResult,
        resolve_dataset_file,
        sanitize_records_for_json,
        sanitize_scalar,
    )


# ==============================================================================
# 1. Pandas AST Security Guardrails (Stateless Pure Functional)
# ==============================================================================
class PandasSecurityViolation(Exception):
    """Raised when Python/Pandas code violates AST security constraints."""
    pass


class PandasValidationResult(NamedTuple):
    """Immutable validation result for Pandas code."""

    is_valid: bool
    error: Optional[str]


FORBIDDEN_PANDAS_CALLS: Set[str] = {
    "eval",
    "exec",
    "open",
    "compile",
    "__import__",
    "globals",
    "locals",
    "getattr",
    "setattr",
    "delattr",
    "system",
    "popen",
    "spawn",
    "fork",
    "to_pickle",
    "read_pickle",
}

FORBIDDEN_PANDAS_MODULES: Set[str] = {
    "os",
    "sys",
    "subprocess",
    "shutil",
    "socket",
    "requests",
    "urllib",
    "pathlib",
    "builtins",
    "importlib",
    "pickle",
    "ctypes",
    "pty",
    "commands",
}


class PandasASTGuardrail(ast.NodeVisitor):
    """
    AST visitor inspecting Python/Pandas code before execution for defense-in-depth.
    """

    def __init__(
        self,
        forbidden_calls: Optional[Set[str]] = None,
        forbidden_modules: Optional[Set[str]] = None,
    ):
        self.forbidden_calls = forbidden_calls or FORBIDDEN_PANDAS_CALLS
        self.forbidden_modules = forbidden_modules or FORBIDDEN_PANDAS_MODULES
        self.violations: list[str] = []
        self.assigned_vars: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        self.violations.append("import statements are strictly forbidden.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.violations.append("from ... import statements are strictly forbidden.")
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.violations.append("while loops are forbidden to prevent infinite execution loops.")
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.violations.append(
            "Custom function definitions are disallowed; use idiomatic Pandas expressions."
        )
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.violations.append("Async function definitions are disallowed.")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.violations.append("Class definitions are disallowed.")
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        self.violations.append("del statements are disallowed.")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.assigned_vars.add(target.id)
            elif isinstance(target, (ast.Tuple, ast.List)):
                for elt in target.elts:
                    if isinstance(elt, ast.Name):
                        self.assigned_vars.add(elt.id)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name):
            self.assigned_vars.add(node.target.id)
        self.generic_visit(node)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        # Support walrus operator (result_df := ...)
        if isinstance(node.target, ast.Name):
            self.assigned_vars.add(node.target.id)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Check direct function call name (e.g. open('foo'))
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in self.forbidden_calls:
                self.violations.append(f"Calling dangerous function '{func_name}()' is forbidden.")
        # Check attribute/method calls (e.g. os.system() or df.to_pickle())
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in self.forbidden_calls:
                self.violations.append(f"Calling attribute/method '{attr_name}()' is forbidden.")

        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in self.forbidden_modules:
            self.violations.append(f"Accessing module '{node.id}' is strictly forbidden.")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__") and node.attr.endswith("__"):
            self.violations.append(f"Accessing dunder attribute '{node.attr}' is forbidden.")
        self.generic_visit(node)


def clean_code_markdown(code: str) -> str:
    """Removes markdown code fences from LLM output."""
    clean = code.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:python|py)?\n?", "", clean)
        clean = re.sub(r"\n?```$", "", clean)
    return clean.strip()


def validate_pandas_code(
    code: str,
    enforce_result_df: bool = True,
    forbidden_calls: Optional[Set[str]] = None,
    forbidden_modules: Optional[Set[str]] = None,
) -> PandasValidationResult:
    """
    Validates Python/Pandas code through AST parsing and security visitor.
    """
    clean_code = clean_code_markdown(code) if code else ""
    if not clean_code:
        return PandasValidationResult(False, "Code string is empty.")

    try:
        tree = ast.parse(clean_code)
    except SyntaxError as e:
        return PandasValidationResult(False, f"Python Syntax Error: {str(e)}")

    visitor = PandasASTGuardrail(
        forbidden_calls=forbidden_calls,
        forbidden_modules=forbidden_modules,
    )
    visitor.visit(tree)

    # 1. Report dangerous security violations first
    if visitor.violations:
        return PandasValidationResult(
            False,
            "Security Guardrail Rejection: " + "; ".join(visitor.violations),
        )

    # 2. Enforce output assignment to result_df if requested
    if enforce_result_df and "result_df" not in visitor.assigned_vars:
        return PandasValidationResult(
            False,
            "Security Guardrail Rejection: Code must assign output DataFrame to 'result_df'.",
        )

    return PandasValidationResult(True, None)


# ==============================================================================
# 2. Path Resolution & Coordinate Helpers
# ==============================================================================
def resolve_spreadsheet_path(
    target_path: Optional[Union[Path, str]] = None,
    file_type: Optional[str] = None
) -> Path:
    """
    Resolves various representations of a CSV or Excel dataset path (relative,
    absolute, or alias) into a canonical Path object.
    """
    is_excel = bool(file_type and file_type.lower() in ("excel", "xlsx", "xls"))
    if not is_excel and target_path:
        str_val = str(target_path).lower()
        if str_val.endswith(".xlsx") or str_val.endswith(".xls") or "budget" in str_val:
            is_excel = True

    default_path = DEFAULT_EXCEL_PATH if is_excel else DEFAULT_CSV_PATH
    default_alias = ["financial_budget"] if is_excel else ["sales_performance"]

    search_dirs = [
        DEFAULT_DATA_DIR,
        DEFAULT_EXCEL_PATH.parent if is_excel else DEFAULT_CSV_PATH.parent,
        DEFAULT_XLSX_DIR if is_excel else DEFAULT_CSV_DIR,
        EXCEL_DIR if is_excel else CSV_DIR,
        UPLOADS_DIR,
        UPLOADS_DIR / ("excel" if is_excel else "csv"),
        DATA_DIR,
        BACKEND_DIR,
    ]

    return resolve_dataset_file(
        target_path=target_path,
        default_path=default_path,
        search_directories=search_dirs,
        default_alias_names=default_alias,
    )


def excel_col_letter(col_idx: int) -> str:
    """Converts 0-based column index to Excel column letter (0 -> A, 27 -> AB)."""
    result = ""
    col_idx += 1
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result = chr(65 + remainder) + result
    return result


def letter_to_col_index(letter: str) -> int:
    """Converts Excel column letter to 0-based index ('A' -> 0, 'Z' -> 25, 'AA' -> 26)."""
    result = 0
    for char in letter.upper():
        result = result * 26 + (ord(char) - ord("A") + 1)
    return result - 1


# ==============================================================================
# 3. Spreadsheet Data Loaders & Schema Introspection
# ==============================================================================
def load_spreadsheet(
    file_path: Optional[Union[Path, str]] = None,
    file_type: Optional[str] = None
) -> Dict[str, pd.DataFrame]:
    """
    Loads CSV or Excel workbook into a dictionary of DataFrames mapping:
    sheet_name -> pd.DataFrame.
    """
    path = resolve_spreadsheet_path(file_path, file_type)
    if not path.exists():
        return {}

    ext = path.suffix.lower()

    # Excel Multi-sheet Workbook
    if ext in [".xlsx", ".xls"] or (file_type and file_type.lower() == "excel"):
        try:
            excel_file = pd.ExcelFile(path)
            sheets: Dict[str, pd.DataFrame] = {}
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                df.columns = [str(c).strip() for c in df.columns]
                sheets[sheet_name] = df
            return sheets
        except Exception:
            return {}

    # CSV Dataset
    try:
        df = pd.read_csv(path)
        df.columns = [str(c).strip() for c in df.columns]
        sheet_name = path.stem.lower().replace("-", "_").replace(" ", "_")
        return {sheet_name: df}
    except Exception:
        return {}


def get_spreadsheet_schema(
    dfs: Optional[Dict[str, pd.DataFrame]] = None,
    file_path: Optional[Union[Path, str]] = None,
    file_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generates a structured schema catalog for spreadsheets matching unified database schema:
    {"tables": [...], "sheets": [...], "relationships": []}
    """
    if dfs is None:
        dfs = load_spreadsheet(file_path, file_type=file_type)

    schema_tables = []
    sheets_info = {}

    for sheet_name, df in dfs.items():
        row_count = len(df)
        cols_meta = []
        col_list = []

        for i, col in enumerate(df.columns):
            col_letter = excel_col_letter(i)
            dtype_name = str(df[col].dtype)
            sample_vals = df[col].dropna().head(3).tolist()
            sample_clean = [sanitize_scalar(v) for v in sample_vals]

            col_list.append(f"{col} ({dtype_name})")
            cols_meta.append({
                "column_index": i,
                "excel_column": col_letter,
                "name": str(col),
                "letter": col_letter,
                "type": dtype_name,
                "non_null_count": int(df[col].count()),
                "sample_values": sample_clean,
                "range": f"{col_letter}2:{col_letter}{row_count + 1}" if row_count > 0 else f"{col_letter}1",
            })

        max_letter = excel_col_letter(len(df.columns) - 1) if len(df.columns) > 0 else "A"
        sheet_entry = {
            "name": sheet_name,
            "cols": col_list,
            "count": row_count,
            "row_count": row_count,
            "column_count": len(df.columns),
            "columns": cols_meta,
            "columns_meta": cols_meta,
            "excel_range": f"A1:{max_letter}{max(1, row_count + 1)}",
            "data_range": f"A2:{max_letter}{max(2, row_count + 1)}" if row_count > 0 else f"A1:{max_letter}1",
        }
        schema_tables.append(sheet_entry)
        sheets_info[sheet_name] = sheet_entry

    return {
        "tables": schema_tables,
        "sheets": sheets_info,
        "sheet_names": list(dfs.keys()),
        "relationships": [],
        "file_type": file_type or "tabular",
    }


def format_spreadsheet_schema_context(
    dfs: Optional[Dict[str, pd.DataFrame]] = None,
    file_path: Optional[Union[Path, str]] = None,
    file_type: Optional[str] = None,
) -> str:
    """
    Generates comprehensive, formatted markdown schema context for LLM prompts:
    - Sheet names, row counts, and cell coordinate ranges
    - Columns with data types, Excel letters, and sample data values
    - Sample 3-row JSON previews
    """
    if dfs is None:
        dfs = load_spreadsheet(file_path, file_type=file_type)

    context_parts: List[str] = []

    for sheet_name, df in dfs.items():
        row_count = len(df)
        col_count = len(df.columns)
        end_col_letter = excel_col_letter(max(0, col_count - 1))
        data_range = f"A2:{end_col_letter}{row_count + 1}" if row_count > 0 else "Empty"

        part = [
            f"### Sheet: '{sheet_name}' (Total Rows: {row_count}, Columns: {col_count})",
            f"Data Range: {data_range} (Header on Row 1, Data on Rows 2 to {row_count + 1})\n",
            "Columns & Cell Coordinates:",
        ]

        for i, col in enumerate(df.columns):
            dtype_name = str(df[col].dtype)
            col_letter_val = excel_col_letter(i)
            col_range = f"{col_letter_val}2:{col_letter_val}{row_count + 1}"
            sample_vals = [str(v) for v in df[col].dropna().head(3).tolist()]
            sample_str = ", ".join(sample_vals) if sample_vals else "None"
            part.append(
                f"- Column {col_letter_val} (`{col}`): dtype={dtype_name} | Range={col_range} | Samples: [{sample_str}]"
            )

        preview_rows = df.head(3).to_dict(orient="records")
        cleaned_preview = clean_records_for_json(preview_rows)
        part.append("\nSample Data (First 3 Rows):")
        part.append(json.dumps(cleaned_preview, indent=2, default=str))

        context_parts.append("\n".join(part))

    return "\n\n" + ("=" * 50) + "\n\n" + "\n\n".join(context_parts)


# Backward-compatible alias for record sanitizer
clean_records_for_json = sanitize_records_for_json


# ==============================================================================
# 4. Multi-Paradigm Tabular Execution
# ==============================================================================
def execute_pandas_code(
    dfs: Dict[str, pd.DataFrame],
    code: str,
    primary_sheet: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Executes sandboxed Python/Pandas code against the spreadsheet DataFrame dictionary.
    """
    clean_code = clean_code_markdown(code)
    target_sheet = primary_sheet or (list(dfs.keys())[0] if dfs else "default")
    df_primary = dfs.get(target_sheet, pd.DataFrame())

    local_ns = {
        "pd": pd,
        "np": np,
        "df": df_primary.copy(),
        "dfs": {k: v.copy() for k, v in dfs.items()},
        "result_df": None,
    }

    for k, v in dfs.items():
        clean_var_name = re.sub(r"\W|^(?=\d)", "_", k)
        local_ns[clean_var_name] = v.copy()

    safe_builtins = {
        "len": len,
        "range": range,
        "round": round,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "min": min,
        "max": max,
        "sum": sum,
        "any": any,
        "all": all,
        "sorted": sorted,
        "abs": abs,
        "enumerate": enumerate,
        "zip": zip,
    }

    exec(clean_code, {"__builtins__": safe_builtins}, local_ns)

    result_df = local_ns.get("result_df")

    if result_df is None:
        return []

    if isinstance(result_df, pd.Series):
        result_df = result_df.to_frame()

    if isinstance(result_df, (int, float, str, bool, np.number, np.bool_)):
        return [{"Result": sanitize_scalar(result_df)}]

    if isinstance(result_df, pd.DataFrame):
        records = result_df.to_dict(orient="records")
        return clean_records_for_json(records)

    if isinstance(result_df, list):
        return clean_records_for_json(result_df)

    if isinstance(result_df, dict):
        return [clean_records_for_json([result_df])[0]]

    return []


def execute_sql_on_spreadsheet(
    dfs: Dict[str, pd.DataFrame],
    sql_query: str,
    primary_sheet: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Executes an ANSI SQL query against spreadsheet sheets loaded as virtual
    in-memory SQLite tables.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    try:
        for sheet_name, df in dfs.items():
            clean_tbl_name = re.sub(r"[^a-zA-Z0-9_]", "_", sheet_name.strip()).lower()
            df.to_sql(clean_tbl_name, conn, index=False, if_exists="replace")

            # Common aliases for single-sheet datasets
            if len(dfs) == 1:
                df.to_sql("data", conn, index=False, if_exists="replace")
                df.to_sql("sales", conn, index=False, if_exists="replace")

        primary_name = primary_sheet or (list(dfs.keys())[0] if dfs else None)
        if primary_name and primary_name in dfs:
            dfs[primary_name].to_sql("df", conn, index=False, if_exists="replace")

        cursor = conn.cursor()
        cursor.execute(sql_query)

        if cursor.description is None:
            return []

        rows = cursor.fetchall()
        results = [dict(r) for r in rows]
        return clean_records_for_json(results)
    finally:
        conn.close()


def _parse_cell_range(cell_range_str: str, df: pd.DataFrame) -> pd.DataFrame:
    """Parses Excel coordinate string (e.g. 'A2:C10' or 'A:C') into a DataFrame slice."""
    clean = cell_range_str.strip().upper()
    if ":" not in clean:
        if clean in df.columns:
            return df[[clean]]
        return df

    start_cell, end_cell = clean.split(":")
    start_match = re.match(r"^([A-Z]+)(\d+)?$", start_cell)
    end_match = re.match(r"^([A-Z]+)(\d+)?$", end_cell)

    if not start_match or not end_match:
        return df

    start_col_letter, start_row_s = start_match.groups()
    end_col_letter, end_row_s = end_match.groups()

    start_col_idx = letter_to_col_index(start_col_letter)
    end_col_idx = letter_to_col_index(end_col_letter)

    start_col_idx = max(0, min(start_col_idx, len(df.columns) - 1))
    end_col_idx = max(start_col_idx, min(end_col_idx, len(df.columns) - 1))

    # Row slicing (1-based Excel row, header is row 1 -> row 2 is index 0)
    start_row_idx = (int(start_row_s) - 2) if start_row_s else 0
    end_row_idx = (int(end_row_s) - 1) if end_row_s else len(df)

    start_row_idx = max(0, min(start_row_idx, len(df)))
    end_row_idx = max(start_row_idx, min(end_row_idx, len(df)))

    return df.iloc[start_row_idx:end_row_idx, start_col_idx:end_col_idx + 1]


def execute_excel_formula(
    dfs: Dict[str, pd.DataFrame],
    formula: str,
    primary_sheet: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Evaluates standard Excel formulas (SUM, AVERAGE, COUNT, MIN, MAX, MEDIAN,
    SUMIFS, FILTER) directly against the DataFrames.
    """
    clean_f = formula.strip().lstrip("=").strip()
    sheet_name = primary_sheet or (list(dfs.keys())[0] if dfs else "default")
    df = dfs.get(sheet_name, pd.DataFrame())

    simple_func_match = re.match(r"^([A-Z]+)\s*\(\s*([A-Z0-9:]+)\s*\)$", clean_f, re.IGNORECASE)
    if simple_func_match:
        func_name = simple_func_match.group(1).upper()
        arg_range = simple_func_match.group(2)
        sliced_df = _parse_cell_range(arg_range, df)

        numeric_series = pd.to_numeric(sliced_df.iloc[:, 0], errors="coerce").dropna()
        val = None

        if func_name in ("SUM",):
            val = round(float(numeric_series.sum()), 2)
        elif func_name in ("AVERAGE", "AVG"):
            val = round(float(numeric_series.mean()), 2) if len(numeric_series) > 0 else None
        elif func_name in ("COUNT",):
            val = int(numeric_series.count())
        elif func_name in ("COUNTA",):
            val = int(sliced_df.iloc[:, 0].dropna().count())
        elif func_name in ("MIN",):
            val = float(numeric_series.min()) if len(numeric_series) > 0 else None
        elif func_name in ("MAX",):
            val = float(numeric_series.max()) if len(numeric_series) > 0 else None
        elif func_name in ("MEDIAN",):
            val = float(numeric_series.median()) if len(numeric_series) > 0 else None

        return [{"Formula": formula, "Function": func_name, "Range": arg_range, "Result": val}]

    sumifs_match = re.match(
        r"^SUMIFS\s*\(\s*([A-Z0-9:]+)\s*,\s*([A-Z0-9:]+)\s*,\s*[\"']?([^\"']+)[\"']?\s*\)$",
        clean_f,
        re.IGNORECASE,
    )
    if sumifs_match:
        sum_range_str, crit_range_str, criterion = sumifs_match.groups()
        sum_slice = _parse_cell_range(sum_range_str, df).iloc[:, 0]
        crit_slice = _parse_cell_range(crit_range_str, df).iloc[:, 0]

        mask = crit_slice.astype(str).str.strip().str.lower() == criterion.strip().lower()
        num_sum = pd.to_numeric(sum_slice[mask], errors="coerce").dropna()
        res_val = round(float(num_sum.sum()), 2)

        return [{"Formula": formula, "Function": "SUMIFS", "Criterion": criterion, "Result": res_val}]

    filter_match = re.match(
        r"^FILTER\s*\(\s*([A-Z0-9:]+)\s*,\s*([A-Z0-9:]+)\s*([<>=!]+)\s*([^)]+)\s*\)$",
        clean_f,
        re.IGNORECASE,
    )
    if filter_match:
        data_range_str, cond_range_str, op, val_str = filter_match.groups()
        data_slice = _parse_cell_range(data_range_str, df)
        cond_slice = _parse_cell_range(cond_range_str, df).iloc[:, 0]

        raw_val = val_str.strip().strip("'\"")
        try:
            num_val = float(raw_val)
            cond_numeric = pd.to_numeric(cond_slice, errors="coerce")
            if op == "<":
                mask = cond_numeric < num_val
            elif op == "<=":
                mask = cond_numeric <= num_val
            elif op == ">":
                mask = cond_numeric > num_val
            elif op == ">=":
                mask = cond_numeric >= num_val
            elif op in ("=", "=="):
                mask = cond_numeric == num_val
            else:
                mask = cond_numeric != num_val
        except ValueError:
            if op in ("=", "=="):
                mask = cond_slice.astype(str).str.strip().str.lower() == raw_val.lower()
            else:
                mask = cond_slice.astype(str).str.strip().str.lower() != raw_val.lower()

        filtered_df = data_slice[mask]
        records = filtered_df.to_dict(orient="records")
        return clean_records_for_json(records)

    return [{"Formula": formula, "Status": "Parsed", "TargetSheet": sheet_name}]


# ==============================================================================
# 5. Backward-Compatible Adapter Class
# ==============================================================================
class SpreadsheetEngine:
    """
    Backward-compatible OOP adapter matching legacy F13 SpreadsheetEngine interface.
    Delegates all operations to pure functional spreadsheet engine methods.
    """

    def __init__(self, file_path: Union[str, Path], file_type: Optional[str] = None):
        self.file_path = resolve_spreadsheet_path(file_path, file_type)
        if not self.file_path.exists():
            raise FileNotFoundError(f"Spreadsheet file not found: {self.file_path}")

        ext = self.file_path.suffix.lower()
        if file_type:
            self.file_type = file_type.lower()
        elif ext in [".xlsx", ".xls"]:
            self.file_type = "excel"
        else:
            self.file_type = "csv"

        self.dfs = load_spreadsheet(self.file_path, self.file_type)
        self.primary_sheet_name = list(self.dfs.keys())[0] if self.dfs else "default"

    def get_sheet_names(self) -> List[str]:
        return list(self.dfs.keys())

    @property
    def primary_df(self) -> pd.DataFrame:
        return self.dfs[self.primary_sheet_name]

    def get_schema_context(self) -> str:
        return format_spreadsheet_schema_context(self.dfs, file_type=self.file_type)

    def execute_pandas_code(self, code: str) -> List[Dict[str, Any]]:
        return execute_pandas_code(self.dfs, code, primary_sheet=self.primary_sheet_name)

    def execute_sql_query(self, sql: str) -> List[Dict[str, Any]]:
        return execute_sql_on_spreadsheet(self.dfs, sql, primary_sheet=self.primary_sheet_name)

    def execute_excel_formula(self, formula: str) -> List[Dict[str, Any]]:
        return execute_excel_formula(self.dfs, formula, primary_sheet=self.primary_sheet_name)


TabularEngine = SpreadsheetEngine
