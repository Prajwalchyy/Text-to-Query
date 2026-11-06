"""
Unit Tests for Conversational Memory Window Manager (Step C.6).
Verifies extract_memory_window, has_pronoun_reference, format_context_for_prompt,
and get_chat_memory_window.
"""

import tempfile
from pathlib import Path
import pytest
from backend.src.pipelines.context import (
    extract_memory_window,
    has_pronoun_reference,
    format_context_for_prompt,
    get_chat_memory_window,
)
from backend.src.storage.chat_store import (
    create_chat_session,
    append_chat_message,
)


def test_extract_memory_window_empty_and_invalid():
    assert extract_memory_window(None) == []
    assert extract_memory_window([]) == []
    assert extract_memory_window("invalid_type") == []
    assert extract_memory_window([{"role": "user", "content": "hi"}], limit=0) == []
    assert extract_memory_window([{"role": "user", "content": "hi"}], limit=-1) == []


def test_extract_memory_window_slicing():
    # 10 messages (5 turns)
    messages = [
        {"role": "user", "content": f"Question {i}", "id": f"q_{i}"}
        if i % 2 == 0
        else {"role": "assistant", "content": f"Answer {i}", "sql": f"SELECT {i};", "id": f"a_{i}"}
        for i in range(10)
    ]

    # Limit = 2 turns -> last 4 messages (indices 6, 7, 8, 9)
    window_2 = extract_memory_window(messages, limit=2)
    assert len(window_2) == 4
    assert window_2[0]["content"] == "Question 6"
    assert window_2[1]["content"] == "Answer 7"
    assert window_2[2]["content"] == "Question 8"
    assert window_2[3]["content"] == "Answer 9"

    # Limit = 10 -> all 10 messages
    window_all = extract_memory_window(messages, limit=10)
    assert len(window_all) == 10


def test_extract_memory_window_key_normalization():
    messages = [
        {
            "role": "user",
            "content": "Find orders over 500",
        },
        {
            "role": "assistant",
            "content": "Found 12 orders.",
            "mql": 'db.orders.find({"amount": {"$gt": 500}})',
            "summary": "12 high value orders",
            "title": "Orders > 500"
        },
        {
            "role": "user",
            "content": "Now show their categories",
        },
        {
            "role": "assistant",
            "content": "Grouped categories.",
            "code": "result_df = df.groupby('category')['amount'].sum()",
            "status": "SUCCESS"
        }
    ]

    window = extract_memory_window(messages, limit=4)
    assert len(window) == 4

    # Check MQL extraction into sql key
    assert window[1]["sql"] == 'db.orders.find({"amount": {"$gt": 500}})'
    assert window[1]["summary"] == "12 high value orders"
    assert window[1]["title"] == "Orders > 500"

    # Check code extraction into sql key
    assert window[3]["sql"] == "result_df = df.groupby('category')['amount'].sum()"
    assert window[3]["status"] == "SUCCESS"


def test_has_pronoun_reference():
    # True positives (pronouns, demonstratives, refinements)
    assert has_pronoun_reference("What is their total spending?") is True
    assert has_pronoun_reference("Show only those from Canada") is True
    assert has_pronoun_reference("Now sort by invoice date") is True
    assert has_pronoun_reference("Show the same ones but with email") is True
    assert has_pronoun_reference("What was its highest price?") is True
    assert has_pronoun_reference("Include them in the report too") is True
    assert has_pronoun_reference("Show the first one only") is True

    # True negatives (independent standalone questions)
    assert has_pronoun_reference("List all customers in France") is False
    assert has_pronoun_reference("How many total tracks are in the database?") is False
    assert has_pronoun_reference("Who are the top 5 artists by sales?") is False
    assert has_pronoun_reference("") is False


def test_format_context_for_prompt():
    messages = [
        {"role": "user", "content": "List top customers"},
        {"role": "assistant", "sql": "SELECT * FROM Customer LIMIT 5;", "content": "Top 5 customers."}
    ]

    context_str = format_context_for_prompt(messages, limit=4, query_label="SQL")
    assert "PREVIOUS CONVERSATION CONTEXT" in context_str
    assert 'User asked: "List top customers"' in context_str
    assert "Generated SQL: SELECT * FROM Customer LIMIT 5;" in context_str
    assert "Answer Summary: Top 5 customers." in context_str

    # Empty messages
    assert format_context_for_prompt([], limit=4) == ""
    assert format_context_for_prompt(None, limit=4) == ""


def test_get_chat_memory_window_integration():
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_file = Path(tmp_dir) / "test_chat.json"

        # Create session
        create_chat_session("session_abc", "Test Chat", temp_file)

        # Append messages
        append_chat_message(
            chat_id="session_abc",
            message_id="m1",
            role="user",
            content="Who bought album 1?",
            file_path=temp_file
        )
        append_chat_message(
            chat_id="session_abc",
            message_id="m2",
            role="assistant",
            content="Customer 12 bought album 1.",
            sql="SELECT CustomerId FROM InvoiceLine WHERE TrackId = 1;",
            file_path=temp_file
        )

        window = get_chat_memory_window("session_abc", limit=2, file_path=temp_file)
        assert len(window) == 2
        assert window[0]["role"] == "user"
        assert window[0]["content"] == "Who bought album 1?"
        assert window[1]["role"] == "assistant"
        assert "SELECT CustomerId" in window[1]["sql"]

        # Unknown session returns empty list
        assert get_chat_memory_window("nonexistent", limit=2, file_path=temp_file) == []

