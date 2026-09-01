import sys
import shutil
from pathlib import Path
from typing import Optional, List, Dict
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add backend/src to Python path so pipeline modules are found
SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from F01_db_engine import DatabaseEngine
from F06_pipeline import TextToSQLPipeline
from F07_chat_storage import ChatStorage
from F08_database_registry import DatabaseRegistry, UPLOADS_DIR

# ==============================================================================
# FastAPI Application & CORS Configuration
# ==============================================================================
app = FastAPI(
    title="Enterprise Text-to-SQL API",
    description="Multi-database Text-to-SQL API with custom database uploading and switching",
    version="1.1.0",
)

# Allow React frontend to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize storage and registry
chat_storage = ChatStorage()
db_registry = DatabaseRegistry()

# Pipeline Cache for instant switching between multiple databases
_pipeline_cache: Dict[str, TextToSQLPipeline] = {}


def get_pipeline_for_db(db_id: str = "chinook") -> TextToSQLPipeline:
    """
    Dynamically returns a cached TextToSQLPipeline instance for the selected database.
    """
    db_info = db_registry.get_database(db_id)
    if not db_info:
        # Fallback to default
        dbs = db_registry.list_databases()
        db_info = dbs[0] if dbs else None

    if not db_info:
        raise HTTPException(status_code=404, detail=f"Database '{db_id}' not found.")

    db_path = Path(db_info["path"]).resolve()
    cache_key = str(db_path)

    if cache_key not in _pipeline_cache:
        engine = DatabaseEngine(uri=f"sqlite:///{db_path.as_posix()}")
        _pipeline_cache[cache_key] = TextToSQLPipeline(db_engine=engine)

    return _pipeline_cache[cache_key]


# ==============================================================================
# Request Models
# ==============================================================================
class QueryRequest(BaseModel):
    question: str
    db_id: Optional[str] = "chinook"

class CreateChatRequest(BaseModel):
    id: str
    title: Optional[str] = "New Conversation"

class UpdateChatRequest(BaseModel):
    title: str


# ==============================================================================
# Database Management & Upload Endpoints
# ==============================================================================
@app.get("/api/databases")
def get_databases():
    """Returns all available databases (system default and user-uploaded)."""
    try:
        return {"databases": db_registry.list_databases()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list databases: {str(e)}")


@app.post("/api/databases/upload")
async def upload_database(
    file: UploadFile = File(...),
    name: str = Form(...)
):
    """
    Uploads a custom SQLite database file and registers it with a user-specified name.
    """
    if not name.strip():
        raise HTTPException(status_code=400, detail="Database name is required.")

    if not file.filename.endswith((".db", ".sqlite", ".sqlite3")):
        raise HTTPException(status_code=400, detail="Only .db, .sqlite, or .sqlite3 files are allowed.")

    # Save uploaded file
    safe_filename = f"{int(Path(file.filename).stem[:24]) if Path(file.filename).stem[:24].isdigit() else Path(file.filename).stem[:24]}_{file.filename}"
    target_path = UPLOADS_DIR / file.filename

    # If file with same name exists, add suffix
    counter = 1
    while target_path.exists():
        target_path = UPLOADS_DIR / f"{Path(file.filename).stem}_{counter}{Path(file.filename).suffix}"
        counter += 1

    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Validate and register
        registered = db_registry.register_database(
            name=name,
            file_path=target_path,
            filename=target_path.name
        )
        return registered

    except ValueError as ve:
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(status_code=500, detail=f"Database upload failed: {str(e)}")


@app.delete("/api/databases/{db_id}")
def delete_database(db_id: str):
    """Deletes a custom user database."""
    success = db_registry.delete_database(db_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete database (either default or not found).")
    return {"success": True, "db_id": db_id}


# ==============================================================================
# Schema Introspection Endpoint
# ==============================================================================
@app.get("/api/tables")
def get_tables(db_id: str = Query(default="chinook")):
    """
    Returns live database tables and columns for the selected database.
    """
    try:
        pipeline = get_pipeline_for_db(db_id)
        table_names = pipeline.db_engine.get_table_names()
        schema_data = []
        for table in table_names:
            cols = pipeline.db_engine.get_table_schema(table)
            col_list = [f"{c['name']} ({c['type']})" for c in cols]
            schema_data.append({"name": table, "cols": col_list})
        return {"db_id": db_id, "tables": schema_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database introspection failed: {str(e)}")


# ==============================================================================
# Health Check Endpoint
# ==============================================================================
@app.get("/api/health")
def health_check():
    """Health check endpoint to verify API connectivity."""
    return {"status": "healthy", "service": "Multi-Database Text-to-SQL API"}


# ==============================================================================
# Persistent Chat Session Endpoints (JSON Storage)
# ==============================================================================
@app.get("/api/chats")
def get_chats():
    """Fetches all conversation sessions and their message history from backend JSON."""
    try:
        return {"chats": chat_storage.list_chats()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve chat history: {str(e)}")


@app.post("/api/chats")
def create_chat(payload: CreateChatRequest):
    """Creates a new conversation session on the backend."""
    try:
        chat = chat_storage.create_chat(chat_id=payload.id, title=payload.title)
        return chat
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create chat: {str(e)}")


@app.patch("/api/chats/{chat_id}")
def update_chat(chat_id: str, payload: UpdateChatRequest):
    """Updates the conversation session title."""
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty.")
    success = chat_storage.update_chat_title(chat_id, payload.title.strip())
    if not success:
        raise HTTPException(status_code=404, detail="Chat not found.")
    return {"success": True, "chat_id": chat_id, "title": payload.title.strip()}


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str):
    """Deletes a conversation session and all its messages from backend JSON."""
    try:
        success = chat_storage.delete_chat(chat_id)
        return {"success": success, "chat_id": chat_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete chat: {str(e)}")


@app.post("/api/chats/{chat_id}/query")
def execute_chat_query(chat_id: str, payload: QueryRequest):
    """
    Executes a Text-to-SQL query within a specific chat session against the selected database:
    1. Saves the User message to the backend database.
    2. Runs Text-to-SQL pipeline for the chosen database (e.g. Chinook or custom).
    3. Saves AI response with SQL, results, and database source badge.
    """
    import time
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        # Resolve database info
        db_id = payload.db_id or "chinook"
        db_info = db_registry.get_database(db_id) or {"name": "Default Database", "id": "chinook"}

        # Check existing messages to update chat title if first message
        existing_chats = chat_storage.list_chats()
        target_chat = next((c for c in existing_chats if c["id"] == chat_id), None)
        
        if not target_chat:
            chat_storage.create_chat(chat_id=chat_id, title=payload.question[:32])
        elif len(target_chat.get("messages", [])) == 0:
            chat_storage.update_chat_title(chat_id, payload.question[:32])

        # 1. Store User Message
        user_msg_id = str(int(time.time() * 1000))
        chat_storage.add_message(
            chat_id=chat_id,
            message_id=user_msg_id,
            role="user",
            content=payload.question
        )

        # 2. Run Pipeline against selected database
        pipeline = get_pipeline_for_db(db_id)
        result = pipeline.run_pipeline(payload.question)

        # 3. Store AI Response with Database context
        ai_msg_id = str(int(time.time() * 1000) + 1)
        telemetry = {
            "confidence_score": result.get("confidence_score", 0),
            "latency_ms": result.get("latency_ms", 0),
            "attempts": result.get("attempts", 1),
            "status": result.get("status", "SUCCESS"),
            "error": result.get("error"),
            "db_id": db_id,
            "db_name": db_info.get("name", "Chinook")
        }

        chat_storage.add_message(
            chat_id=chat_id,
            message_id=ai_msg_id,
            role="assistant",
            content=result.get("summary", ""),
            sql=result.get("final_sql"),
            data=result.get("data"),
            telemetry=telemetry,
            status=result.get("status", "SUCCESS")
        )

        return {
            "id": ai_msg_id,
            "role": "assistant",
            "content": result.get("summary", ""),
            "sql": result.get("final_sql"),
            "data": result.get("data"),
            "telemetry": telemetry,
            "status": result.get("status", "SUCCESS"),
            "db_name": db_info.get("name", "Chinook")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline execution error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
