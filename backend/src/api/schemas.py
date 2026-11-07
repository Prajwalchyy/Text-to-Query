"""
Pydantic API Schemas & Data Transfer Objects (DTOs)
Enterprise Text-to-SQL API (v2.0)

Pure data contract definitions for HTTP request parsing, input validation,
and OpenAPI response serialization across chat and dataset endpoints.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ==============================================================================
# Common Base Config
# ==============================================================================
class ApiBaseModel(BaseModel):
    """Base model permitting extra fields for forward-compatible deserialization."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# ==============================================================================
# Chat & Conversation Request Models
# ==============================================================================
class CreateChatRequest(ApiBaseModel):
    """Payload for creating a new conversational chat session."""
    id: str = Field(..., description="Unique chat identifier")
    title: Optional[str] = Field(default="New Conversation", description="Display title for the chat")
    db_id: Optional[str] = Field(default=None, description="Associated data source identifier")
    db_name: Optional[str] = Field(default=None, description="Display name for associated data source")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Chat ID cannot be blank.")
        return v.strip()

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> str:
        if not v or not v.strip():
            return "New Conversation"
        return v.strip()

    @field_validator("db_id")
    @classmethod
    def validate_db_id(cls, v: Optional[str]) -> Optional[str]:
        if not v or not v.strip():
            return None
        return v.strip()


class UpdateChatRequest(ApiBaseModel):
    """Payload for updating a chat session's title or dataset."""
    title: Optional[str] = Field(default=None, description="New display title")
    db_id: Optional[str] = Field(default=None, description="New dataset identifier (only allowed if 0 messages)")
    db_name: Optional[str] = Field(default=None, description="New dataset display name")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Title cannot be empty.")
        return v.strip() if v is not None else None


class QueryRequest(ApiBaseModel):
    """Payload for executing a natural language question against a data source."""
    question: str = Field(..., description="Natural language prompt or query")
    db_id: Optional[str] = Field(default="chinook", description="Target data source identifier")
    target_language: Optional[str] = Field(
        default=None, 
        description="Target dialect/code type (e.g. sql, pandas, nosql, excel_formula, r)"
    )

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Question cannot be empty.")
        return v.strip()

    @field_validator("db_id")
    @classmethod
    def validate_db_id(cls, v: Optional[str]) -> str:
        if not v or not v.strip():
            return "chinook"
        return v.strip()

    @field_validator("target_language")
    @classmethod
    def validate_target_language(cls, v: Optional[str]) -> Optional[str]:
        if not v or not v.strip():
            return None
        return v.strip().lower()


class ConvertCodeRequest(ApiBaseModel):
    """Payload for translating code or queries across supported languages."""
    code: str = Field(..., description="Source code or query string to convert")
    from_language: str = Field(..., description="Source programming language or dialect")
    to_language: Optional[str] = Field(default=None, description="Target programming language or dialect")
    target_language: Optional[str] = Field(default=None, description="Alias for target programming language")
    db_id: Optional[str] = Field(default="chinook", description="Associated data source identifier")

    @model_validator(mode="before")
    @classmethod
    def resolve_target_language(cls, data: Any) -> Any:
        if isinstance(data, dict):
            target = data.get("to_language") or data.get("target_language")
            if target:
                data["to_language"] = target
                data["target_language"] = target
        return data

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Code cannot be empty.")
        return v.strip()

    @field_validator("from_language")
    @classmethod
    def validate_from_language(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Language cannot be empty.")
        return v.strip().lower()

    @field_validator("to_language")
    @classmethod
    def validate_to_language(cls, v: Optional[str]) -> str:
        if not v or not v.strip():
            raise ValueError("Target language cannot be empty.")
        return v.strip().lower()

    @field_validator("db_id")
    @classmethod
    def validate_db_id(cls, v: Optional[str]) -> str:
        if not v or not v.strip():
            return "chinook"
        return v.strip()


# ==============================================================================
# Database Upload & Append Request Form Models
# ==============================================================================
class DatabaseUploadForm(ApiBaseModel):
    """Form parameters for dataset uploads."""
    name: Optional[str] = Field(default="", description="Display name for custom database")
    type: Optional[str] = Field(default=None, description="Dataset type: sql, nosql, csv, excel")
    mode: str = Field(default="full", description="Upload mode: single dataset file")
    group_name: Optional[str] = Field(default=None, description="Optional legacy group name")


class AppendTableForm(ApiBaseModel):
    """Form parameters for appending a SQL table script."""
    overwrite: bool = Field(default=False, description="Whether to overwrite existing table")


class AppendCollectionForm(ApiBaseModel):
    """Form parameters for appending a NoSQL collection."""
    overwrite: bool = Field(default=False, description="Whether to overwrite existing collection")


# ==============================================================================
# Pipeline & Chat Execution Response Models
# ==============================================================================
class TelemetryDetail(ApiBaseModel):
    """Pipeline execution telemetry and performance metrics."""
    confidence_score: float = Field(default=0.0, description="Semantic evaluation confidence 0.0-1.0")
    latency_ms: int = Field(default=0, description="Total pipeline latency in milliseconds")
    attempts: int = Field(default=1, description="Number of execution / reflection attempts")
    status: str = Field(default="SUCCESS", description="Execution status: SUCCESS, FAILED, OOD")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    db_id: str = Field(default="chinook", description="Data source identifier")
    db_name: str = Field(default="Default", description="Data source display name")
    db_type: str = Field(default="sql", description="Data source type (sql, nosql, csv, excel)")
    code_type: Optional[str] = Field(default=None, description="Resulting code type (sql, pandas, excel_formula, mql, etc.)")
    needed_tables: List[str] = Field(default_factory=list, description="Tables identified in question")
    available_tables: List[str] = Field(default_factory=list, description="Available tables in data source")
    suggested_questions: List[str] = Field(default_factory=list, description="Suggested valid questions if OOD")


class SubQueryDetail(ApiBaseModel):
    """Individual sub-task result when handling compound questions."""
    title: Optional[str] = Field(default=None, description="Sub-task title or description")
    sql: Optional[str] = Field(default=None, description="Generated SQL statement")
    mql: Optional[Any] = Field(default=None, description="Generated MQL pipeline")
    code: Optional[str] = Field(default=None, description="Generated Pandas / Python code")
    formula: Optional[str] = Field(default=None, description="Generated Excel formula")
    data: Optional[List[Dict[str, Any]]] = Field(default=None, description="Execution result rows")
    status: str = Field(default="SUCCESS", description="Execution status of this sub-query")
    error: Optional[str] = Field(default=None, description="Error message if sub-task failed")


class QueryExecutionResponse(ApiBaseModel):
    """Assistant message payload returned after query pipeline execution."""
    id: str = Field(..., description="Assistant message identifier (epoch ms)")
    role: str = Field(default="assistant", description="Message role (assistant)")
    title: Optional[str] = Field(default=None, description="Short title describing query")
    content: str = Field(default="", description="Natural language summary or explanation")
    sql: Optional[str] = Field(default=None, description="Generated query or code block")
    data: Optional[List[Dict[str, Any]]] = Field(default=None, description="Query execution tabular data")
    sub_queries: Optional[List[Dict[str, Any]]] = Field(default=None, description="Sub-query results if compound")
    telemetry: Optional[Dict[str, Any]] = Field(default=None, description="Execution telemetry metrics")
    status: str = Field(default="SUCCESS", description="Overall execution status")
    needed_tables: List[str] = Field(default_factory=list, description="Required tables extracted from prompt")
    available_tables: List[str] = Field(default_factory=list, description="Data source tables")
    suggested_questions: List[str] = Field(default_factory=list, description="Domain suggestions if OOD")
    db_name: Optional[str] = Field(default="Default", description="Data source display name")
    db_type: Optional[str] = Field(default="sql", description="Data source type")
    code_type: Optional[str] = Field(default=None, description="Language/code dialect")


class ChatMessageItem(ApiBaseModel):
    """Single message entry in conversation history."""
    id: str = Field(..., description="Message identifier")
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(default="", description="Text content or natural language explanation")
    title: Optional[str] = Field(default=None, description="Message or query title")
    sql: Optional[str] = Field(default=None, description="Generated query/code")
    data: Optional[List[Dict[str, Any]]] = Field(default=None, description="Result rows")
    sub_queries: Optional[List[Dict[str, Any]]] = Field(default=None, description="Compound query sub-tasks")
    telemetry: Optional[Dict[str, Any]] = Field(default=None, description="Telemetry metadata")
    status: Optional[str] = Field(default="SUCCESS", description="Execution status")
    needed_tables: List[str] = Field(default_factory=list)
    available_tables: List[str] = Field(default_factory=list)
    suggested_questions: List[str] = Field(default_factory=list)
    timestamp: Optional[str] = Field(default=None)


class ChatSessionDetail(ApiBaseModel):
    """Complete conversational session including all message turns."""
    id: str = Field(..., description="Session identifier")
    title: str = Field(..., description="Session title")
    db_id: Optional[str] = Field(default="chinook", description="Associated dataset identifier")
    db_name: Optional[str] = Field(default=None, description="Associated dataset display name")
    created_at: Optional[str] = Field(default=None, description="Creation ISO timestamp")
    updated_at: Optional[str] = Field(default=None, description="Last update ISO timestamp")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="List of messages")


class ChatsListResponse(ApiBaseModel):
    """Response payload for GET /api/chats."""
    chats: List[Dict[str, Any]] = Field(default_factory=list, description="All chat sessions")


class GenericActionResponse(ApiBaseModel):
    """Generic status response for CRUD actions."""
    success: bool = Field(default=True, description="Whether action succeeded")
    chat_id: Optional[str] = Field(default=None, description="Affected chat identifier")
    title: Optional[str] = Field(default=None, description="Updated title")
    message: Optional[str] = Field(default=None, description="Informational message")


class CodeConversionResponse(ApiBaseModel):
    """Response payload for POST /api/chats/convert-code."""
    code: str = Field(..., description="Converted code snippet")
    from_language: str = Field(..., description="Source language")
    to_language: str = Field(..., description="Target language")
    language_name: str = Field(..., description="Display name of target language")
    badge_color: str = Field(..., description="Hex or Tailwind color for language badge")
    extension: str = Field(..., description="File extension")
    note: Optional[str] = Field(default=None, description="Syntax or compatibility note")


class LanguageOption(ApiBaseModel):
    """Language descriptor in supported languages catalog."""
    id: str = Field(..., description="Language identifier")
    name: str = Field(..., description="Display name")
    badge_color: Optional[str] = Field(default=None, description="UI badge color")
    extension: Optional[str] = Field(default=None, description="File extension")
    prism_language: Optional[str] = Field(default=None, description="Prism/syntax highlight identifier")


class SupportedLanguagesResponse(ApiBaseModel):
    """Response payload for GET /api/chats/languages/{db_id}."""
    db_id: str = Field(..., description="Data source identifier")
    db_type: str = Field(..., description="Data source type")
    languages: List[Dict[str, Any]] = Field(default_factory=list, description="Supported languages")


# ==============================================================================
# Database & Schema Response Models
# ==============================================================================
class ColumnDetail(ApiBaseModel):
    """Column metadata for a database table or collection."""
    name: str = Field(..., description="Column or property name")
    type: str = Field(..., description="Data type representation")
    is_pk: bool = Field(default=False, description="Is Primary Key")
    is_fk: bool = Field(default=False, description="Is Foreign Key")
    fk_to_table: Optional[str] = Field(default=None, description="Target table if FK")
    fk_to_col: Optional[str] = Field(default=None, description="Target column if FK")
    display: str = Field(..., description="Formatted display string with badges")


class TableSchemaItem(ApiBaseModel):
    """Table or collection schema with columns and sample count."""
    name: str = Field(..., description="Table or collection name")
    cols: List[str] = Field(default_factory=list, description="List of display column strings")
    columns: List[ColumnDetail] = Field(default_factory=list, description="Detailed column models")
    count: Optional[int] = Field(default=None, description="Record or document count")


class RelationshipItem(ApiBaseModel):
    """Foreign key or join relationship between tables."""
    from_table: str = Field(..., description="Source table")
    from_column: str = Field(..., description="Source foreign key column")
    to_table: str = Field(..., description="Target primary key table")
    to_column: str = Field(..., description="Target primary key column")


class TablesSchemaResponse(ApiBaseModel):
    """Response payload for GET /api/tables."""
    db_id: str = Field(..., description="Data source identifier")
    type: str = Field(..., description="Data source type: sql, nosql, csv, excel")
    tables: List[TableSchemaItem] = Field(default_factory=list, description="List of table schemas")
    relationships: List[RelationshipItem] = Field(default_factory=list, description="Relationships")


class DatabaseRecord(ApiBaseModel):
    """Registered database metadata entry."""
    id: str = Field(..., description="Unique database identifier")
    name: str = Field(..., description="Display name")
    type: str = Field(..., description="Database type: sql, nosql, csv, excel")
    path: str = Field(..., description="Absolute or relative file path")
    filename: Optional[str] = Field(default=None, description="Original filename")
    upload_mode: Optional[str] = Field(default=None, description="Upload mode: single or multiple")
    group_name: Optional[str] = Field(default=None, description="Bulk group folder name")
    created_at: Optional[str] = Field(default=None, description="Registration timestamp")
    is_default: Optional[bool] = Field(default=False, description="System default dataset flag")
    tables: Optional[List[str]] = Field(default=None, description="Optional table names list")


class DatabasesListResponse(ApiBaseModel):
    """Response payload for GET /api/databases."""
    databases: List[DatabaseRecord] = Field(default_factory=list, description="List of all registered databases")


class ConflictDetail(ApiBaseModel):
    """Conflict error payload when table or collection already exists."""
    conflict: bool = Field(default=True, description="Conflict flag")
    type: str = Field(..., description="Target type: table or collection")
    target: str = Field(..., description="Target database identifier")
    conflicts: List[str] = Field(default_factory=list, description="Conflicting table/collection names")
    message: str = Field(..., description="Explanatory conflict message")


class HealthResponse(ApiBaseModel):
    """Health check response for GET /api/health."""
    status: str = Field(default="healthy", description="Service health status")
    service: str = Field(default="Enterprise Text-to-SQL API", description="Service name")
    version: Optional[str] = Field(default="2.0.0", description="API Version")

