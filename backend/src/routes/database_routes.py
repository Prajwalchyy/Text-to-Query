from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Query
from controllers.database_controller import DatabaseController

router = APIRouter(tags=["Databases"])


@router.get("/databases")
def get_databases():
    """Returns all available databases (system default and user-uploaded)."""
    return DatabaseController.list_databases()


@router.post("/databases/upload")
async def upload_database(
    file: UploadFile = File(...),
    name: str = Form(...),
    type: Optional[str] = Form(default=None)
):
    """Uploads a custom SQL (.db) or NoSQL (.json) file and registers it with validation."""
    return DatabaseController.upload_database(file=file, name=name, dataset_type=type)


@router.delete("/databases/{db_id}")
def delete_database(db_id: str):
    """Deletes a custom user database."""
    return DatabaseController.delete_database(db_id=db_id)


@router.get("/tables")
def get_tables(db_id: str = Query(default="chinook")):
    """Returns live database tables and columns for the selected database."""
    return DatabaseController.get_tables_schema(db_id=db_id)
