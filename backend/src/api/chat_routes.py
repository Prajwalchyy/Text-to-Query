"""
Chat & Conversational Query API Routes.
Enterprise Text-to-SQL API (v2.0)

Pure functional route handlers for chat session management (CRUD),
conversational Text-to-SQL/polyglot query execution, cross-language code translation,
and supported dialect discovery.

Zero OOP business logic; 100% stateless pure functions with a backward-compatible adapter.
"""

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, HTTPException

# Ensure backend root and src directory are on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = Path(__file__).resolve().parent.parent
for p in [str(BACKEND_DIR), str(SRC_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# API Schemas & DTOs
try:
    from src.api.schemas import (
        CreateChatRequest,
        UpdateChatRequest,
        QueryRequest,
        ConvertCodeRequest,
        ChatsListResponse,
        GenericActionResponse,
        QueryExecutionResponse,
        CodeConversionResponse,
        SupportedLanguagesResponse,
    )
except ImportError:
    from api.schemas import (
        CreateChatRequest,
        UpdateChatRequest,
        QueryRequest,
        ConvertCodeRequest,
        ChatsListResponse,
        GenericActionResponse,
        QueryExecutionResponse,
        CodeConversionResponse,
        SupportedLanguagesResponse,
    )

# Storage
try:
    from src.storage.chat_store import (
        append_chat_message,
        create_chat_session,
        delete_chat_session,
        get_chat_session,
        get_conversation_context,
        list_all_chats,
        update_chat_title,
    )
    from src.storage.registry import get_database, list_databases
except ImportError:
    from storage.chat_store import (
        append_chat_message,
        create_chat_session,
        delete_chat_session,
        get_chat_session,
        get_conversation_context,
        list_all_chats,
        update_chat_title,
    )
    from storage.registry import get_database, list_databases

# Pipeline & Polyglot Engine
try:
    from src.pipelines.router import (
        introspect_datasource,
        resolve_datasource,
        run_pipeline,
    )
    from src.core.polyglot import (
        LANGUAGE_CONFIG,
        convert_code,
        get_supported_languages,
        is_language_supported,
        normalize_db_type,
    )
except ImportError:
    from pipelines.router import (
        introspect_datasource,
        resolve_datasource,
        run_pipeline,
    )
    from core.polyglot import (
        LANGUAGE_CONFIG,
        convert_code,
        get_supported_languages,
        is_language_supported,
        normalize_db_type,
    )

router = APIRouter(tags=["Chats"])


# ==============================================================================
# Pure Functional Service Helpers
# ==============================================================================
def list_chats_data(file_path: Optional[Union[Path, str]] = None) -> Dict[str, Any]:
    """Fetches all conversation sessions and message history from JSON storage."""
    try:
        return {"chats": list_all_chats(file_path=file_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve chat history: {str(e)}")


def create_chat_session_data(
    payload: CreateChatRequest,
    file_path: Optional[Union[Path, str]] = None,
) -> Dict[str, Any]:
    """Creates and persists a new conversation session."""
    try:
        chat = create_chat_session(chat_id=payload.id, title=payload.title, file_path=file_path)
        return chat
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create chat: {str(e)}")


def update_chat_title_data(
    chat_id: str,
    payload: UpdateChatRequest,
    file_path: Optional[Union[Path, str]] = None,
) -> Dict[str, Any]:
    """Updates a conversation session title."""
    clean_title = (payload.title or "").strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="Title cannot be empty.")

    success = update_chat_title(chat_id=chat_id, title=clean_title, file_path=file_path)
    if not success:
        raise HTTPException(status_code=404, detail="Chat not found.")
    return {"success": True, "chat_id": chat_id, "title": clean_title}


def delete_chat_data(
    chat_id: str,
    file_path: Optional[Union[Path, str]] = None,
) -> Dict[str, Any]:
    """Deletes a conversation session from JSON storage."""
    try:
        success = delete_chat_session(chat_id=chat_id, file_path=file_path)
        return {"success": success, "chat_id": chat_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete chat: {str(e)}")


def execute_query_data(
    chat_id: str,
    payload: QueryRequest,
    file_path: Optional[Union[Path, str]] = None,
) -> Dict[str, Any]:
    """
    Executes a Text-to-SQL or multi-language query within a specific chat session:
    1. Validates non-empty prompt.
    2. Resolves target dataset metadata (defaults to Chinook).
    3. Auto-titles the chat session from initial question if new or empty.
    4. Fetches conversational memory window (last 4 turns).
    5. Stores user prompt message in chat storage.
    6. Dispatches to stateless master pipeline runner (`run_pipeline`).
    7. Stores AI assistant response with full telemetry and metadata.
    8. Returns standardized response payload matching `QueryExecutionResponse`.
    """
    clean_q = (payload.question or "").strip()
    if not clean_q:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        # Resolve database metadata
        db_id = payload.db_id if payload.db_id and payload.db_id.strip() else "chinook"
        db_info = get_database(db_id)
        if not db_info:
            db_info = {"name": "Default Database", "id": "chinook", "type": "sql"}

        # Auto-title chat from first question if session is new or has 0 messages
        existing_chat = get_chat_session(chat_id, file_path=file_path)
        auto_title = clean_q[:32].strip() or "New Conversation"

        if existing_chat is None:
            create_chat_session(chat_id=chat_id, title=auto_title, file_path=file_path)
        elif len(existing_chat.get("messages", [])) == 0:
            update_chat_title(chat_id=chat_id, title=auto_title, file_path=file_path)

        # 1. Fetch Prior Conversation Context (Memory Window)
        conversation_context = get_conversation_context(chat_id=chat_id, limit=4, file_path=file_path)

        # 2. Store User Message
        user_msg_id = str(int(time.time() * 1000))
        append_chat_message(
            chat_id=chat_id,
            message_id=user_msg_id,
            role="user",
            content=clean_q,
            file_path=file_path,
        )

        # 3. Run Pipeline with Conversational Memory and Target Language
        target_lang = payload.target_language
        result = run_pipeline(
            question=clean_q,
            db_id=db_id,
            target_language=target_lang,
            history=conversation_context,
        )

        # Determine resulting code_type
        result_code_type = result.get("code_type")
        if not result_code_type:
            if target_lang:
                result_code_type = target_lang
            elif db_info.get("type") == "excel":
                result_code_type = "excel_formula"
            elif db_info.get("type") == "csv":
                result_code_type = "pandas"
            elif db_info.get("type") == "nosql":
                result_code_type = "nosql"
            else:
                result_code_type = "sql"

        # 4. Store AI Assistant Response with full Telemetry
        ai_msg_id = str(int(time.time() * 1000) + 1)
        telemetry = {
            "confidence_score": result.get("confidence_score", 0),
            "latency_ms": result.get("latency_ms", 0),
            "attempts": result.get("attempts", 1),
            "status": result.get("status", "SUCCESS"),
            "error": result.get("error"),
            "db_id": db_id,
            "db_name": db_info.get("name", "Default"),
            "db_type": db_info.get("type", "sql"),
            "code_type": result_code_type,
            "needed_tables": result.get("needed_tables", []),
            "available_tables": result.get("available_tables", []),
            "suggested_questions": result.get("suggested_questions", []),
        }

        resolved_title = result.get("title") or (
            result.get("sub_queries", [{}])[0].get("title")
            if result.get("sub_queries")
            else None
        )

        append_chat_message(
            chat_id=chat_id,
            message_id=ai_msg_id,
            role="assistant",
            title=resolved_title,
            content=result.get("summary", ""),
            sql=result.get("final_sql"),
            data=result.get("data"),
            sub_queries=result.get("sub_queries"),
            telemetry=telemetry,
            status=result.get("status", "SUCCESS"),
            needed_tables=result.get("needed_tables", []),
            available_tables=result.get("available_tables", []),
            suggested_questions=result.get("suggested_questions", []),
            file_path=file_path,
        )

        return {
            "id": ai_msg_id,
            "role": "assistant",
            "title": resolved_title,
            "content": result.get("summary", ""),
            "sql": result.get("final_sql"),
            "data": result.get("data"),
            "sub_queries": result.get("sub_queries"),
            "telemetry": telemetry,
            "status": result.get("status", "SUCCESS"),
            "needed_tables": result.get("needed_tables", []),
            "available_tables": result.get("available_tables", []),
            "suggested_questions": result.get("suggested_questions", []),
            "db_name": db_info.get("name", "Default"),
            "db_type": db_info.get("type", "sql"),
            "code_type": result_code_type,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline execution error: {str(e)}")


def convert_code_data(payload: ConvertCodeRequest) -> Dict[str, Any]:
    """
    Translates an existing query or code snippet into another dialect with full schema awareness.
    """
    db_id = payload.db_id if payload.db_id and payload.db_id.strip() else "chinook"
    db_info = get_database(db_id)
    db_type = db_info.get("type", "sql") if db_info else "sql"

    schema_context = ""
    try:
        _, canonical_type, resolved_path = resolve_datasource(db_id)
        _, schema_context, _ = introspect_datasource(canonical_type, resolved_path)
    except Exception:
        pass

    try:
        converted = convert_code(
            code=payload.code,
            from_language=payload.from_language,
            to_language=payload.to_language,
            schema_context=schema_context,
            db_type=db_type,
        )
        # Enrich with language display metadata for client consumption
        target_cfg = LANGUAGE_CONFIG.get(payload.to_language.lower().strip(), {})
        converted.setdefault("converted_code", converted.get("code"))
        converted.setdefault("from_language", payload.from_language)
        converted.setdefault("to_language", payload.to_language)
        converted.setdefault("language_name", target_cfg.get("name", payload.to_language))
        converted.setdefault("badge_color", target_cfg.get("color", "indigo"))
        converted.setdefault("extension", target_cfg.get("extension", ""))
        converted.setdefault("note", converted.get("explanation"))
        return converted
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def get_supported_languages_data(db_id: str) -> Dict[str, Any]:
    """Returns the list of allowed languages for the active data source."""
    db_info = get_database(db_id)
    db_type = db_info.get("type", "sql") if db_info else "sql"
    languages = get_supported_languages(db_type)
    return {
        "db_id": db_id,
        "db_type": db_type,
        "languages": languages,
    }


# ==============================================================================
# FastAPI APIRouter Endpoints
# ==============================================================================
@router.get("/chats")
def get_chats():
    """Fetches all conversation sessions and message history from JSON storage."""
    return list_chats_data()


@router.post("/chats")
def create_chat(payload: CreateChatRequest):
    """Creates a new conversation session on the backend."""
    return create_chat_session_data(payload=payload)


@router.patch("/chats/{chat_id}")
def update_chat(chat_id: str, payload: UpdateChatRequest):
    """Updates the conversation session title."""
    return update_chat_title_data(chat_id=chat_id, payload=payload)


@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: str):
    """Deletes a conversation session from JSON storage."""
    return delete_chat_data(chat_id=chat_id)


@router.post("/chats/{chat_id}/query")
def execute_chat_query(chat_id: str, payload: QueryRequest):
    """Executes a multi-language query within a specific chat session."""
    return execute_query_data(chat_id=chat_id, payload=payload)


@router.post("/chats/convert-code")
def convert_query_code(payload: ConvertCodeRequest):
    """Converts an existing query/code block into another language with full schema awareness."""
    return convert_code_data(payload=payload)


@router.get("/chats/languages/{db_id}")
def get_supported_languages_for_db(db_id: str):
    """Returns the list of allowed languages for the active data source."""
    return get_supported_languages_data(db_id=db_id)


# ==============================================================================
# Backward-Compatible Controller Adapter
# ==============================================================================
class ChatController:
    """
    Thin static adapter maintaining 100% backward compatibility with legacy
    controllers.chat_controller.ChatController callers.
    """
    list_chats = staticmethod(list_chats_data)
    create_chat = staticmethod(create_chat_session_data)
    update_chat_title = staticmethod(update_chat_title_data)
    delete_chat = staticmethod(delete_chat_data)
    execute_query = staticmethod(execute_query_data)
    convert_code = staticmethod(convert_code_data)
    get_supported_languages = staticmethod(get_supported_languages_data)

