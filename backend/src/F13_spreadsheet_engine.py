import os
import re
import json
import math
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union


class SpreadsheetEngine:
    """
    High-performance engine for inspecting and querying CSV and Excel files.
    - Loads CSV into a primary DataFrame.
    - Loads Excel workbooks into multi-sheet DataFrames with cell-coordinate mapping.
    - Provides rich schema context with sample rows and column types for LLM grounding.
    """

    def __init__(self, file_path: str, file_type: Optional[str] = None):
        self.file_path = Path(file_path).resolve()
        if not self.file_path.exists():
            raise FileNotFoundError(f"Spreadsheet file not found: {self.file_path}")

        ext = self.file_path.suffix.lower()
        if file_type:
            self.file_type = file_type.lower()
        elif ext in [".xlsx", ".xls"]:
            self.file_type = "excel"
        else:
            self.file_type = "csv"

        self.dfs: Dict[str, pd.DataFrame] = {}
        self.primary_sheet_name: str = "default"
        self._load_data()

    def _load_data(self) -> None:
        """Loads the CSV or Excel file into DataFrames."""
        if self.file_type == "excel":
            # Load all sheets as dict of {sheet_name: DataFrame}
            excel_data = pd.read_excel(str(self.file_path), sheet_name=None, engine="openpyxl")
            if not excel_data:
                raise ValueError("Excel file contains no readable worksheets.")
            self.dfs = excel_data
            self.primary_sheet_name = list(self.dfs.keys())[0]
        else:
            # Load single CSV
            df = pd.read_csv(str(self.file_path))
            sheet_name = self.file_path.stem
            self.dfs = {sheet_name: df}
            self.primary_sheet_name = sheet_name

    def get_sheet_names(self) -> List[str]:
        """Returns sheet/table names available in this spreadsheet."""
        return list(self.dfs.keys())

    @property
    def primary_df(self) -> pd.DataFrame:
        """Returns the main active DataFrame."""
        return self.dfs[self.primary_sheet_name]

    @staticmethod
    def _excel_col_letter(col_idx: int) -> str:
        """Converts 0-based column index to Excel column letter (0->A, 25->Z, 26->AA)."""
        result = ""
        col_idx += 1
        while col_idx > 0:
            col_idx, remainder = divmod(col_idx - 1, 26)
            result = chr(65 + remainder) + result
        return result

    def get_schema_context(self) -> str:
        """
        Generates comprehensive schema context for LLM prompt:
        - Sheet names and row counts
        - Column names, data types, and Excel column letters
        - Cell coordinate ranges (e.g. A2:F13)
        - 3 sample data rows
        """
        context_parts = []

        for sheet_name, df in self.dfs.items():
            row_count = len(df)
            col_count = len(df.columns)
            end_col_letter = self._excel_col_letter(max(0, col_count - 1))
            data_range = f"A2:{end_col_letter}{row_count + 1}" if row_count > 0 else "Empty"

            part = [
                f"### Sheet: '{sheet_name}' (Total Rows: {row_count}, Columns: {col_count})",
                f"Data Range: {data_range} (Header on Row 1, Data on Rows 2 to {row_count + 1})\n",
                "Columns & Cell Coordinates:"
            ]

            for i, col in enumerate(df.columns):
                dtype_name = str(df[col].dtype)
                col_letter = self._excel_col_letter(i)
                col_range = f"{col_letter}2:{col_letter}{row_count + 1}"
                sample_vals = [str(v) for v in df[col].dropna().head(3).tolist()]
                sample_str = ", ".join(sample_vals) if sample_vals else "None"
                part.append(f"- Column {col_letter} (`{col}`): dtype={dtype_name} | Range={col_range} | Samples: [{sample_str}]")

            # Sample 3 rows preview
            preview_rows = df.head(3).to_dict(orient="records")
            cleaned_preview = self._clean_records_for_json(preview_rows)
            part.append("\nSample Data (First 3 Rows):")
            part.append(json.dumps(cleaned_preview, indent=2, default=str))

            context_parts.append("\n".join(part))

        return "\n\n" + ("=" * 50) + "\n\n" + "\n\n".join(context_parts)

    def execute_pandas_code(self, code: str) -> List[Dict[str, Any]]:
        """
        Executes verified Pandas code in a sandboxed local environment.
        - `df`: Primary DataFrame.
        - `dfs`: Dictionary of all sheets for cross-sheet operations.
        - `pd`: pandas module.
        - `np`: numpy module.
        Returns serialized records suitable for UI data tables.
        """
        clean_code = code.strip()
        if clean_code.startswith("```"):
            clean_code = re.sub(r"^```(?:python|py)?\n?", "", clean_code)
            clean_code = re.sub(r"\n?```$", "", clean_code)
        clean_code = clean_code.strip()

        local_scope = {
            "df": self.primary_df.copy(),
            "dfs": {k: v.copy() for k, v in self.dfs.items()},
            "pd": pd,
            "np": np,
            "result_df": None
        }

        safe_builtins = {
            "abs": abs, "min": min, "max": max, "sum": sum, "len": len,
            "range": range, "round": round, "int": int, "float": float,
            "str": str, "bool": bool, "list": list, "dict": dict,
            "tuple": tuple, "set": set, "sorted": sorted, "zip": zip,
            "enumerate": enumerate, "True": True, "False": False, "None": None
        }

        exec(clean_code, {"__builtins__": safe_builtins}, local_scope)

        result = local_scope.get("result_df")
        if result is None:
            for var_name in reversed(list(local_scope.keys())):
                val = local_scope[var_name]
                if isinstance(val, (pd.DataFrame, pd.Series)) and var_name not in ["df"]:
                    result = val
                    break

        if result is None:
            raise ValueError("The executed Python code did not produce a 'result_df' DataFrame.")

        if isinstance(result, pd.Series):
            result = result.reset_index()

        records = result.to_dict(orient="records")
        return self._clean_records_for_json(records)

    def _clean_records_for_json(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sanitizes records to ensure NaN, Infinity, and Timestamps are JSON serializable."""
        cleaned = []
        for row in records:
            clean_row = {}
            for k, v in row.items():
                if isinstance(v, (float, int)) and (math.isnan(v) or math.isinf(v)):
                    clean_row[k] = None
                elif isinstance(v, (pd.Timestamp, np.datetime64)):
                    clean_row[k] = str(v)
                elif isinstance(v, np.generic):
                    clean_row[k] = v.item()
                else:
                    clean_row[k] = v
            cleaned.append(clean_row)
        return cleaned
