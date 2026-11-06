"""
Conversational Memory Window Manager.

Extracts, normalizes, and filters multi-turn conversational history
to resolve pronouns, coreferences, and user refinements across
SQL, NoSQL, and Spreadsheet queries.

Pure functional implementation with zero OOP state.
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure backend and project root are discoverable for internal imports
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
for p in [str(PROJECT_ROOT), str(BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from backend.src.pipelines.prompts import format_history_context
except ImportError:
    try:
        from src.pipelines.prompts import format_history_context
    except ImportError:
        from pipelines.prompts import format_history_context


# Coreference and pronoun detection regex
PRONOUN_PATTERN = re.compile(
    r"\b(their|them|they|those|these|that|this|it|its|his|her|hers|"
    r"the same|same ones|first one|second one|last one|previous|prior|"
    r"above|also|too|now sort|now filter|instead|only those|only them)\b",
    re.IGNORECASE
)


def extract_memory_window(
    messages: Optional[List[Dict[str, Any]]],
    limit: int = 4
) -> List[Dict[str, Any]]:
    """
    Extracts the last `limit` conversational turns (pairs of user question + assistant response)
    from a list of chat messages and normalizes each turn into a clean dictionary.

    Args:
        messages: List of raw chat message dictionaries (e.g. from chat_history.json).
        limit: Number of conversational turns to extract (defaults to 4, yielding up to 8 messages).

    Returns:
        List of normalized message dictionaries with consistent keys:
        `role`, `content`, `sql`, `status`, `summary`.
    """
    if not messages or limit <= 0 or not isinstance(messages, list):
        return []

    # Filter for valid dict objects only
    valid_messages = [m for m in messages if isinstance(m, dict)]
    if not valid_messages:
        return []

    # Get the last limit * 2 messages (representing limit turns of user + assistant)
    slice_size = limit * 2
    recent_messages = valid_messages[-slice_size:]

    normalized_turns: List[Dict[str, Any]] = []

    for msg in recent_messages:
        role = (msg.get("role") or "").lower().strip()
        if not role:
            continue

        # Extract query/code across various dialect keys
        query_val = (
            msg.get("sql")
            or msg.get("mql")
            or msg.get("code")
            or msg.get("formula")
            or msg.get("query")
        )

        # Extract summary or explanation
        summary_val = (
            msg.get("summary")
            or msg.get("explanation")
            or ""
        )

        turn: Dict[str, Any] = {
            "role": role,
            "content": (msg.get("content") or "").strip(),
            "sql": str(query_val).strip() if query_val is not None else None,
            "status": msg.get("status", "SUCCESS"),
        }

        if summary_val:
            turn["summary"] = summary_val.strip()

        if msg.get("title"):
            turn["title"] = str(msg["title"]).strip()

        normalized_turns.append(turn)

    return normalized_turns


def has_pronoun_reference(question: str) -> bool:
    """
    Checks if a user question contains pronouns, demonstratives, or relative
    modifiers indicating it relies on previous conversation turns for context.

    Examples:
      - "What is their total spending?" -> True
      - "Now filter for only those from Germany" -> True
      - "Show the same ones but sort by date" -> True
      - "List all tracks in the database" -> False
    """
    if not question:
        return False
    return bool(PRONOUN_PATTERN.search(question))


def format_context_for_prompt(
    messages: Optional[List[Dict[str, Any]]],
    limit: int = 4,
    query_label: str = "Query"
) -> str:
    """
    Extracts the conversational memory window from messages and formats
    it into a standardized text context block suitable for LLM system/user prompts.

    Args:
        messages: List of raw chat messages.
        limit: Max turns to extract.
        query_label: Label for generated queries ("SQL", "MQL Query", "Pandas Code").

    Returns:
        Formatted context string, or empty string if no relevant history.
    """
    window = extract_memory_window(messages, limit=limit)
    if not window:
        return ""
    return format_history_context(window, query_label=query_label)


def get_chat_memory_window(
    chat_id: str,
    limit: int = 4,
    file_path: Optional[Union[Path, str]] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves the memory window for a specific stored chat session by ID.

    Args:
        chat_id: Unique conversation identifier.
        limit: Max turns to extract.
        file_path: Optional path override for chat JSON storage.

    Returns:
        Normalized list of recent message dicts.
    """
    try:
        from backend.src.storage.chat_store import get_chat_session
    except ImportError:
        try:
            from src.storage.chat_store import get_chat_session
        except ImportError:
            from storage.chat_store import get_chat_session
    chat = get_chat_session(chat_id, file_path=file_path)
    if not chat or not chat.get("messages"):
        return []
    return extract_memory_window(chat["messages"], limit=limit)

