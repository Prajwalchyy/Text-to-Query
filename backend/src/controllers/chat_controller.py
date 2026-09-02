import time
from typing import Dict, Any, Optional
from fastapi import HTTPException
from pydantic import BaseModel
from F07_chat_storage import ChatStorage
from F08_database_registry import DatabaseRegistry
from controllers.database_controller import DatabaseController

chat_storage = ChatStorage()
db_registry = DatabaseRegistry()


class CreateChatRequest(BaseModel):
    id: str
    title: Optional[str] = "New Conversation"


class UpdateChatRequest(BaseModel):
    title: str


class QueryRequest(BaseModel):
    question: str
    db_id: Optional[str] = "chinook"


class ChatController:
    """
    Controller handling conversational chat sessions, message persistence,
    title renaming, and query execution against the chosen database.
    """

    @staticmethod
    def list_chats() -> Dict[str, Any]:
        """Fetches all conversation sessions and message history from backend JSON."""
        try:
            return {"chats": chat_storage.list_chats()}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve chat history: {str(e)}")

    @staticmethod
    def create_chat(payload: CreateChatRequest) -> Dict[str, Any]:
        """Creates and persists a new conversation session."""
        try:
            chat = chat_storage.create_chat(chat_id=payload.id, title=payload.title)
            return chat
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create chat: {str(e)}")

    @staticmethod
    def update_chat_title(chat_id: str, payload: UpdateChatRequest) -> Dict[str, Any]:
        """Updates a conversation session title."""
        if payload.title.strip() == "":
            raise HTTPException(status_code=400, detail="Title cannot be empty.")
        
        success = chat_storage.update_chat_title(chat_id, payload.title.strip())
        if success == False:
            raise HTTPException(status_code=404, detail="Chat not found.")
        return {"success": True, "chat_id": chat_id, "title": payload.title.strip()}

    @staticmethod
    def delete_chat(chat_id: str) -> Dict[str, Any]:
        """Deletes a conversation session from JSON storage."""
        try:
            success = chat_storage.delete_chat(chat_id)
            return {"success": success, "chat_id": chat_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete chat: {str(e)}")

    @staticmethod
    def execute_query(chat_id: str, payload: QueryRequest) -> Dict[str, Any]:
        """
        Executes a Text-to-SQL query within a specific chat session:
        1. Stores User message.
        2. Executes pipeline on selected database (Chinook or custom).
        3. Stores AI response with SQL, table data, and database telemetry.
        """
        if payload.question.strip() == "":
            raise HTTPException(status_code=400, detail="Question cannot be empty.")

        try:
            # Resolve database metadata
            db_id = payload.db_id if payload.db_id != None and payload.db_id != "" else "chinook"
            db_info = db_registry.get_database(db_id)
            if db_info == None:
                db_info = {"name": "Default Database", "id": "chinook"}

            # Auto-title chat from first question if needed
            existing_chats = chat_storage.list_chats()
            target_chat = next((c for c in existing_chats if c["id"] == chat_id), None)

            if target_chat == None:
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
            pipeline = DatabaseController.get_pipeline(db_id)
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
                "db_name": db_info.get("name", "Default"),
                "db_type": db_info.get("type", "sql")
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
                "db_name": db_info.get("name", "Default"),
                "db_type": db_info.get("type", "sql")
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Pipeline execution error: {str(e)}")
