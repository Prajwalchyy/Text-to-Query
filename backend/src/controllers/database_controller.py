import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from fastapi import HTTPException, UploadFile
from F01_db_engine import DatabaseEngine
from F06_pipeline import TextToSQLPipeline
from F09_nosql_engine import NoSQLEngine
from F12_nosql_pipeline import TextToNoSQLPipeline
from F08_database_registry import DatabaseRegistry, UPLOADS_DIR

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
    def upload_database(file: UploadFile, name: str, dataset_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Validates, saves, and registers a custom SQL (.db, .sqlite) or NoSQL (.json, .jsonl) file.
        """
        if name.strip() == "":
            raise HTTPException(status_code=400, detail="Name is required.")

        file_ext = Path(file.filename).suffix.lower()

        # Strict validation against requested dataset_type
        if dataset_type == "sql":
            if file_ext not in [".db", ".sqlite", ".sqlite3"]:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid file type for SQL Database: '{file.filename}'. Expected a .db, .sqlite, or .sqlite3 file."
                )
        elif dataset_type == "nosql":
            if file_ext not in [".json", ".jsonl"]:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid file type for NoSQL Database: '{file.filename}'. Expected a .json or .jsonl document file."
                )
        else:
            allowed_exts = (".db", ".sqlite", ".sqlite3", ".json", ".jsonl")
            if file.filename.lower().endswith(allowed_exts) == False:
                raise HTTPException(status_code=400, detail="Only .db, .sqlite, .json, or .jsonl files are allowed.")

        target_path = UPLOADS_DIR / file.filename

        # If a file with the same name exists, append counter suffix
        counter = 1
        while target_path.exists() == True:
            target_path = UPLOADS_DIR / f"{Path(file.filename).stem}_{counter}{Path(file.filename).suffix}"
            counter += 1

        try:
            with open(target_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Validate and register with custom name
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
                # NoSQL Multi-Collection Schema Introspection
                pipeline = DatabaseController.get_pipeline(db_id)
                schema_tables = pipeline.engine.get_all_tables_schema()
                nosql_relationships = [
                    {"from_table": "orders", "from_col": "customer_id", "to_table": "customers", "to_col": "_id"},
                    {"from_table": "orders", "from_col": "product_id", "to_table": "products", "to_col": "_id"},
                    {"from_table": "reviews", "from_col": "product_id", "to_table": "products", "to_col": "_id"},
                    {"from_table": "reviews", "from_col": "customer_id", "to_table": "customers", "to_col": "_id"}
                ]
                return {
                    "db_id": db_id,
                    "type": "nosql",
                    "tables": schema_tables,
                    "relationships": nosql_relationships
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
