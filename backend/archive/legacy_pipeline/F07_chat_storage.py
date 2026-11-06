import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
JSON_PATH = DATA_DIR / "chat_history.json"

class ChatStorage:
    """
    Manages persistent conversational chat history using a structured JSON file.
    All sessions, user questions, AI responses, SQL queries, and telemetry are
    stored in human-readable JSON.
    """
    def __init__(self, file_path: Path = JSON_PATH):
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_storage()

    def _init_storage(self):
        """Initializes the JSON file if it does not already exist."""
        if self.file_path.exists() == False:
            self._write_data([])

    def _read_data(self) -> List[Dict[str, Any]]:
        """Reads and parses the JSON chat history."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content == "":
                    return []
                return json.loads(content)
        except (json.JSONDecodeError, OSError):
            return []

    def _write_data(self, data: List[Dict[str, Any]]) -> None:
        """Safely writes chat history to the JSON file with formatting."""
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def list_chats(self) -> List[Dict[str, Any]]:
        """Returns all chat sessions ordered with newest first."""
        return self._read_data()

    def create_chat(self, chat_id: str, title: str = "New Conversation") -> Dict[str, Any]:
        """Creates and persists a new conversation session."""
        chats = self._read_data()
        
        # Avoid duplicate creation if chat_id already exists
        for chat in chats:
            if chat["id"] == chat_id:
                return chat

        new_chat = {
            "id": chat_id,
            "title": title,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "messages": []
        }
        
        # Place newest chat at the beginning
        chats.insert(0, new_chat)
        self._write_data(chats)
        return new_chat

    def update_chat_title(self, chat_id: str, title: str) -> bool:
        """Updates the conversation title (e.g. from the first prompt)."""
        chats = self._read_data()
        for chat in chats:
            if chat["id"] == chat_id:
                chat["title"] = title
                self._write_data(chats)
                return True
        return False

    def delete_chat(self, chat_id: str) -> bool:
        """Deletes a conversation session from the JSON file."""
        chats = self._read_data()
        initial_count = len(chats)
        chats = [c for c in chats if c["id"] != chat_id]
        if len(chats) < initial_count:
            self._write_data(chats)
            return True
        return False

    def add_message(
        self,
        chat_id: str,
        message_id: str,
        role: str,
        content: str,
        sql: Optional[str] = None,
        data: Optional[List[Dict]] = None,
        telemetry: Optional[Dict] = None,
        status: str = "SUCCESS",
        sub_queries: Optional[List[Dict]] = None,
        needed_tables: Optional[List[str]] = None,
        available_tables: Optional[List[str]] = None,
        suggested_questions: Optional[List[str]] = None,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Appends a new message to the specified conversation session in JSON."""
        chats = self._read_data()
        target_chat = next((c for c in chats if c["id"] == chat_id), None)

        if target_chat == None:
            # Auto-create chat if not found
            target_chat = {
                "id": chat_id,
                "title": content[:32],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "messages": []
            }
            chats.insert(0, target_chat)

        new_message = {
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
        self._write_data(chats)
        return new_message

    def get_conversation_context(self, chat_id: str, limit: int = 4) -> List[Dict[str, Any]]:
        """
        Retrieves the last `limit` completed turns (user question + assistant query/summary)
        for feeding as conversational context / memory to the LLM generator.
        """
        chats = self._read_data()
        target_chat = next((c for c in chats if c["id"] == chat_id), None)
        if not target_chat or not target_chat.get("messages"):
            return []

        # Get last limit * 2 messages (pairs of user/assistant)
        recent_messages = target_chat["messages"][-(limit * 2):]
        context_turns = []
        for msg in recent_messages:
            context_turns.append({
                "role": msg.get("role"),
                "content": msg.get("content", ""),
                "sql": msg.get("sql"),
                "status": msg.get("status", "SUCCESS")
            })
        return context_turns
