"""Storage layer for dataset registry and chat history persistence."""

from storage.registry import (
    list_registered_databases,
    get_database_by_id,
    register_database,
    delete_registered_database,
    check_table_conflict,
    check_collection_conflict,
    get_upload_dir_for_type,
)

from storage.chat_store import (
    list_all_chats,
    get_chat_session,
    create_chat_session,
    update_chat_title,
    auto_title_chat,
    delete_chat_session,
    append_chat_message,
    get_conversation_context,
)

__all__ = [
    # Registry
    "list_registered_databases",
    "get_database_by_id",
    "register_database",
    "delete_registered_database",
    "check_table_conflict",
    "check_collection_conflict",
    "get_upload_dir_for_type",
    # Chat Storage
    "list_all_chats",
    "get_chat_session",
    "create_chat_session",
    "update_chat_title",
    "auto_title_chat",
    "delete_chat_session",
    "append_chat_message",
    "get_conversation_context",
]
