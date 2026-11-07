import sys
import tempfile
from pathlib import Path
import pytest

# Ensure backend and src are in path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
src_dir = backend_dir / "src"
for p in [str(root_dir), str(backend_dir), str(src_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from storage.chat_store import (
    list_all_chats,
    create_chat_session,
    get_chat_session,
    update_chat_title,
    auto_title_chat,
    delete_chat_session,
    append_chat_message,
    get_conversation_context,
)
from storage.registry import (
    list_databases,
    get_database,
)


def test_chat_store_crud_lifecycle():
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_file = Path(tmp_dir) / "test_chat_history.json"

        # 1. Initial empty read
        assert list_all_chats(temp_file) == []

        # 2. Create session
        session = create_chat_session("session_123", "First Conversation", temp_file)
        assert session["id"] == "session_123"
        assert session["title"] == "First Conversation"
        assert session["messages"] == []

        # 3. Prevent duplicate creation
        dup = create_chat_session("session_123", "Duplicate Session", temp_file)
        assert dup["id"] == "session_123"
        assert len(list_all_chats(temp_file)) == 1

        # 4. Lookup session
        found = get_chat_session("session_123", temp_file)
        assert found is not None
        assert found["title"] == "First Conversation"
        assert get_chat_session("unknown_id", temp_file) is None

        # 5. Update title
        assert update_chat_title("session_123", "Renamed Conversation", temp_file) is True
        assert get_chat_session("session_123", temp_file)["title"] == "Renamed Conversation"
        assert update_chat_title("session_123", "   ", temp_file) is False

        # 6. Append user message
        user_msg = append_chat_message(
            chat_id="session_123",
            message_id="msg_001",
            role="user",
            content="Show total revenue for 2024",
            file_path=temp_file
        )
        assert user_msg["role"] == "user"
        assert user_msg["content"] == "Show total revenue for 2024"

        # 7. Append assistant message
        asst_msg = append_chat_message(
            chat_id="session_123",
            message_id="msg_002",
            role="assistant",
            content="Total revenue was calculated.",
            sql="SELECT SUM(Total) FROM Invoices WHERE Year = 2024;",
            data=[{"SUM(Total)": 50000}],
            telemetry={"confidence_score": 0.98},
            file_path=temp_file
        )
        assert asst_msg["sql"] == "SELECT SUM(Total) FROM Invoices WHERE Year = 2024;"
        assert len(get_chat_session("session_123", temp_file)["messages"]) == 2

        # 8. Memory window context retrieval
        context = get_conversation_context("session_123", limit=4, file_path=temp_file)
        assert len(context) == 2
        assert context[0]["role"] == "user"
        assert context[1]["role"] == "assistant"
        assert context[1]["sql"] == "SELECT SUM(Total) FROM Invoices WHERE Year = 2024;"

        # 9. Auto-create session on message append to new chat_id
        append_chat_message(
            chat_id="session_auto",
            message_id="msg_003",
            role="user",
            content="What are top products?",
            file_path=temp_file
        )
        auto_chat = get_chat_session("session_auto", temp_file)
        assert auto_chat is not None
        assert auto_chat["title"] == "What are top products?"

        # 10. Delete session
        assert delete_chat_session("session_123", temp_file) is True
        assert get_chat_session("session_123", temp_file) is None
        assert len(list_all_chats(temp_file)) == 1


def test_auto_title_chat():
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_file = Path(tmp_dir) / "test_chat_history.json"
        create_chat_session("session_title", "New Conversation", temp_file)

        # Should auto-title from initial prompt
        updated = auto_title_chat("session_title", "How many customers are in Canada?", max_chars=32, file_path=temp_file)
        assert updated is True
        assert get_chat_session("session_title", temp_file)["title"] == "How many customers are in Canada"


def test_registry_integration():
    """Verifies that default datasets are present in registry."""
    dbs = list_databases()
    assert len(dbs) >= 4
    db_ids = {d["id"] for d in dbs}
    assert "chinook" in db_ids
    assert "ecommerce_store" in db_ids
    assert "sales_performance" in db_ids
    assert "financial_budget" in db_ids

    chinook = get_database("chinook")
    assert chinook is not None
    assert chinook["type"] == "sql"


def test_chat_storage_directory_and_path_resolution():
    """Verifies that chat storage points to data/chat-storage and resolves correctly."""
    from config import CHAT_STORAGE_DIR, CHAT_HISTORY_FILE
    from storage.chat_store import _resolve_file_path

    assert CHAT_STORAGE_DIR.name == "chat-storage"
    assert CHAT_HISTORY_FILE.name == "chat_history.json"
    assert CHAT_HISTORY_FILE.parent == CHAT_STORAGE_DIR

    # When no explicit file path is provided, it resolves to CHAT_HISTORY_FILE
    resolved = _resolve_file_path()
    assert resolved.name == "chat_history.json"
    assert "chat-storage" in str(resolved)


