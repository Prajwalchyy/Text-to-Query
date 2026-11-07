"""
Unit Tests for Chat & Conversational Query API Routes.
Phase D Step D.3 Verification
"""

import json
from unittest.mock import patch, MagicMock
import pytest
from fastapi import HTTPException

from backend.src.api.chat_routes import (
    get_chats,
    create_chat,
    update_chat,
    delete_chat,
    execute_chat_query,
    convert_query_code,
    get_supported_languages_for_db,
    list_chats_data,
    create_chat_session_data,
    update_chat_title_data,
    delete_chat_data,
    execute_query_data,
    convert_code_data,
    get_supported_languages_data,
    ChatController,
    router,
)
from backend.src.api.schemas import (
    CreateChatRequest,
    UpdateChatRequest,
    QueryRequest,
    ConvertCodeRequest,
)


@pytest.fixture
def temp_chat_file(tmp_path):
    """Provides an isolated JSON chat history file for each test."""
    p = tmp_path / "test_chat_history.json"
    p.write_text("[]", encoding="utf-8")
    return p


# ==============================================================================
# Chat CRUD Tests
# ==============================================================================
def test_list_chats_empty(temp_chat_file):
    """Verify listing chats on empty storage returns empty list."""
    res = list_chats_data(file_path=temp_chat_file)
    assert "chats" in res
    assert res["chats"] == []


def test_create_and_list_chat(temp_chat_file):
    """Verify creating a session persists and appears in listing."""
    req = CreateChatRequest(id="session-001", title="Sales Analysis")
    created = create_chat_session_data(req, file_path=temp_chat_file)

    assert created["id"] == "session-001"
    assert created["title"] == "Sales Analysis"
    assert "created_at" in created
    assert created["messages"] == []

    listed = list_chats_data(file_path=temp_chat_file)
    assert len(listed["chats"]) == 1
    assert listed["chats"][0]["id"] == "session-001"


def test_create_duplicate_chat_id_returns_existing(temp_chat_file):
    """Creating a chat with an existing ID should return existing session without duplication."""
    req1 = CreateChatRequest(id="session-dup", title="First Title")
    create_chat_session_data(req1, file_path=temp_chat_file)

    req2 = CreateChatRequest(id="session-dup", title="Second Title")
    res2 = create_chat_session_data(req2, file_path=temp_chat_file)

    assert res2["id"] == "session-dup"
    assert res2["title"] == "First Title"

    listed = list_chats_data(file_path=temp_chat_file)
    assert len(listed["chats"]) == 1


def test_update_chat_title(temp_chat_file):
    """Verify updating a session title."""
    req = CreateChatRequest(id="session-rename", title="Old Title")
    create_chat_session_data(req, file_path=temp_chat_file)

    upd = UpdateChatRequest(title="Brand New Title")
    res = update_chat_title_data(chat_id="session-rename", payload=upd, file_path=temp_chat_file)

    assert res["success"] is True
    assert res["chat_id"] == "session-rename"
    assert res["title"] == "Brand New Title"

    listed = list_chats_data(file_path=temp_chat_file)
    assert listed["chats"][0]["title"] == "Brand New Title"


def test_update_chat_title_not_found(temp_chat_file):
    """Updating a non-existent chat should raise 404 HTTPException."""
    upd = UpdateChatRequest(title="Some Title")
    with pytest.raises(HTTPException) as exc_info:
        update_chat_title_data(chat_id="non-existent-id", payload=upd, file_path=temp_chat_file)
    assert exc_info.value.status_code == 404


def test_delete_chat(temp_chat_file):
    """Verify deleting a chat removes it from storage."""
    req = CreateChatRequest(id="session-to-del", title="Delete Me")
    create_chat_session_data(req, file_path=temp_chat_file)

    res = delete_chat_data(chat_id="session-to-del", file_path=temp_chat_file)
    assert res["success"] is True
    assert res["chat_id"] == "session-to-del"

    listed = list_chats_data(file_path=temp_chat_file)
    assert len(listed["chats"]) == 0

    # Deleting non-existent chat returns success=False
    res_non_exist = delete_chat_data(chat_id="session-to-del", file_path=temp_chat_file)
    assert res_non_exist["success"] is False


# ==============================================================================
# Supported Languages Tests
# ==============================================================================
def test_get_supported_languages_for_sql():
    """Verify supported languages catalog for SQL database (chinook)."""
    res = get_supported_languages_data(db_id="chinook")
    assert res["db_id"] == "chinook"
    assert res["db_type"] == "sql"
    assert isinstance(res["languages"], list)

    lang_ids = [l["id"] for l in res["languages"]]
    assert "sql" in lang_ids
    assert "pandas" in lang_ids
    assert "r" in lang_ids
    assert "javascript" not in lang_ids
    assert "java" not in lang_ids
    assert "csharp" not in lang_ids
    assert "nosql" not in lang_ids
    assert "excel_formula" not in lang_ids


def test_get_supported_languages_for_nosql():
    """Verify supported languages catalog for NoSQL database (ecommerce_store)."""
    res = get_supported_languages_data(db_id="ecommerce_store")
    assert res["db_id"] == "ecommerce_store"
    assert res["db_type"] == "nosql"
    assert isinstance(res["languages"], list)

    lang_ids = [l["id"] for l in res["languages"]]
    assert "nosql" in lang_ids
    assert "pandas" in lang_ids
    assert "r" in lang_ids
    assert "sql" not in lang_ids
    assert "excel_formula" not in lang_ids


# ==============================================================================
# Code Conversion Tests
# ==============================================================================
def test_convert_code_unsupported_target():
    """Converting to an unsupported dialect should raise 400 HTTPException."""
    req = ConvertCodeRequest(
        code="SELECT * FROM customers",
        from_language="sql",
        to_language="nosql",
        db_id="chinook",
    )
    with pytest.raises(HTTPException) as exc_info:
        convert_code_data(req)
    assert exc_info.value.status_code == 400


def test_convert_code_valid_fallback():
    """Converting code to a valid target language returns enriched model."""
    req = ConvertCodeRequest(
        code="SELECT CustomerId, FirstName FROM Customer LIMIT 5;",
        from_language="sql",
        to_language="pandas",
        db_id="chinook",
    )
    res = convert_code_data(req)
    assert "code" in res
    assert res["from_language"] == "sql"
    assert res["to_language"] == "pandas"
    assert res["language_name"] == "Python (Pandas)"
    assert "badge_color" in res


# ==============================================================================
# Query Execution & Telemetry Tests
# ==============================================================================
def test_execute_query_empty_question(temp_chat_file):
    """Empty question string should raise 400 HTTPException."""
    with pytest.raises(Exception):
        # Pydantic validator will reject empty string
        QueryRequest(question="")


def test_execute_query_flow(temp_chat_file):
    """
    Verify complete query execution lifecycle:
    - Auto-creates chat session with question title
    - Persists user prompt message
    - Calls run_pipeline
    - Persists assistant response message with telemetry
    - Returns standardized QueryExecutionResponse shape
    """
    mock_pipeline_res = {
        "question": "Show top 5 artists",
        "title": "Top 5 Artists by Album Count",
        "status": "SUCCESS",
        "final_sql": "SELECT Name FROM Artist LIMIT 5;",
        "code": "SELECT Name FROM Artist LIMIT 5;",
        "code_type": "sql",
        "data": [{"Name": "AC/DC"}, {"Name": "Accept"}],
        "columns": ["Name"],
        "summary": "Retrieved top 5 artists from database.",
        "confidence_score": 0.95,
        "is_accurate": True,
        "attempts": 1,
        "latency_ms": 120,
        "sub_queries": [],
        "needed_tables": [],
        "available_tables": ["Artist", "Album"],
        "suggested_questions": [],
    }

    with patch("backend.src.api.chat_routes.run_pipeline", return_value=mock_pipeline_res) as mock_run:
        req = QueryRequest(
            question="Show top 5 artists",
            db_id="chinook",
            target_language="sql"
        )
        res = execute_query_data(
            chat_id="test-session-flow",
            payload=req,
            file_path=temp_chat_file
        )

        # Verify pipeline was called with proper args
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["question"] == "Show top 5 artists"
        assert call_kwargs["db_id"] == "chinook"
        assert call_kwargs["target_language"] == "sql"

        # Verify returned response fields
        assert res["role"] == "assistant"
        assert res["title"] == "Top 5 Artists by Album Count"
        assert res["sql"] == "SELECT Name FROM Artist LIMIT 5;"
        assert len(res["data"]) == 2
        assert res["status"] == "SUCCESS"
        assert res["telemetry"]["confidence_score"] == 0.95
        assert res["telemetry"]["attempts"] == 1
        assert res["telemetry"]["db_id"] == "chinook"
        assert res["code_type"] == "sql"

        # Verify session was created and contains 2 messages (user + assistant)
        session = list_chats_data(file_path=temp_chat_file)["chats"][0]
        assert session["id"] == "test-session-flow"
        assert len(session["messages"]) == 2
        assert session["messages"][0]["role"] == "user"
        assert session["messages"][0]["content"] == "Show top 5 artists"
        assert session["messages"][1]["role"] == "assistant"
        assert session["messages"][1]["sql"] == "SELECT Name FROM Artist LIMIT 5;"


def test_execute_query_stateless_individual_turns(temp_chat_file):
    """
    Verify multi-turn query execution treats each prompt individually without
    passing prior conversation turns to run_pipeline (eliminating token turn penalty).
    """
    mock_res_1 = {
        "question": "What is the highest invoice?",
        "title": "Highest Invoice",
        "status": "SUCCESS",
        "final_sql": "SELECT MAX(Total) FROM Invoice;",
        "data": [{"MAX(Total)": 25.86}],
        "summary": "Max invoice total is 25.86.",
        "confidence_score": 1.0,
        "attempts": 1,
        "latency_ms": 90,
    }

    mock_res_2 = {
        "question": "Who was the customer for it?",
        "title": "Customer for Highest Invoice",
        "status": "SUCCESS",
        "final_sql": "SELECT c.FirstName, c.LastName FROM Customer c JOIN Invoice i ON c.CustomerId = i.CustomerId WHERE i.Total = 25.86;",
        "data": [{"FirstName": "Helena", "LastName": "Holý"}],
        "summary": "The customer was Helena Holý.",
        "confidence_score": 0.92,
        "attempts": 1,
        "latency_ms": 110,
    }

    with patch("backend.src.api.chat_routes.run_pipeline") as mock_run:
        mock_run.side_effect = [mock_res_1, mock_res_2]

        req1 = QueryRequest(question="What is the highest invoice?")
        execute_query_data(chat_id="multi-turn-chat", payload=req1, file_path=temp_chat_file)

        req2 = QueryRequest(question="Who was the customer for it?")
        execute_query_data(chat_id="multi-turn-chat", payload=req2, file_path=temp_chat_file)

        assert mock_run.call_count == 2
        # Verify both turns were invoked independently without prior conversation context
        first_call_kwargs = mock_run.call_args_list[0][1]
        assert first_call_kwargs.get("history") is None

        second_call_kwargs = mock_run.call_args_list[1][1]
        assert second_call_kwargs.get("history") is None

        # Verify chat history persistence still records all turns for the UI session
        session = list_chats_data(file_path=temp_chat_file)["chats"][0]
        assert session["id"] == "multi-turn-chat"
        assert len(session["messages"]) == 4  # Turn 1 (user+assistant) + Turn 2 (user+assistant)


# ==============================================================================
# Adapter & Router Integrity Tests
# ==============================================================================
def test_chat_controller_adapter_parity(temp_chat_file):
    """Verify ChatController static adapter delegates accurately to service helpers."""
    req = CreateChatRequest(id="adapter-session", title="Adapter Title")
    chat = ChatController.create_chat(req, file_path=temp_chat_file)
    assert chat["id"] == "adapter-session"

    chats = ChatController.list_chats(file_path=temp_chat_file)
    assert len(chats["chats"]) == 1

    langs = ChatController.get_supported_languages("chinook")
    assert langs["db_type"] == "sql"

    del_res = ChatController.delete_chat("adapter-session", file_path=temp_chat_file)
    assert del_res["success"] is True


def test_router_endpoints_registered():
    """Verify all 7 expected route paths are defined on router."""
    routes = [r.path for r in router.routes]
    assert "/chats" in routes
    assert "/chats/{chat_id}" in routes
    assert "/chats/{chat_id}/query" in routes
    assert "/chats/convert-code" in routes
    assert "/chats/languages/{db_id}" in routes


# ==============================================================================
# One Dataset Per Conversation Enforcement Tests
# ==============================================================================
def test_create_chat_with_dataset_persists(temp_chat_file):
    """Verify creating a session explicitly records db_id and db_name."""
    req = CreateChatRequest(id="session-nosql-01", title="Store Inventory", db_id="ecommerce_store")
    created = create_chat_session_data(req, file_path=temp_chat_file)

    assert created["id"] == "session-nosql-01"
    assert created["db_id"] == "ecommerce_store"
    assert "E-Commerce" in created["db_name"]

    listed = list_chats_data(file_path=temp_chat_file)
    assert len(listed["chats"]) == 1
    assert listed["chats"][0]["db_id"] == "ecommerce_store"


def test_one_dataset_per_conversation_enforced_in_query(temp_chat_file):
    """
    Verify strict 1-Dataset-Per-Conversation invariant:
    If a chat session is bound to 'chinook', any subsequent query payload with a
    different db_id (e.g. 'ecommerce_store') MUST be overridden to use 'chinook'.
    """
    mock_res = {
        "question": "Show tracks",
        "title": "Track Listing",
        "status": "SUCCESS",
        "final_sql": "SELECT * FROM Track LIMIT 5;",
        "code_type": "sql",
        "data": [{"TrackId": 1}],
        "summary": "Tracks returned.",
        "confidence_score": 0.9,
        "attempts": 1,
        "latency_ms": 100,
        "sub_queries": [],
        "needed_tables": [],
        "available_tables": ["Track"],
        "suggested_questions": [],
    }

    # 1. Create chat bound to chinook
    create_req = CreateChatRequest(id="session-strict-chinook", title="Music Chat", db_id="chinook")
    create_chat_session_data(create_req, file_path=temp_chat_file)

    with patch("backend.src.api.chat_routes.run_pipeline", return_value=mock_res) as mock_run:
        # 2. Try to query with a DIFFERENT dataset (ecommerce_store)
        query_req = QueryRequest(
            question="Show tracks",
            db_id="ecommerce_store",  # Attempt to switch dataset within existing conversation
            target_language="sql"
        )
        res = execute_query_data(
            chat_id="session-strict-chinook",
            payload=query_req,
            file_path=temp_chat_file
        )

        # 3. Assert run_pipeline was called with chinook (NOT ecommerce_store)
        mock_run.assert_called_once()
        assert mock_run.call_args[1]["db_id"] == "chinook"

        # 4. Assert response telemetry reflects chinook
        assert res["db_id"] == "chinook"
        assert res["telemetry"]["db_id"] == "chinook"


def test_update_chat_dataset_allowed_for_empty_chat(temp_chat_file):
    """Verify an empty conversation (0 messages) can update its dataset."""
    create_req = CreateChatRequest(id="session-empty", title="New Conversation", db_id="chinook")
    create_chat_session_data(create_req, file_path=temp_chat_file)

    # Update dataset before any messages exist
    upd = UpdateChatRequest(db_id="sales_performance")
    res = update_chat_title_data(chat_id="session-empty", payload=upd, file_path=temp_chat_file)

    assert res["success"] is True
    assert res["db_id"] == "sales_performance"

    listed = list_chats_data(file_path=temp_chat_file)
    assert listed["chats"][0]["db_id"] == "sales_performance"


def test_update_chat_dataset_rejected_once_messages_exist(temp_chat_file):
    """Verify attempting to change dataset on a conversation with messages is rejected (HTTP 400)."""
    # 1. Create chat
    create_req = CreateChatRequest(id="session-locked", title="Music Analysis", db_id="chinook")
    create_chat_session_data(create_req, file_path=temp_chat_file)

    # 2. Add a message to make it non-empty
    from backend.src.storage.chat_store import append_chat_message
    append_chat_message(
        chat_id="session-locked",
        message_id="msg-1",
        role="user",
        content="What is top artist?",
        file_path=temp_chat_file
    )

    # 3. Attempt to change dataset should raise HTTPException 400
    upd = UpdateChatRequest(db_id="ecommerce_store")
    with pytest.raises(HTTPException) as exc_info:
        update_chat_title_data(chat_id="session-locked", payload=upd, file_path=temp_chat_file)

    assert exc_info.value.status_code == 400
    assert "Cannot change dataset" in exc_info.value.detail


