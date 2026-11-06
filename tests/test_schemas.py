"""
Unit Tests for Pydantic API Schemas & DTOs
Phase D Step D.1 Verification
"""

import pytest
from pydantic import ValidationError

from backend.src.api.schemas import (
    CreateChatRequest,
    UpdateChatRequest,
    QueryRequest,
    ConvertCodeRequest,
    DatabaseUploadForm,
    AppendTableForm,
    AppendCollectionForm,
    TelemetryDetail,
    SubQueryDetail,
    QueryExecutionResponse,
    ChatMessageItem,
    ChatSessionDetail,
    ChatsListResponse,
    GenericActionResponse,
    CodeConversionResponse,
    LanguageOption,
    SupportedLanguagesResponse,
    ColumnDetail,
    TableSchemaItem,
    RelationshipItem,
    TablesSchemaResponse,
    DatabaseRecord,
    DatabasesListResponse,
    ConflictDetail,
    HealthResponse,
)


def test_create_chat_request_valid():
    """Verify CreateChatRequest instantiates with valid parameters and defaults."""
    req = CreateChatRequest(id="chat-123")
    assert req.id == "chat-123"
    assert req.title == "New Conversation"

    req_custom = CreateChatRequest(id="  chat-456  ", title="  Custom Analysis  ")
    assert req_custom.id == "chat-456"
    assert req_custom.title == "Custom Analysis"


def test_create_chat_request_invalid_id():
    """Verify CreateChatRequest rejects blank or whitespace IDs."""
    with pytest.raises(ValidationError):
        CreateChatRequest(id="")

    with pytest.raises(ValidationError):
        CreateChatRequest(id="   ")


def test_create_chat_request_empty_title_fallback():
    """Verify CreateChatRequest falls back to default when title is empty string."""
    req = CreateChatRequest(id="chat-1", title="")
    assert req.title == "New Conversation"

    req_spaces = CreateChatRequest(id="chat-2", title="   ")
    assert req_spaces.title == "New Conversation"


def test_update_chat_request_valid():
    """Verify UpdateChatRequest trims title."""
    req = UpdateChatRequest(title="  Renamed Session  ")
    assert req.title == "Renamed Session"


def test_update_chat_request_empty_title():
    """Verify UpdateChatRequest rejects empty or whitespace title."""
    with pytest.raises(ValidationError):
        UpdateChatRequest(title="")

    with pytest.raises(ValidationError):
        UpdateChatRequest(title="   ")


def test_query_request_valid_and_defaults():
    """Verify QueryRequest handles valid question and populates default fields."""
    req = QueryRequest(question="  Show top 5 tracks  ")
    assert req.question == "Show top 5 tracks"
    assert req.db_id == "chinook"
    assert req.target_language is None

    req_custom = QueryRequest(
        question="Find customer orders",
        db_id="ecommerce",
        target_language="pandas"
    )
    assert req_custom.question == "Find customer orders"
    assert req_custom.db_id == "ecommerce"
    assert req_custom.target_language == "pandas"


def test_query_request_empty_question():
    """Verify QueryRequest raises ValidationError for blank questions."""
    with pytest.raises(ValidationError):
        QueryRequest(question="")

    with pytest.raises(ValidationError):
        QueryRequest(question="    ")


def test_query_request_empty_optional_fields_fallback():
    """Verify QueryRequest falls back to defaults if empty strings provided."""
    req = QueryRequest(question="Test query", db_id="", target_language="")
    assert req.db_id == "chinook"
    assert req.target_language is None


def test_convert_code_request_valid():
    """Verify ConvertCodeRequest handles valid parameters."""
    req = ConvertCodeRequest(
        code="SELECT * FROM Customer",
        from_language="SQL",
        to_language="Pandas",
        db_id="chinook"
    )
    assert req.code == "SELECT * FROM Customer"
    assert req.from_language == "sql"
    assert req.to_language == "pandas"
    assert req.db_id == "chinook"


def test_convert_code_request_validation_errors():
    """Verify ConvertCodeRequest requires non-empty code and languages."""
    with pytest.raises(ValidationError):
        ConvertCodeRequest(code="", from_language="sql", to_language="pandas")

    with pytest.raises(ValidationError):
        ConvertCodeRequest(code="SELECT 1", from_language="", to_language="pandas")

    with pytest.raises(ValidationError):
        ConvertCodeRequest(code="SELECT 1", from_language="sql", to_language="")


def test_telemetry_and_query_response_serialization():
    """Verify TelemetryDetail and QueryExecutionResponse serialization."""
    telemetry = TelemetryDetail(
        confidence_score=0.95,
        latency_ms=120,
        attempts=1,
        status="SUCCESS",
        db_id="chinook",
        db_type="sql"
    )
    assert telemetry.confidence_score == 0.95
    assert telemetry.latency_ms == 120

    resp = QueryExecutionResponse(
        id="1730000000",
        role="assistant",
        title="Top Customers",
        content="Here are the top customers.",
        sql="SELECT * FROM Customer LIMIT 5;",
        data=[{"CustomerId": 1, "Name": "Alice"}],
        telemetry=telemetry.model_dump(),
        status="SUCCESS"
    )
    dumped = resp.model_dump()
    assert dumped["id"] == "1730000000"
    assert dumped["role"] == "assistant"
    assert dumped["telemetry"]["confidence_score"] == 0.95
    assert len(dumped["data"]) == 1


def test_databases_and_schema_response():
    """Verify TableSchemaItem, TablesSchemaResponse and DatabasesListResponse."""
    col = ColumnDetail(
        name="CustomerId",
        type="INTEGER",
        is_pk=True,
        display="CustomerId (INTEGER) 🔑 PK"
    )
    table = TableSchemaItem(
        name="Customer",
        cols=[col.display],
        columns=[col],
        count=59
    )
    schema_resp = TablesSchemaResponse(
        db_id="chinook",
        type="sql",
        tables=[table],
        relationships=[]
    )
    assert schema_resp.tables[0].name == "Customer"
    assert schema_resp.tables[0].columns[0].is_pk is True

    db_rec = DatabaseRecord(
        id="chinook",
        name="Chinook Music Store",
        type="sql",
        path="/data/chinook.db",
        is_default=True
    )
    list_resp = DatabasesListResponse(databases=[db_rec])
    assert len(list_resp.databases) == 1
    assert list_resp.databases[0].id == "chinook"


def test_extra_fields_ignored_gracefully():
    """Verify that forward-compatible extra fields from client/storage are safely ignored."""
    req = QueryRequest(
        question="How many tracks?",
        unknown_metadata_field="ignored",
        extra_client_param=999
    )
    assert req.question == "How many tracks?"
    assert not hasattr(req, "unknown_metadata_field")

