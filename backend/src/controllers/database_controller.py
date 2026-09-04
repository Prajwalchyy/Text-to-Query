import json
import shutil
import sqlite3
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from fastapi import HTTPException, UploadFile
from F01_db_engine import DatabaseEngine
from F06_pipeline import TextToSQLPipeline
from F09_nosql_engine import NoSQLEngine
from F12_nosql_pipeline import TextToNoSQLPipeline
from F08_database_registry import (
    DatabaseRegistry, 
    TableConflictError,
    CollectionConflictError,
    get_upload_dir_for_type, 
    RELATIONAL_DIR, 
    NOSQL_DIR, 
    CSV_DIR, 
    EXCEL_DIR
)

# Initialize database registry
db_registry = DatabaseRegistry()

# Pipeline Cache for fast switching between multiple SQL/NoSQL sources
_pipeline_cache: Dict[str, Union[TextToSQLPipeline, TextToNoSQLPipeline]] = {}


class DatabaseController:
    """
    Controller handling multi-source (SQL & NoSQL) file uploads, listing, deletion,
    schema introspection, and dynamic pipeline resolution.
    """

    @staticmethod
    def get_pipeline(db_id: str = "chinook") -> Union[TextToSQLPipeline, TextToNoSQLPipeline]:
        """
        Dynamically resolves and caches a Pipeline instance (SQL or NoSQL) for a given database ID.
        """
        db_info = db_registry.get_database(db_id)
        if db_info == None:
            dbs = db_registry.list_databases()
            db_info = dbs[0] if len(dbs) > 0 else None

        if db_info == None:
            raise HTTPException(status_code=404, detail=f"Data source '{db_id}' not found.")

        db_path = Path(db_info["path"]).resolve()
        cache_key = f"{db_info.get('type', 'sql')}:{str(db_path)}"

        if cache_key not in _pipeline_cache:
            if db_info.get("type") == "nosql":
                nosql_engine = NoSQLEngine(file_path=str(db_path))
                _pipeline_cache[cache_key] = TextToNoSQLPipeline(engine=nosql_engine)
            else:
                sql_engine = DatabaseEngine(uri=f"sqlite:///{db_path.as_posix()}")
                _pipeline_cache[cache_key] = TextToSQLPipeline(db_engine=sql_engine)

        return _pipeline_cache[cache_key]

    @staticmethod
    def list_databases() -> Dict[str, Any]:
        """Returns all registered data sources (SQL and NoSQL)."""
        try:
            return {"databases": db_registry.list_databases()}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to list data sources: {str(e)}")

    @staticmethod
    def upload_database(
        file: Optional[UploadFile] = None,
        files: Optional[List[UploadFile]] = None,
        name: str = "",
        dataset_type: Optional[str] = None,
        mode: str = "full"
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Validates, saves, and registers custom datasets.
        Supports:
        1. Full Database Mode (mode='full'): 1 file or bulk multi-file import registering independent databases.
        2. Merge Mode (mode='merge'): Merging multiple SQL table scripts (.sql) into 1 SQLite DB,
           OR merging multiple NoSQL collection files (.json, .bson) into 1 multi-collection NoSQL store.
        """
        file_list = []
        if files != None and len(files) > 0:
            file_list.extend(files)
        if file != None:
            file_list.append(file)

        if len(file_list) == 0:
            raise HTTPException(status_code=400, detail="At least one file is required.")

        # =========================================================================
        # BRANCH A: MERGE MODE (Multiple Tables -> 1 SQL DB  OR  Multiple Collections -> 1 NoSQL DB)
        # =========================================================================
        if mode == "merge":
            if name.strip() == "":
                raise HTTPException(status_code=400, detail="Custom Display Name is required when merging into a combined database.")

            # A1: SQL MERGE (Multiple .sql scripts -> 1 SQLite DB)
            if dataset_type == "sql":
                for f in file_list:
                    ext = Path(f.filename).suffix.lower()
                    if ext != ".sql":
                        raise HTTPException(
                            status_code=400,
                            detail=f"In Multiple Tables (Merge) mode, SQL only accepts .sql table scripts. Received '{f.filename}'."
                        )

                target_dir = get_upload_dir_for_type("sql", ".db")
                clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', name.strip().lower())
                target_db_path = target_dir / f"{clean_name}.db"

                counter = 1
                while target_db_path.exists() == True:
                    target_db_path = target_dir / f"{clean_name}_{counter}.db"
                    counter += 1

                conn = None
                try:
                    conn = sqlite3.connect(str(target_db_path.resolve()))
                    for f in file_list:
                        content = f.file.read().decode("utf-8", errors="ignore")
                        if content.strip() != "":
                            conn.executescript(content)
                    conn.commit()
                    conn.close()
                    conn = None

                    registered = db_registry.register_database(
                        name=name,
                        file_path=target_db_path,
                        filename=target_db_path.name
                    )
                    return registered
                except Exception as e:
                    if conn != None:
                        try:
                            conn.close()
                        except Exception:
                            pass
                    if target_db_path.exists() == True:
                        target_db_path.unlink()
                    raise HTTPException(status_code=400, detail=f"Failed to merge table scripts into database: {str(e)}")

            # A2: NoSQL MERGE (Multiple .json / .bson collection files -> 1 Multi-Collection JSON store)
            elif dataset_type == "nosql":
                for f in file_list:
                    ext = Path(f.filename).suffix.lower()
                    if ext not in [".json", ".jsonl", ".bson"]:
                        raise HTTPException(
                            status_code=400,
                            detail=f"In Multiple Collections (Merge) mode, NoSQL only accepts .json, .jsonl, or .bson files. Received '{f.filename}'."
                        )

                from F09_nosql_engine import NoSQLEngine
                target_dir = get_upload_dir_for_type("nosql", ".json")
                clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', name.strip().lower())
                target_json_path = target_dir / f"{clean_name}.json"

                counter = 1
                while target_json_path.exists() == True:
                    target_json_path = target_dir / f"{clean_name}_{counter}.json"
                    counter += 1

                try:
                    file_tuples = [(f.filename, f.file.read()) for f in file_list]
                    dataset = NoSQLEngine.compile_collections_to_dataset(file_tuples)
                    target_json_path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")

                    registered = db_registry.register_database(
                        name=name,
                        file_path=target_json_path,
                        filename=target_json_path.name
                    )
                    return registered
                except Exception as e:
                    if target_json_path.exists() == True:
                        target_json_path.unlink()
                    raise HTTPException(status_code=400, detail=f"Failed to merge collection files into NoSQL database: {str(e)}")
            else:
                raise HTTPException(status_code=400, detail="Merge mode only supports SQL or NoSQL datasets.")

        # =========================================================================
        # BRANCH B: FULL DATABASE MODE (Single Upload OR Multi-File Bulk Import)
        # =========================================================================
        # B1: Single Full Database
        if len(file_list) == 1:
            single_file = file_list[0]
            if name.strip() == "":
                clean_name = Path(single_file.filename).stem.replace("_", " ").replace("-", " ").title()
                name = clean_name

            file_ext = Path(single_file.filename).suffix.lower()
            if dataset_type == "sql":
                if file_ext not in [".db", ".sqlite", ".sqlite3", ".s3db", ".sl3", ".sql"]:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid file type for SQL Database: '{single_file.filename}'. Expected .db, .sqlite, or .sql script file."
                    )
            elif dataset_type == "nosql":
                if file_ext not in [".json", ".jsonl", ".bson"]:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid file type for NoSQL Database: '{single_file.filename}'. Expected .json, .jsonl, or .bson document file."
                    )

            target_dir = get_upload_dir_for_type(dataset_type, file_ext)
            target_path = target_dir / single_file.filename

            counter = 1
            while target_path.exists() == True:
                target_path = target_dir / f"{Path(single_file.filename).stem}_{counter}{Path(single_file.filename).suffix}"
                counter += 1

            try:
                with open(target_path, "wb") as buffer:
                    shutil.copyfileobj(single_file.file, buffer)

                registered = db_registry.register_database(
                    name=name,
                    file_path=target_path,
                    filename=target_path.name
                )
                return registered
            except ValueError as ve:
                if target_path.exists() == True:
                    target_path.unlink()
                raise HTTPException(status_code=400, detail=str(ve))
            except Exception as e:
                if target_path.exists() == True:
                    target_path.unlink()
                raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

        # B2: Multi-File Bulk Import (Multiple Full Databases)
        bulk_registered = []
        for f in file_list:
            file_ext = Path(f.filename).suffix.lower()
            derived_name = Path(f.filename).stem.replace("_", " ").replace("-", " ").title()

            if dataset_type == "sql" and file_ext not in [".db", ".sqlite", ".sqlite3", ".s3db", ".sl3", ".sql"]:
                continue
            if dataset_type == "nosql" and file_ext not in [".json", ".jsonl", ".bson"]:
                continue

            target_dir = get_upload_dir_for_type(dataset_type, file_ext)
            target_path = target_dir / f.filename

            counter = 1
            while target_path.exists() == True:
                target_path = target_dir / f"{Path(f.filename).stem}_{counter}{Path(f.filename).suffix}"
                counter += 1

            try:
                with open(target_path, "wb") as buffer:
                    shutil.copyfileobj(f.file, buffer)

                reg = db_registry.register_database(
                    name=derived_name,
                    file_path=target_path,
                    filename=target_path.name
                )
                bulk_registered.append(reg)
            except Exception as e:
                if target_path.exists() == True:
                    target_path.unlink()

        if len(bulk_registered) == 0:
            raise HTTPException(status_code=400, detail="None of the uploaded files could be successfully registered as databases.")

        return {
            "success": True,
            "databases": bulk_registered,
            "message": f"{len(bulk_registered)} databases successfully imported!"
        }

    @staticmethod
    def append_table_to_database(db_id: str, file: UploadFile, overwrite: bool = False) -> Dict[str, Any]:
        """
        Executes an uploaded .sql table script into an existing custom SQL database.
        Detects collisions and supports overwrite flag.
        """
        ext = Path(file.filename).suffix.lower()
        if ext != ".sql":
            raise HTTPException(status_code=400, detail=f"Only .sql table scripts can be appended. Received '{file.filename}'.")

        try:
            sql_content = file.file.read().decode("utf-8", errors="ignore")
            if sql_content.strip() == "":
                raise HTTPException(status_code=400, detail="Uploaded SQL script is empty.")

            updated = db_registry.append_table_to_database(db_id=db_id, sql_script=sql_content, overwrite=overwrite)
            return {
                "success": True,
                "database": updated,
                "message": f"Table script '{file.filename}' successfully added! Database now has {updated['table_count']} tables."
            }
        except TableConflictError as tce:
            raise HTTPException(
                status_code=409, 
                detail={
                    "conflict": True,
                    "conflicts": tce.conflicts,
                    "table_name": tce.conflicts[0] if len(tce.conflicts) > 0 else "Table",
                    "message": f"Table '{tce.conflicts[0]}' already exists in this database. Would you like to overwrite and replace it?"
                }
            )
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to append table: {str(e)}")

    @staticmethod
    def append_collection_to_database(db_id: str, file: UploadFile, overwrite: bool = False) -> Dict[str, Any]:
        """
        Appends an uploaded collection file (.json, .jsonl, .bson) into an existing custom NoSQL database.
        Detects collisions and supports overwrite flag.
        """
        ext = Path(file.filename).suffix.lower()
        if ext not in [".json", ".jsonl", ".bson"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Only .json, .jsonl, or .bson collection files can be appended. Received '{file.filename}'."
            )

        try:
            content = file.file.read()
            if len(content) == 0:
                raise HTTPException(status_code=400, detail="Uploaded collection file is empty.")

            from F09_nosql_engine import NoSQLEngine
            col_name, docs = NoSQLEngine.parse_collection_file(file.filename, content)
            if len(docs) == 0:
                raise HTTPException(status_code=400, detail=f"No valid documents found in '{file.filename}'.")

            updated = db_registry.append_collection_to_database(
                db_id=db_id,
                collection_name=col_name,
                documents=docs,
                overwrite=overwrite
            )
            return {
                "success": True,
                "database": updated,
                "message": f"Collection '{col_name}' successfully added! Database now has {updated['doc_count']} documents."
            }
        except CollectionConflictError as cce:
            raise HTTPException(
                status_code=409,
                detail={
                    "conflict": True,
                    "conflicts": cce.conflicts,
                    "collection_name": cce.conflicts[0] if len(cce.conflicts) > 0 else "Collection",
                    "message": f"Collection '{cce.conflicts[0]}' already exists in this database. Would you like to overwrite and replace it?"
                }
            )
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to append collection: {str(e)}")

    @staticmethod
    def delete_database(db_id: str) -> Dict[str, Any]:
        """Deletes a custom user data source and unregisters it."""
        success = db_registry.delete_database(db_id)
        if success == False:
            raise HTTPException(status_code=400, detail="Cannot delete data source (either system default or not found).")
        return {"success": True, "db_id": db_id}

    @staticmethod
    def get_tables_schema(db_id: str = "chinook") -> Dict[str, Any]:
        """
        Introspects and returns live tables/columns for SQL, or nested fields for NoSQL.
        """
        try:
            db_info = db_registry.get_database(db_id)
            if db_info != None and db_info.get("type") == "nosql":
                # NoSQL Multi-Collection Schema & Relationship Introspection
                pipeline = DatabaseController.get_pipeline(db_id)
                relationships = pipeline.engine.get_all_relationships()
                schema_tables = pipeline.engine.get_all_tables_schema()

                enriched_tables = []
                for tbl in schema_tables:
                    c_name = tbl["name"]
                    fields = pipeline.engine.get_schema_fields(c_name)
                    col_details = []
                    col_strings = []

                    # Determine foreign keys originating from this collection
                    fk_col_map = {
                        r.get("from_col"): r
                        for r in relationships
                        if r.get("from_table") == c_name
                    }

                    # Find candidate PK for this collection (avoiding columns that point elsewhere as FK)
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
                        "count": tbl.get("count", 0)
                    })

                return {
                    "db_id": db_id,
                    "type": "nosql",
                    "tables": enriched_tables,
                    "relationships": relationships
                }
            else:
                # SQL Schema & Foreign Key Introspection
                pipeline = DatabaseController.get_pipeline(db_id)
                table_names = pipeline.db_engine.get_table_names()
                relationships = pipeline.db_engine.get_all_relationships()
                schema_data = []
                for table in table_names:
                    cols, pks, fks = pipeline.db_engine.get_table_details(table)
                    col_details = []
                    col_strings = []
                    for c in cols:
                        c_name = c["name"]
                        c_type = str(c["type"])
                        is_pk = c_name in pks
                        fk_match = next((fk for fk in fks if c_name in fk.get("constrained_columns", [])), None)
                        fk_to_table = fk_match.get("referred_table") if fk_match != None else None
                        fk_to_col = fk_match.get("referred_columns", [None])[0] if fk_match != None else None

                        badge = ""
                        if is_pk == True:
                            badge = " 🔑 PK"
                        elif fk_to_table != None:
                            badge = f" 🔗 {fk_to_table}"

                        display_str = f"{c_name} ({c_type}){badge}"
                        col_strings.append(display_str)
                        col_details.append({
                            "name": c_name,
                            "type": c_type,
                            "is_pk": is_pk,
                            "is_fk": fk_to_table != None,
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
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Schema introspection failed: {str(e)}")
