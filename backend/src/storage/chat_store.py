"""
Chat Storage Module.

Provides pure functional persistence and session management for conversational
chat history stored in backend/data/chat_history.json.
All sessions, user prompts, AI responses, generated code/queries, and
telemetry metrics are stored in structured, human-readable JSON.

Zero OOP classes; 100% pure stateless functions with backwards-compatible signatures.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import CHAT_HISTORY_FILE, ensure_directories


# ==============================================================================
# Low-Level File Persistence
# ==============================================================================
def _resolve_file_path(file_path: Optional[Path | str] = None) -> Path:
    """Resolves and returns the Path object for chat history storage."""
    if file_path is None:
        return CHAT_HISTORY_FILE
    return Path(file_path).resolve()


def _normalize_chat_record(chat: Dict[str, Any]) -> Dict[str, Any]:
    """Ensures each chat session has db_id and db_name populated if available."""
    if not chat.get("db_id"):
        # Try to infer db_id and db_name from messages telemetry
        for msg in chat.get("messages", []):
            t = msg.get("telemetry") or {}
            if t.get("db_id"):
                chat["db_id"] = t.get("db_id")
                chat["db_name"] = t.get("db_name") or t.get("db_id")
                break
    if chat.get("db_id") and not chat.get("db_name"):
        known_names = {
            "chinook": "Chinook (Music)",
            "ecommerce_store": "E-Commerce Store (NoSQL)",
            "sales_performance": "Sales Performance (CSV)",
            "financial_budget": "Financial Budget (Excel)",
        }
        chat["db_name"] = known_names.get(chat["db_id"], chat["db_id"].replace("_", " ").title())
    return chat


def _read_chats(file_path: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """
    Safely reads and parses the JSON chat history file.
    Returns an empty list if file doesn't exist, is empty, or is corrupted.
    """
    path = _resolve_file_path(file_path)
    if not path.exists():
        _write_chats([], path)
        return []

    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return []
        data = json.loads(content)
        if isinstance(data, list):
            return [_normalize_chat_record(c) for c in data if isinstance(c, dict)]
        return []
    except (json.JSONDecodeError, OSError):
        return []


def _write_chats(data: List[Dict[str, Any]], file_path: Optional[Path | str] = None) -> None:
    """
    Safely writes formatted chat history JSON to disk.
    Automatically ensures parent directory exists.
    """
    path = _resolve_file_path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ==============================================================================
# Session Management (Pure Functions)
# ==============================================================================
def list_all_chats(file_path: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """
    Returns all chat sessions ordered newest first.
    """
    return _read_chats(file_path)


def get_chat_session(chat_id: str, file_path: Optional[Path | str] = None) -> Optional[Dict[str, Any]]:
    """
    Finds and returns a single conversation session by ID, or None if not found.
    """
    chats = _read_chats(file_path)
    for chat in chats:
        if chat.get("id") == chat_id:
            return chat
    return None


def create_chat_session(
    chat_id: str,
    title: str = "New Conversation",
    file_path: Optional[Path | str] = None,
    db_id: Optional[str] = None,
    db_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates and persists a new conversation session.
    If the chat_id already exists, returns the existing session without duplicating.
    New sessions are inserted at the beginning (newest first).
    Maintains 100% backward compatibility with positional file_path callers.
    """
    # Detect if 3rd positional argument was passed as db_id instead of file_path
    resolved_file_path = file_path
    resolved_db_id = db_id
    if isinstance(file_path, str) and not file_path.endswith(".json") and "/" not in file_path and "\\" not in file_path:
        resolved_db_id = file_path
        resolved_file_path = None

    chats = _read_chats(resolved_file_path)

    # Prevent duplicate session creation
    for chat in chats:
        if chat.get("id") == chat_id:
            return chat

    clean_db_id = resolved_db_id.strip() if resolved_db_id else None
    if clean_db_id and not db_name:
        known_names = {
            "chinook": "Chinook (Music)",
            "ecommerce_store": "E-Commerce Store (NoSQL)",
            "sales_performance": "Sales Performance (CSV)",
            "financial_budget": "Financial Budget (Excel)",
        }
        db_name = known_names.get(clean_db_id, clean_db_id.replace("_", " ").title())

    new_chat: Dict[str, Any] = {
        "id": chat_id,
        "title": title or "New Conversation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "messages": []
    }
    if clean_db_id:
        new_chat["db_id"] = clean_db_id
        new_chat["db_name"] = db_name

    # Prepend newest chat session
    chats.insert(0, new_chat)
    _write_chats(chats, resolved_file_path)
    return new_chat


def update_chat_db(
    chat_id: str,
    db_id: str,
    db_name: Optional[str] = None,
    file_path: Optional[Path | str] = None
) -> bool:
    """
    Updates the dataset associated with a chat session.
    STRICT INVARIANT: Only permitted if the conversation has 0 messages.
    Once messages exist, the conversation is locked to its dataset.
    """
    chats = _read_chats(file_path)
    for chat in chats:
        if chat.get("id") == chat_id:
            if len(chat.get("messages", [])) > 0:
                return False
            clean_db_id = (db_id or "chinook").strip()
            chat["db_id"] = clean_db_id
            if db_name:
                chat["db_name"] = db_name.strip()
            else:
                known_names = {
                    "chinook": "Chinook (Music)",
                    "ecommerce_store": "E-Commerce Store (NoSQL)",
                    "sales_performance": "Sales Performance (CSV)",
                    "financial_budget": "Financial Budget (Excel)",
                }
                chat["db_name"] = known_names.get(clean_db_id, clean_db_id.replace("_", " ").title())
            _write_chats(chats, file_path)
            return True
    return False


def update_chat_title(
    chat_id: str,
    title: str,
    file_path: Optional[Path | str] = None
) -> bool:
    """
    Updates the conversation session title.
    Returns True if found and updated, False otherwise.
    """
    clean_title = title.strip()
    if not clean_title:
        return False

    chats = _read_chats(file_path)
    for chat in chats:
        if chat.get("id") == chat_id:
            chat["title"] = clean_title
            _write_chats(chats, file_path)
            return True
    return False


def auto_title_chat(
    chat_id: str,
    prompt_text: str,
    max_chars: int = 32,
    file_path: Optional[Path | str] = None
) -> bool:
    """
    Auto-titles a chat session based on prompt text if it's untitled, empty,
    or currently named 'New Conversation'.
    """
    clean_prompt = prompt_text.strip()
    if not clean_prompt:
        return False

    target_title = clean_prompt[:max_chars].strip()
    chats = _read_chats(file_path)
    for chat in chats:
        if chat.get("id") == chat_id:
            current_title = (chat.get("title") or "").strip()
            # Only update if default, empty, or has no messages yet
            if not current_title or current_title == "New Conversation" or len(chat.get("messages", [])) == 0:
                chat["title"] = target_title
                _write_chats(chats, file_path)
                return True
            return False
    return False


def delete_chat_session(
    chat_id: str,
    file_path: Optional[Path | str] = None
) -> bool:
    """
    Deletes a conversation session from JSON storage by ID.
    Returns True if deleted, False if chat was not found.
    """
    chats = _read_chats(file_path)
    initial_count = len(chats)
    remaining_chats = [c for c in chats if c.get("id") != chat_id]

    if len(remaining_chats) < initial_count:
        _write_chats(remaining_chats, file_path)
        return True
    return False


# ==============================================================================
# Message Management (Pure Functions)
# ==============================================================================
def append_chat_message(
    chat_id: str,
    message_id: str,
    role: str,
    content: str,
    sql: Optional[str] = None,
    data: Optional[List[Dict[str, Any]]] = None,
    telemetry: Optional[Dict[str, Any]] = None,
    status: str = "SUCCESS",
    sub_queries: Optional[List[Dict[str, Any]]] = None,
    needed_tables: Optional[List[str]] = None,
    available_tables: Optional[List[str]] = None,
    suggested_questions: Optional[List[str]] = None,
    title: Optional[str] = None,
    file_path: Optional[Path | str] = None
) -> Dict[str, Any]:
    """
    Appends a new message to the specified conversation session in JSON storage.
    If the session does not exist, it is automatically created with title derived
    from the content.
    """
    chats = _read_chats(file_path)
    target_chat = next((c for c in chats if c.get("id") == chat_id), None)

    if target_chat is None:
        # Auto-create chat if not found
        auto_title = content[:32].strip() if content else "New Conversation"
        inferred_db_id = (telemetry or {}).get("db_id") or "chinook"
        inferred_db_name = (telemetry or {}).get("db_name")
        if not inferred_db_name:
            known_names = {
                "chinook": "Chinook (Music)",
                "ecommerce_store": "E-Commerce Store (NoSQL)",
                "sales_performance": "Sales Performance (CSV)",
                "financial_budget": "Financial Budget (Excel)",
            }
            inferred_db_name = known_names.get(inferred_db_id, inferred_db_id.replace("_", " ").title())

        target_chat = {
            "id": chat_id,
            "title": auto_title or "New Conversation",
            "db_id": inferred_db_id,
            "db_name": inferred_db_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "messages": []
        }
        chats.insert(0, target_chat)
    else:
        if not target_chat.get("db_id") and telemetry and telemetry.get("db_id"):
            target_chat["db_id"] = telemetry["db_id"]
        if not target_chat.get("db_name") and telemetry and telemetry.get("db_name"):
            target_chat["db_name"] = telemetry["db_name"]

    new_message: Dict[str, Any] = {
        "id": message_id,
        "role": role,
        "title": title,
        "content": content,
        "sql": sql,
        "data": data,
        "sub_queries": sub_queries,
        "telemetry": telemetry,
        "status": status,
        "needed_tables": needed_tables or [],
        "available_tables": available_tables or [],
        "suggested_questions": suggested_questions or [],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    target_chat["messages"].append(new_message)
    _write_chats(chats, file_path)
    return new_message


def get_conversation_context(
    chat_id: str,
    limit: int = 4,
    file_path: Optional[Path | str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves the last `limit` completed conversational turns (user question +
    assistant response) for feeding as memory to the LLM generator.
    """
    target_chat = get_chat_session(chat_id, file_path)
    if not target_chat or not target_chat.get("messages"):
        return []

    # Get last limit * 2 messages (pairs of user/assistant)
    recent_messages = target_chat["messages"][-(limit * 2):]
    context_turns: List[Dict[str, Any]] = []

    for msg in recent_messages:
        context_turns.append({
            "role": msg.get("role"),
            "content": msg.get("content", ""),
            "sql": msg.get("sql"),
            "status": msg.get("status", "SUCCESS")
        })

    return context_turns


def clear_all_chats(file_path: Optional[Path | str] = None) -> None:
    """Empties the chat history file. Useful for testing and resets."""
    _write_chats([], file_path)


# ==============================================================================
# Backward-Compatible Function Aliases
# ==============================================================================
list_chats = list_all_chats
get_chat = get_chat_session
create_chat = create_chat_session
delete_chat = delete_chat_session
add_message = append_chat_message
update_chat_dataset = update_chat_db

