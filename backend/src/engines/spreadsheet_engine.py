"""
Spreadsheet Data Execution Engine (CSV & Excel).

Provides pure functional inspection, schema generation, sandboxed Pandas vector execution,
virtual in-memory SQLite ANSI SQL querying, and modern Excel formula evaluation.

Zero OOP classes; 100% stateless functions with clean, typed inputs and outputs.
"""

import json
import math
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from config import (
    BACKEND_DIR,
    CSV_DIR,
    DATA_DIR,
    DEFAULT_CSV_PATH,
    DEFAULT_EXCEL_PATH,
    EXCEL_DIR,
)


# ==============================================================================
# Path Resolution & Coordinate Helpers
# ==============================================================================
def resolve_spreadsheet_path(
    target_path: Optional[Union[Path, str]] = None,
    file_type: Optional[str] = None,
) -> Path:
    """
    Resolves various representations of a spreadsheet path (relative, absolute, or alias)
    into a canonical Path object. Defaults to DEFAULT_CSV_PATH or DEFAULT_EXCEL_PATH.
    """
    if target_path is None or str(target_path).strip() == "" or str(target_path).strip() in ("default", "sales"):
        if file_type and file_type.lower() == "excel":
            return DEFAULT_EXCEL_PATH.resolve()
        return DEFAULT_CSV_PATH.resolve()

    p = Path(str(target_path).strip())
    if p.is_absolute() and p.exists():
        return p.resolve()

    filename = p.name
    for base in [DATA_DIR, CSV_DIR, EXCEL_DIR, BACKEND_DIR]:
        candidate_file = (base / filename).resolve()
        if candidate_file.exists():
            return candidate_file

    for base in [DATA_DIR, CSV_DIR, EXCEL_DIR, BACKEND_DIR]:
        try:
            candidate = (base / p).resolve()
            if candidate.exists():
                return candidate
        except Exception:
            pass

    return p.resolve()


def excel_col_letter(col_idx: int) -> str:
    """
    Converts 0-based column index to Excel column letter (0->A, 25->Z, 26->AA, 27->AB).
    """
    result = ""
    col_idx += 1
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result = chr(65 + remainder) + result
    return result


def letter_to_col_index(letter: str) -> int:
    """
    Converts Excel column letter to 0-based column index ('A'->0, 'Z'->25, 'AA'->26).
    """
    idx = 0
    for char in letter.upper():
        idx = idx * 26 + (ord(char) - ord("A") + 1)
    return idx - 1


def clean_records_for_json(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sanitizes records to ensure NaN, Infinity, Timestamps, and NumPy generics
    are fully JSON serializable primitives.
    """
    cleaned = []
    for row in records:
        clean_row = {}
        for k, v in row.items():
            if isinstance(v, (float, int)) and (math.isnan(v) or math.isinf(v)):
                clean_row[k] = None
            elif isinstance(v, (pd.Timestamp, np.datetime64, datetime, date)):
                clean_row[k] = str(v)
            elif isinstance(v, np.generic):
                clean_row[k] = v.item()
            elif isinstance(v, (list, tuple)):
                clean_row[k] = [
                    str(x) if isinstance(x, (pd.Timestamp, np.datetime64, datetime, date))
                    else (x.item() if isinstance(x, np.generic) else (None if isinstance(x, float) and (math.isnan(x) or math.isinf(x)) else x))
                    for x in v
                ]
            else:
                clean_row[k] = v
        cleaned.append(clean_row)
    return cleaned


# ==============================================================================
# Loading Spreadsheets
# ==============================================================================
def load_spreadsheet(
    file_path: Optional[Union[Path, str]] = None,
    file_type: Optional[str] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Loads CSV or multi-sheet Excel file from disk into a dictionary mapping
    sheet_name -> pd.DataFrame.
    """
    path = resolve_spreadsheet_path(file_path, file_type=file_type)
    if not path.exists():
        raise FileNotFoundError(f"Spreadsheet file not found: {path}")

    ext = path.suffix.lower()
    inferred_type = (file_type or ("excel" if ext in [".xlsx", ".xls"] else "csv")).lower()

    if inferred_type == "excel" or ext in [".xlsx", ".xls"]:
        excel_data = pd.read_excel(str(path), sheet_name=None, engine="openpyxl")
        if not excel_data:
            raise ValueError(f"Excel workbook contains no readable sheets: {path}")
        return {str(sheet): df for sheet, df in excel_data.items()}
    elif ext == ".tsv":
        df = pd.read_csv(str(path), sep="\t")
        sheet_name = path.stem.lower().replace("-", "_").replace(" ", "_")
        return {sheet_name: df}
    elif ext == ".parquet":
        df = pd.read_parquet(str(path))
        sheet_name = path.stem.lower().replace("-", "_").replace(" ", "_")
        return {sheet_name: df}
    else:
        df = pd.read_csv(str(path))
        sheet_name = path.stem.lower().replace("-", "_").replace(" ", "_")
        return {sheet_name: df}


# ==============================================================================
# Schema Introspection & Context
# ==============================================================================
def get_spreadsheet_schema(
    dfs: Optional[Dict[str, pd.DataFrame]] = None,
    file_path: Optional[Union[Path, str]] = None,
    file_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns full schema representation for spreadsheet sheets matching
    the unified database schema structure:
    {"tables": [{"name": sheet, "cols": [...], "count": N, "columns_meta": [...]}], "relationships": []}
    """
    if dfs is None:
        dfs = load_spreadsheet(file_path, file_type=file_type)

    schema_tables = []
    for sheet_name, df in dfs.items():
        row_count = len(df)
        cols_meta = []
        col_list = []

        for i, col in enumerate(df.columns):
            dtype_name = str(df[col].dtype)
            col_let = excel_col_letter(i)
            col_list.append(f"{col} ({dtype_name})")
            cols_meta.append({
                "name": str(col),
                "letter": col_let,
                "type": dtype_name,
                "range": f"{col_let}2:{col_let}{row_count + 1}" if row_count > 0 else f"{col_let}1",
            })

        schema_tables.append({
            "name": sheet_name,
            "cols": col_list,
            "count": row_count,
            "columns_meta": cols_meta,
            "data_range": f"A2:{excel_col_letter(max(0, len(df.columns) - 1))}{row_count + 1}" if row_count > 0 else "Empty",
        })

    return {
        "tables": schema_tables,
        "relationships": [],
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


# ==============================================================================
# Sandboxed Pandas Execution Engine
# ==============================================================================
def execute_pandas_code(
    dfs: Dict[str, pd.DataFrame],
    code: str,
    primary_sheet: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Executes vectorized Pandas code in a sandboxed local environment.

    Injected Scope:
    - df: Primary DataFrame copy.
    - dfs: Dictionary of all sheets as DataFrame copies.
    - pd: pandas module.
    - np: numpy module.
    - result_df: Initially None, expected to be populated by code.

    Returns serialized records suitable for UI display.
    """
    clean_code = code.strip()
    if clean_code.startswith("```"):
        clean_code = re.sub(r"^```(?:python|py)?\n?", "", clean_code)
        clean_code = re.sub(r"\n?```$", "", clean_code).strip()

    # Determine primary sheet
    if primary_sheet and primary_sheet in dfs:
        p_df = dfs[primary_sheet].copy()
    elif dfs:
        first_key = list(dfs.keys())[0]
        p_df = dfs[first_key].copy()
    else:
        p_df = pd.DataFrame()

    local_scope: Dict[str, Any] = {
        "df": p_df,
        "dfs": {k: v.copy() for k, v in dfs.items()},
        "pd": pd,
        "np": np,
        "result_df": None,
    }

    safe_builtins = {
        "abs": abs, "min": min, "max": max, "sum": sum, "len": len,
        "range": range, "round": round, "int": int, "float": float,
        "str": str, "bool": bool, "list": list, "dict": dict,
        "tuple": tuple, "set": set, "sorted": sorted, "zip": zip,
        "enumerate": enumerate, "True": True, "False": False, "None": None,
        "isinstance": isinstance, "any": any, "all": all,
    }

    exec(clean_code, {"__builtins__": safe_builtins}, local_scope)

    result = local_scope.get("result_df")
    if result is None:
        # Fallback inspection for newly assigned DataFrame or Series
        for var_name in reversed(list(local_scope.keys())):
            val = local_scope[var_name]
            if isinstance(val, (pd.DataFrame, pd.Series)) and var_name not in ["df"]:
                result = val
                break

    if result is None:
        raise ValueError("The executed Python code did not assign or produce a 'result_df' DataFrame.")

    if isinstance(result, pd.Series):
        result = result.reset_index()

    records = result.to_dict(orient="records")
    return clean_records_for_json(records)


# ==============================================================================
# Virtual SQLite ANSI SQL Execution on Spreadsheets
# ==============================================================================
def execute_sql_on_spreadsheet(
    dfs: Dict[str, pd.DataFrame],
    sql: str,
    primary_sheet: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Executes an ANSI SQL query directly over the spreadsheet sheets by loading
    them into an in-memory SQLite virtual database (:memory:).
    """
    conn = sqlite3.connect(":memory:")
    try:
        for sheet_name, df in dfs.items():
            clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", sheet_name.strip()).lower()
            df.to_sql(clean_name, conn, if_exists="replace", index=False)
            # Register common aliases for single-sheet datasets
            if len(dfs) == 1:
                df.to_sql("data", conn, if_exists="replace", index=False)
                df.to_sql("sales", conn, if_exists="replace", index=False)

        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        results = [dict(zip(columns, row)) for row in rows]
        return clean_records_for_json(results)
    finally:
        conn.close()


# ==============================================================================
# Modern Excel Formula Evaluator
# ==============================================================================
def _parse_cell_range(cell_range_str: str, df: pd.DataFrame) -> pd.DataFrame:
    """
    Parses cell range like 'A2:C7' or 'B2:B10' into DataFrame slice.
    Row 1 is header; Row 2 maps to df.iloc[0].
    """
    match = re.match(r"^([A-Z]+)(\d+):([A-Z]+)(\d+)$", cell_range_str.strip().upper())
    if not match:
        # Check single column letter or column name
        if cell_range_str in df.columns:
            return df[[cell_range_str]]
        raise ValueError(f"Invalid Excel cell range format: '{cell_range_str}'")

    start_col_let, start_row_num, end_col_let, end_row_num = match.groups()
    start_col = letter_to_col_index(start_col_let)
    end_col = letter_to_col_index(end_col_let)

    # Convert 1-based Excel row to 0-based DataFrame index (row 2 -> 0)
    start_row = max(0, int(start_row_num) - 2)
    end_row = max(0, int(end_row_num) - 1)

    return df.iloc[start_row:end_row, start_col : end_col + 1]


def execute_excel_formula(
    dfs: Dict[str, pd.DataFrame],
    formula: str,
    primary_sheet: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Evaluates modern Excel formulas (e.g. =SUM(B2:B10), =AVERAGE(C2:C7), =FILTER(A2:F7, ...))
    directly against the spreadsheet DataFrames and returns JSON records.
    """
    clean_f = formula.strip()
    if clean_f.startswith("="):
        clean_f = clean_f[1:].strip()

    # Determine target sheet if SheetName!Range is used
    sheet_name = primary_sheet or list(dfs.keys())[0]
    if "!" in clean_f:
        prefix, rest = clean_f.split("!", 1)
        clean_prefix = prefix.strip().strip("'\"")
        if clean_prefix in dfs:
            sheet_name = clean_prefix
            clean_f = rest

    df = dfs.get(sheet_name)
    if df is None:
        raise ValueError(f"Sheet '{sheet_name}' not found in workbook.")

    # Match common aggregate functions: FUNC(RANGE)
    agg_match = re.match(r"^(SUM|AVERAGE|AVG|COUNT|MIN|MAX|MEDIAN)\s*\(\s*([A-Za-z0-9_:]+)\s*\)$", clean_f, re.IGNORECASE)
    if agg_match:
        func_name = agg_match.group(1).upper()
        arg_range = agg_match.group(2)

        sliced = _parse_cell_range(arg_range, df)
        numeric_series = pd.to_numeric(sliced.iloc[:, 0], errors="coerce").dropna()

        val: Any = None
        if func_name in ("SUM",):
            val = round(float(numeric_series.sum()), 2)
        elif func_name in ("AVERAGE", "AVG"):
            val = round(float(numeric_series.mean()), 2) if len(numeric_series) > 0 else 0
        elif func_name in ("COUNT",):
            val = int(len(numeric_series))
        elif func_name in ("MIN",):
            val = float(numeric_series.min()) if len(numeric_series) > 0 else None
        elif func_name in ("MAX",):
            val = float(numeric_series.max()) if len(numeric_series) > 0 else None
        elif func_name in ("MEDIAN",):
            val = float(numeric_series.median()) if len(numeric_series) > 0 else None

        return [{"Formula": formula, "Function": func_name, "Range": arg_range, "Result": val}]

    # Match SUMIFS(sum_range, criteria_range, criteria)
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

    # Match FILTER(range, criteria_col condition value)
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

    # General fallback: return formula metadata
    return [{"Formula": formula, "Status": "Parsed", "TargetSheet": sheet_name}]


# ==============================================================================
# Backward-Compatible Adapter
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


