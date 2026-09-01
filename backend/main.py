import sys
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add backend/src to Python path so pipeline modules are found
SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from F06_pipeline import TextToSQLPipeline
from F07_chat_storage import ChatStorage

# ==============================================================================
# FastAPI Application & CORS Configuration
# ==============================================================================
app = FastAPI(
    title="Enterprise Text-to-SQL API",
    description="Backend API with 4-layer guardrails, self-correction, hallucination scoring, and persistent chat storage",
    version="1.0.0",
)

# Allow React frontend (Vite running on localhost:5173 or 5174) to communicate
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

# Initialize pipeline and database chat storage
pipeline = TextToSQLPipeline()
chat_storage = ChatStorage()


# ==============================================================================
# Request & Response Models
# ==============================================================================
class QueryRequest(BaseModel):
    question: str

class CreateChatRequest(BaseModel):
    id: str
    title: Optional[str] = "New Conversation"


# ==============================================================================
# System & Database Introspection Endpoints
# ==============================================================================
@app.get("/api/health")
def health_check():
    """Health check endpoint to verify API and database connectivity."""
    return {"status": "healthy", "service": "Text-to-SQL Pipeline API"}


@app.get("/api/tables")
def get_tables():
    """Returns live database tables and their schema for the React sidebar."""
    try:
        table_names = pipeline.db_engine.get_table_names()
        schema_data = []
        for table in table_names:
            cols = pipeline.db_engine.get_table_schema(table)
            col_list = [f"{c['name']} ({c['type']})" for c in cols]
            schema_data.append({"name": table, "cols": col_list})
        return {"tables": schema_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database introspection failed: {str(e)}")


# ==============================================================================
# Persistent Chat Session Endpoints (Backend SQLite Storage)
# ==============================================================================
@app.get("/api/chats")
def get_chats():
    """Fetches all conversation sessions and their message history from backend SQLite."""
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


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str):
    """Deletes a conversation session and all its messages from backend SQLite."""
    try:
        success = chat_storage.delete_chat(chat_id)
        return {"success": success, "chat_id": chat_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete chat: {str(e)}")


@app.post("/api/chats/{chat_id}/query")
def execute_chat_query(chat_id: str, payload: QueryRequest):
    """
    Executes a Text-to-SQL query within a specific chat session:
    1. Saves the User message to the backend database.
    2. Updates chat title if this is the first message.
    3. Runs the Text-to-SQL pipeline (Guardrails -> Execution -> Evaluation).
    4. Saves the AI response (Summary, SQL, data, telemetry) to the backend database.
    5. Returns the complete AI response.
    """
    import time
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        # Check existing messages to determine if we should update the chat title
        existing_chats = chat_storage.list_chats()
        target_chat = next((c for c in existing_chats if c["id"] == chat_id), None)
        
        if not target_chat:
            # Auto-create chat if not exists
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

        # 2. Run Pipeline
        result = pipeline.run_pipeline(payload.question)

        # 3. Store AI Response
        ai_msg_id = str(int(time.time() * 1000) + 1)
        telemetry = {
            "confidence_score": result.get("confidence_score", 0),
            "latency_ms": result.get("latency_ms", 0),
            "attempts": result.get("attempts", 1),
            "status": result.get("status", "SUCCESS")
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
            "status": result.get("status", "SUCCESS")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline execution error: {str(e)}")


@app.post("/api/query")
def execute_standalone_query(payload: QueryRequest):
    """Standalone query execution endpoint (backward compatible)."""
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    try:
        return pipeline.run_pipeline(payload.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
