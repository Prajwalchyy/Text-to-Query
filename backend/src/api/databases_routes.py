"""
Database & Dataset API Routes.
Enterprise Text-to-SQL API (v2.0)

Pure functional route handlers for dataset registration, multi-source file uploads
(SQL, NoSQL, CSV, Excel), merge operations, table/collection appends, and schema introspection.
"""

import json
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from src.engines.nosql_engine import (
    get_schema_fields,
    infer_nosql_relationships,
    load_nosql_collections,
    resolve_nosql_path,
)
from src.engines.spreadsheet_engine import (
    load_spreadsheet,
    resolve_spreadsheet_path,
)
from src.engines.sql_engine import (
    get_all_relationships,
    get_table_details,
    get_table_names,
    get_table_row_count,
    resolve_sqlite_path,
)
from src.storage.registry import (
    delete_database as storage_delete_database,
    get_database,
    get_upload_dir_for_type,
    list_databases as storage_list_databases,
    register_database,
)

router = APIRouter(tags=["Databases"])


# ==============================================================================
# Pure Functional Service Helpers
# ==============================================================================
def get_databases_data() -> Dict[str, Any]:
    """Retrieves all registered datasets from the registry."""
    try:
        return {"databases": storage_list_databases()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list data sources: {str(e)}")


def upload_dataset(
    files: Optional[List[UploadFile]] = None,
    file: Optional[UploadFile] = None,
    name: str = "",
    dataset_type: Optional[str] = None,
    mode: str = "full",
    group_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validates, saves, and registers a custom dataset file.
    Only single-file uploads are supported. Multi-sheet Excel files are supported naturally.
    """
    file_list: List[UploadFile] = []
    if files is not None and len(files) > 0:
        file_list.extend(files)
    if file is not None:
        file_list.append(file)

    if len(file_list) == 0:
        raise HTTPException(status_code=400, detail="A dataset file is required.")

    if len(file_list) > 1:
        raise HTTPException(
            status_code=400,
            detail="Multiple file upload has been removed. Please upload one dataset file at a time."
        )

    if mode == "merge":
        raise HTTPException(
            status_code=400,
            detail="Merge mode has been removed. Please upload a single dataset file."
        )

    single_file = file_list[0]
    fname = single_file.filename or "uploaded_data"
    if not name or not name.strip():
        derived = Path(fname).stem.replace("_", " ").replace("-", " ").title()
        name = derived

    file_ext = Path(fname).suffix.lower()
    effective_type = dataset_type

    if effective_type == "sql":
        if file_ext not in [".db", ".sqlite", ".sqlite3", ".s3db", ".sl3", ".sql"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type for SQL Database: '{fname}'. Expected .db, .sqlite, or .sql script file."
            )
    elif effective_type == "nosql":
        if file_ext not in [".json", ".jsonl", ".bson"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type for NoSQL Database: '{fname}'. Expected .json, .jsonl, or .bson file."
            )
    elif effective_type in ["csv", "excel", "spreadsheet"]:
        if file_ext not in [".csv", ".xlsx", ".xls", ".tsv", ".parquet"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type for Tabular Dataset: '{fname}'. Expected .csv, .xlsx, .xls, .tsv, or .parquet file."
            )
    else:
        if file_ext in [".csv", ".tsv", ".parquet"]:
            effective_type = "csv"
        elif file_ext in [".xlsx", ".xls"]:
            effective_type = "excel"
        elif file_ext in [".json", ".jsonl", ".bson"]:
            effective_type = "nosql"
        elif file_ext in [".db", ".sqlite", ".sqlite3", ".s3db", ".sl3", ".sql"]:
            effective_type = "sql"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: '{fname}'."
            )

    target_dir = get_upload_dir_for_type(effective_type, file_ext, upload_mode="single")
    target_path = target_dir / fname

    counter = 1
    while target_path.exists():
        target_path = target_dir / f"{Path(fname).stem}_{counter}{Path(fname).suffix}"
        counter += 1

    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(single_file.file, buffer)

        registered = register_database(
            name=name.strip(),
            file_path=target_path,
            filename=target_path.name,
            upload_mode="single"
        )
        return registered
    except ValueError as ve:
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")


def remove_dataset(db_id: str) -> Dict[str, Any]:
    """Deletes a custom user data source and removes it from disk and registry."""
    success = storage_delete_database(db_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete data source (either system default or not found)."
        )
    return {"success": True, "db_id": db_id}


def introspect_schema(db_id: str = "chinook") -> Dict[str, Any]:
    """
    Introspects and returns live tables/columns and relationships across SQL, NoSQL, CSV, or Excel.
    """
    try:
        db_info = get_database(db_id)
        if db_info is None:
            # Fallback to default Chinook if not registered by that exact ID
            if db_id.lower() in ("chinook", "default"):
                db_info = {"id": "chinook", "type": "sql", "path": str(resolve_sqlite_path("chinook"))}
            else:
                dbs = storage_list_databases()
                db_info = next((d for d in dbs if d["id"] == db_id), None)
                if db_info is None and dbs:
                    db_info = dbs[0]

        if db_info is None:
            raise HTTPException(status_code=404, detail=f"Data source '{db_id}' not found.")

        db_type = db_info.get("type", "sql")
        db_path = db_info.get("path", "")

        # ----------------------------------------------------------------------
        # SPREADSHEETS (CSV / Excel)
        # ----------------------------------------------------------------------
        if db_type in ["csv", "excel"]:
            dfs = load_spreadsheet(db_path, file_type=db_type)
            schema_tables: List[Dict[str, Any]] = []
            for sheet_name, df in dfs.items():
                col_details: List[Dict[str, Any]] = []
                col_strings: List[str] = []
                for i, col in enumerate(df.columns):
                    dtype = str(df[col].dtype)
                    is_pk = (i == 0 and ("id" in str(col).lower()))
                    badge = " 🔑 PK" if is_pk else ""
                    display_str = f"{col} ({dtype}){badge}"
                    col_strings.append(display_str)
                    col_details.append({
                        "name": str(col),
                        "type": dtype,
                        "is_pk": is_pk,
                        "is_fk": False,
                        "fk_to_table": None,
                        "fk_to_col": None,
                        "display": display_str
                    })
                schema_tables.append({
                    "name": sheet_name,
                    "cols": col_strings,
                    "columns": col_details,
                    "count": len(df)
                })
            return {
                "db_id": db_id,
                "type": db_type,
                "tables": schema_tables,
                "relationships": []
            }

        # ----------------------------------------------------------------------
        # NOSQL (MongoDB Document Datasets)
        # ----------------------------------------------------------------------
        elif db_type == "nosql":
            collections = load_nosql_collections(db_path)
            relationships = infer_nosql_relationships(collections)

            enriched_tables: List[Dict[str, Any]] = []
            for c_name, docs in collections.items():
                fields = get_schema_fields(docs)
                col_details = []
                col_strings = []

                fk_col_map = {
                    r.get("from_col"): r
                    for r in relationships
                    if r.get("from_table") == c_name
                }

                pk_name = None
                field_paths = [f["path"] for f in fields]
                if "_id" in field_paths:
                    pk_name = "_id"
                else:
                    tokens = c_name.lower().split("_")
                    for f in fields:
                        fp = f["path"]
                        if fp in fk_col_map:
                            continue
                        fp_lower = fp.lower()
                        if fp_lower.endswith("_id"):
                            stem = fp_lower[:-3]
                            if stem == c_name.lower() or stem == tokens[-1] or stem in (c_name.lower().rstrip("s"), tokens[-1].rstrip("s")):
                                pk_name = fp
                                break
                    if pk_name is None and "id" in field_paths and "id" not in fk_col_map:
                        pk_name = "id"

                for f in fields:
                    path = f["path"]
                    dtype = f["type"]
                    is_pk = (path == pk_name)
                    fk_match = fk_col_map.get(path)
                    fk_to_table = fk_match.get("to_table") if fk_match is not None else None
                    fk_to_col = fk_match.get("to_col") if fk_match is not None else None

                    badge = ""
                    if is_pk:
                        badge = " 🔑 PK"
                    elif fk_to_table is not None:
                        badge = f" 🔗 {fk_to_table}"

                    display_str = f"{path} ({dtype}){badge}"
                    col_strings.append(display_str)
                    col_details.append({
                        "name": path,
                        "type": dtype,
                        "is_pk": is_pk,
                        "is_fk": fk_to_table is not None,
                        "fk_to_table": fk_to_table,
                        "fk_to_col": fk_to_col,
                        "display": display_str
                    })

                enriched_tables.append({
                    "name": c_name,
                    "cols": col_strings,
                    "columns": col_details,
                    "count": len(docs)
                })

            return {
                "db_id": db_id,
                "type": "nosql",
                "tables": enriched_tables,
                "relationships": relationships
            }

        # ----------------------------------------------------------------------
        # SQL (SQLite Databases)
        # ----------------------------------------------------------------------
        else:
            resolved_path = resolve_sqlite_path(db_path)
            table_names = get_table_names(resolved_path)
            relationships = get_all_relationships(resolved_path)

            schema_data: List[Dict[str, Any]] = []
            for table in table_names:
                cols, pks, fks = get_table_details(resolved_path, table)
                col_details = []
                col_strings = []
                for c in cols:
                    c_name = c["name"]
                    c_type = str(c["type"])
                    is_pk = c_name in pks
                    fk_match = next((fk for fk in fks if c_name in fk.get("constrained_columns", [])), None)
                    fk_to_table = fk_match.get("referred_table") if fk_match is not None else None
                    fk_to_col = fk_match.get("referred_columns", [None])[0] if fk_match is not None else None

                    badge = ""
                    if is_pk:
                        badge = " 🔑 PK"
                    elif fk_to_table is not None:
                        badge = f" 🔗 {fk_to_table}"

                    display_str = f"{c_name} ({c_type}){badge}"
                    col_strings.append(display_str)
                    col_details.append({
                        "name": c_name,
                        "type": c_type,
                        "is_pk": is_pk,
                        "is_fk": fk_to_table is not None,
                        "fk_to_table": fk_to_table,
                        "fk_to_col": fk_to_col,
                        "display": display_str
                    })

                schema_data.append({
                    "name": table,
                    "cols": col_strings,
                    "columns": col_details,
                    "count": get_table_row_count(resolved_path, table)
                })

            return {
                "db_id": db_id,
                "type": "sql",
                "tables": schema_data,
                "relationships": relationships
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schema introspection failed: {str(e)}")


# ==============================================================================
# FastAPI Route Handlers
# ==============================================================================
@router.get("/databases")
def get_databases():
    """Returns all available databases (system default and user-uploaded)."""
    return get_databases_data()


@router.post("/databases/upload")
async def upload_database(
    files: Optional[List[UploadFile]] = File(default=None),
    file: Optional[UploadFile] = File(default=None),
    name: Optional[str] = Form(default=""),
    type: Optional[str] = Form(default=None),
    mode: str = Form(default="full"),
    group_name: Optional[str] = Form(default=None),
):
    """
    Uploads a custom dataset file (.db/.sqlite/.sql, .json/.bson, .csv, .xlsx).
    """
    return upload_dataset(
        files=files,
        file=file,
        name=name or "",
        dataset_type=type,
        mode=mode,
        group_name=group_name
    )


@router.delete("/databases/{db_id}")
def delete_database(db_id: str):
    """Deletes a custom user database."""
    return remove_dataset(db_id=db_id)


@router.get("/tables")
def get_tables(db_id: str = Query(default="chinook")):
    """Returns live database tables and columns for the selected database."""
    return introspect_schema(db_id=db_id)


# ==============================================================================
# Backward-Compatible Controller Adapter
# ==============================================================================
class DatabaseController:
    """Thin static adapter maintaining backward compatibility with legacy callers."""
    list_databases = staticmethod(get_databases_data)
    upload_database = staticmethod(upload_dataset)
    delete_database = staticmethod(remove_dataset)
    get_tables_schema = staticmethod(introspect_schema)

