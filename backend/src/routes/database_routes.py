from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException
from controllers.database_controller import DatabaseController

router = APIRouter(tags=["Databases"])


@router.get("/databases")
def get_databases():
    """Returns all available databases (system default and user-uploaded)."""
    return DatabaseController.list_databases()


@router.post("/databases/upload")
async def upload_database(
    files: Optional[List[UploadFile]] = File(default=None),
    file: Optional[UploadFile] = File(default=None),
    name: Optional[str] = Form(default=""),
    type: Optional[str] = Form(default=None),
    mode: str = Form(default="full"),
    group_name: Optional[str] = Form(default=None)
):
    """
    Uploads custom dataset(s).
    Supports:
    - Full Database mode (mode='full'): 1 file or multi-file bulk import.
    - Merge mode (mode='merge'): Merges multiple SQL tables into 1 SQLite DB,
      or multiple NoSQL collections into 1 NoSQL store.
    """
    file_list = []
    if files != None and len(files) > 0:
        file_list.extend(files)
    if file != None:
        file_list.append(file)

    if len(file_list) == 0:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    return DatabaseController.upload_database(
        files=file_list, 
        name=name or "", 
        dataset_type=type, 
        mode=mode,
        group_name=group_name
    )


@router.post("/databases/{db_id}/append-table")
async def append_table(
    db_id: str,
    file: UploadFile = File(...),
    overwrite: bool = Form(default=False)
):
    """Appends an individual .sql table script to an existing custom SQL database."""
    return DatabaseController.append_table_to_database(db_id=db_id, file=file, overwrite=overwrite)


@router.post("/databases/{db_id}/append-collection")
async def append_collection(
    db_id: str,
    file: UploadFile = File(...),
    overwrite: bool = Form(default=False)
):
    """Appends an individual .json/.jsonl/.bson collection file to an existing custom NoSQL database."""
    return DatabaseController.append_collection_to_database(db_id=db_id, file=file, overwrite=overwrite)


@router.delete("/databases/{db_id}")
def delete_database(db_id: str):
    """Deletes a custom user database."""
    return DatabaseController.delete_database(db_id=db_id)


@router.get("/tables")
def get_tables(db_id: str = Query(default="chinook")):
    """Returns live database tables and columns for the selected database."""
    return DatabaseController.get_tables_schema(db_id=db_id)
