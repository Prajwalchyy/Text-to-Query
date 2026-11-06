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
    compile_collections_to_dataset,
    get_schema_fields,
    infer_nosql_relationships,
    load_nosql_collections,
    parse_collection_file,
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
    resolve_sqlite_path,
)
from src.storage.registry import (
    CollectionConflictError,
    TableConflictError,
    append_collection_to_database,
    append_table_to_database,
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
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Validates, saves, and registers custom datasets.
    Supports:
    1. Merge Mode (mode='merge'): Merging multiple SQL tables into 1 SQLite DB,
       or multiple NoSQL collections into 1 NoSQL store.
    2. Full Database Mode (mode='full'): 1 file (single/) or multi-file bulk import (multiple/<group>/).
    """
    file_list: List[UploadFile] = []
    if files is not None and len(files) > 0:
        file_list.extend(files)
    if file is not None:
        file_list.append(file)

    if len(file_list) == 0:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    # --------------------------------------------------------------------------
    # BRANCH A: MERGE MODE (Multiple Tables -> 1 SQL DB | Multiple Collections -> 1 NoSQL DB)
    # --------------------------------------------------------------------------
    if mode == "merge":
        if not name or not name.strip():
            raise HTTPException(
                status_code=400,
                detail="Custom Display Name is required when merging into a combined database."
            )

        # A1: SQL Merge (Multiple .sql scripts -> 1 SQLite DB)
        if dataset_type == "sql":
            for f in file_list:
                ext = Path(f.filename or "").suffix.lower()
                if ext != ".sql":
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "In Multiple Tables (Merge) mode, SQL only accepts .sql table scripts. "
                            f"Received '{f.filename}'."
                        )
                    )

            target_dir = get_upload_dir_for_type("sql", ".db", upload_mode="single")
            clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', name.strip().lower())
            target_db_path = target_dir / f"{clean_name}.db"

            counter = 1
            while target_db_path.exists():
                target_db_path = target_dir / f"{clean_name}_{counter}.db"
                counter += 1

            conn: Optional[sqlite3.Connection] = None
            try:
                conn = sqlite3.connect(str(target_db_path.resolve()))
                for f in file_list:
                    content = f.file.read().decode("utf-8", errors="ignore")
                    if content.strip():
                        conn.executescript(content)
                conn.commit()
                conn.close()
                conn = None

                registered = register_database(
                    name=name.strip(),
                    file_path=target_db_path,
                    filename=target_db_path.name,
                    upload_mode="single"
                )
                return registered
            except Exception as e:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
                if target_db_path.exists():
                    target_db_path.unlink()
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to merge table scripts into database: {str(e)}"
                )

        # A2: NoSQL Merge (Multiple .json / .bson collection files -> 1 Multi-Collection JSON store)
        elif dataset_type == "nosql":
            for f in file_list:
                ext = Path(f.filename or "").suffix.lower()
                if ext not in [".json", ".jsonl", ".bson"]:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "In Multiple Collections (Merge) mode, NoSQL only accepts .json, .jsonl, "
                            f"or .bson files. Received '{f.filename}'."
                        )
                    )

            target_dir = get_upload_dir_for_type("nosql", ".json", upload_mode="single")
            clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', name.strip().lower())
            target_json_path = target_dir / f"{clean_name}.json"

            counter = 1
            while target_json_path.exists():
                target_json_path = target_dir / f"{clean_name}_{counter}.json"
                counter += 1

            try:
                file_tuples = [(f.filename or "collection", f.file.read()) for f in file_list]
                dataset = compile_collections_to_dataset(file_tuples)
                target_json_path.write_text(
                    json.dumps(dataset, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )

                registered = register_database(
                    name=name.strip(),
                    file_path=target_json_path,
                    filename=target_json_path.name,
                    upload_mode="single"
                )
                return registered
            except Exception as e:
                if target_json_path.exists():
                    target_json_path.unlink()
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to merge collection files into NoSQL database: {str(e)}"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Merge mode only supports SQL or NoSQL datasets."
            )

    # --------------------------------------------------------------------------
    # BRANCH B: FULL DATABASE MODE (Single Upload OR Multi-File Bulk Import)
    # --------------------------------------------------------------------------
    # B1: Single Full Dataset (single/ folder)
    if len(file_list) == 1:
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
            if file_ext not in [".csv", ".xlsx", ".xls"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type for Spreadsheet: '{fname}'. Expected .csv, .xlsx, or .xls file."
                )
        else:
            if file_ext == ".csv":
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

    # B2: Multi-File Bulk/Group Import (multiple/<group_folder>/)
    effective_group_name = (group_name or name or "Batch Upload").strip()
    timestamp = int(datetime.now(timezone.utc).timestamp())
    clean_group_slug = re.sub(r'[^a-zA-Z0-9_]', '_', effective_group_name.lower())
    group_id = f"group_{clean_group_slug}_{timestamp}"
    group_folder = f"{clean_group_slug}_{timestamp}"

    bulk_registered: List[Dict[str, Any]] = []
    for f in file_list:
        fname = f.filename or "bulk_file"
        file_ext = Path(fname).suffix.lower()
        derived_name = Path(fname).stem.replace("_", " ").replace("-", " ").title()

        effective_type = dataset_type
        if effective_type == "sql" and file_ext not in [".db", ".sqlite", ".sqlite3", ".s3db", ".sl3", ".sql"]:
            continue
        if effective_type == "nosql" and file_ext not in [".json", ".jsonl", ".bson"]:
            continue
        if effective_type in ["csv", "excel", "spreadsheet"] and file_ext not in [".csv", ".xlsx", ".xls"]:
            continue
        if not effective_type:
            if file_ext == ".csv":
                effective_type = "csv"
            elif file_ext in [".xlsx", ".xls"]:
                effective_type = "excel"
            elif file_ext in [".json", ".jsonl", ".bson"]:
                effective_type = "nosql"
            elif file_ext in [".db", ".sqlite", ".sqlite3", ".s3db", ".sl3", ".sql"]:
                effective_type = "sql"
            else:
                continue

        target_dir = get_upload_dir_for_type(
            effective_type,
            file_ext,
            upload_mode="multiple",
            group_folder=group_folder
        )
        target_path = target_dir / fname

        counter = 1
        while target_path.exists():
            target_path = target_dir / f"{Path(fname).stem}_{counter}{Path(fname).suffix}"
            counter += 1

        try:
            with open(target_path, "wb") as buffer:
                shutil.copyfileobj(f.file, buffer)

            reg = register_database(
                name=derived_name,
                file_path=target_path,
                filename=target_path.name,
                upload_mode="multiple",
                group_name=effective_group_name,
                group_id=group_id
            )
            bulk_registered.append(reg)
        except Exception:
            if target_path.exists():
                target_path.unlink()

    if len(bulk_registered) == 0:
        raise HTTPException(
            status_code=400,
            detail="None of the uploaded files could be successfully registered as databases."
        )

    return {
        "success": True,
        "databases": bulk_registered,
        "message": f"{len(bulk_registered)} data sources successfully imported into group '{effective_group_name}'!"
    }


def append_table_script(db_id: str, file: UploadFile, overwrite: bool = False) -> Dict[str, Any]:
    """Appends an individual .sql table script to an existing custom SQL database."""
    fname = file.filename or ""
    ext = Path(fname).suffix.lower()
    if ext != ".sql":
        raise HTTPException(
            status_code=400,
            detail=f"Only .sql table scripts can be appended. Received '{fname}'."
        )

    try:
        sql_content = file.file.read().decode("utf-8", errors="ignore")
        if not sql_content.strip():
            raise HTTPException(status_code=400, detail="Uploaded SQL script is empty.")

        updated = append_table_to_database(db_id=db_id, sql_script=sql_content, overwrite=overwrite)
        return {
            "success": True,
            "database": updated,
            "message": f"Table script '{fname}' successfully added! Database now has {updated.get('table_count', 0)} tables."
        }
    except TableConflictError as tce:
        conflicts = tce.conflicts
        target_name = conflicts[0] if conflicts else "Table"
        raise HTTPException(
            status_code=409,
            detail={
                "conflict": True,
                "conflicts": conflicts,
                "table_name": target_name,
                "message": f"Table '{target_name}' already exists in this database. Would you like to overwrite and replace it?"
            }
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to append table: {str(e)}")


def append_collection_docs(db_id: str, file: UploadFile, overwrite: bool = False) -> Dict[str, Any]:
    """Appends an individual .json/.jsonl/.bson collection file to an existing custom NoSQL database."""
    fname = file.filename or ""
    ext = Path(fname).suffix.lower()
    if ext not in [".json", ".jsonl", ".bson"]:
        raise HTTPException(
            status_code=400,
            detail=f"Only .json, .jsonl, or .bson collection files can be appended. Received '{fname}'."
        )

    try:
        content = file.file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded collection file is empty.")

        col_name, docs = parse_collection_file(fname, content)
        if len(docs) == 0:
            raise HTTPException(status_code=400, detail=f"No valid documents found in '{fname}'.")

        updated = append_collection_to_database(
            db_id=db_id,
            collection_name=col_name,
            documents=docs,
            overwrite=overwrite
        )
        return {
            "success": True,
            "database": updated,
            "message": f"Collection '{col_name}' successfully added! Database now has {updated.get('doc_count', 0)} documents."
        }
    except CollectionConflictError as cce:
        conflicts = cce.conflicts
        target_name = conflicts[0] if conflicts else "Collection"
        raise HTTPException(
            status_code=409,
            detail={
                "conflict": True,
                "conflicts": conflicts,
                "collection_name": target_name,
                "message": f"Collection '{target_name}' already exists in this database. Would you like to overwrite and replace it?"
            }
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to append collection: {str(e)}")


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
                    "columns": col_details
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
    Uploads custom dataset(s).
    Supports:
    - Full Database mode (mode='full'): 1 file or multi-file bulk import.
    - Merge mode (mode='merge'): Merges multiple SQL tables into 1 SQLite DB,
      or multiple NoSQL collections into 1 NoSQL store.
    """
    return upload_dataset(
        files=files,
        file=file,
        name=name or "",
        dataset_type=type,
        mode=mode,
        group_name=group_name
    )


@router.post("/databases/{db_id}/append-table")
async def append_table(
    db_id: str,
    file: UploadFile = File(...),
    overwrite: bool = Form(default=False),
):
    """Appends an individual .sql table script to an existing custom SQL database."""
    return append_table_script(db_id=db_id, file=file, overwrite=overwrite)


@router.post("/databases/{db_id}/append-collection")
async def append_collection(
    db_id: str,
    file: UploadFile = File(...),
    overwrite: bool = Form(default=False),
):
    """Appends an individual .json/.jsonl/.bson collection file to an existing custom NoSQL database."""
    return append_collection_docs(db_id=db_id, file=file, overwrite=overwrite)


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
    """Thin static adapter maintaining 100% backward compatibility with legacy callers."""
    list_databases = staticmethod(get_databases_data)
    upload_database = staticmethod(upload_dataset)
    append_table_to_database = staticmethod(append_table_script)
    append_collection_to_database = staticmethod(append_collection_docs)
    delete_database = staticmethod(remove_dataset)
    get_tables_schema = staticmethod(introspect_schema)

