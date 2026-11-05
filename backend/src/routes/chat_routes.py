from fastapi import APIRouter
from controllers.chat_controller import (
    ChatController, 
    CreateChatRequest, 
    UpdateChatRequest, 
    QueryRequest,
    ConvertCodeRequest
)

router = APIRouter(tags=["Chats"])


@router.get("/chats")
def get_chats():
    """Fetches all conversation sessions and message history from backend JSON."""
    return ChatController.list_chats()


@router.post("/chats")
def create_chat(payload: CreateChatRequest):
    """Creates a new conversation session on the backend."""
    return ChatController.create_chat(payload=payload)


@router.patch("/chats/{chat_id}")
def update_chat(chat_id: str, payload: UpdateChatRequest):
    """Updates the conversation session title."""
    return ChatController.update_chat_title(chat_id=chat_id, payload=payload)


@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: str):
    """Deletes a conversation session from backend JSON."""
    return ChatController.delete_chat(chat_id=chat_id)


@router.post("/chats/{chat_id}/query")
def execute_chat_query(chat_id: str, payload: QueryRequest):
    """Executes a multi-language query within a specific chat session."""
    return ChatController.execute_query(chat_id=chat_id, payload=payload)


@router.post("/chats/convert-code")
def convert_query_code(payload: ConvertCodeRequest):
    """Converts an existing query/code block into another language with full schema awareness."""
    return ChatController.convert_code(payload=payload)


@router.get("/chats/languages/{db_id}")
def get_supported_languages(db_id: str):
    """Returns the list of allowed languages for the active data source."""
    return ChatController.get_supported_languages(db_id=db_id)

