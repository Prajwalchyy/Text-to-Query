"""
Unit Tests for backend/main.py Application Bootstrap & Modular Router Cutover (Step D.4).
Enterprise Text-to-SQL API (v2.0)

Validates FastAPI application instance, CORS middleware configurations, OpenAPI
specification generation, all mounted modular route paths (/api/databases, /api/chats, /api/health),
pure functional health check endpoint handler, and backward-compatible route aliases.
"""

import sys
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure project root and backend are on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
for p in [str(PROJECT_ROOT), str(BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.main import (
    app,
    health_check,
    databases_router,
    chat_router,
    database_router,
    HealthResponse,
)


def test_app_instance_metadata():
    """Verify FastAPI application metadata, title, version, and description."""
    assert isinstance(app, FastAPI)
    assert app.title == "Enterprise Text-to-SQL API"
    assert app.version == "2.0.0"
    assert "Multi-Database Text-to-SQL API" in app.description


def test_pure_functional_health_check_handler():
    """Verify health_check() returns valid HealthResponse schema."""
    resp = health_check()
    assert isinstance(resp, HealthResponse)
    assert resp.status == "healthy"
    assert resp.service == "Enterprise Text-to-SQL API"
    assert resp.version == "2.0.0"

    # Also test dict serialization compatibility
    resp_dict = resp.model_dump()
    assert resp_dict["status"] == "healthy"
    assert resp_dict["service"] == "Enterprise Text-to-SQL API"
    assert resp_dict["version"] == "2.0.0"


def test_cors_middleware_configuration():
    """Verify CORS middleware is registered with correct allowed origins and headers."""
    cors_middlewares = [
        m for m in app.user_middleware
        if issubclass(m.cls, CORSMiddleware)
    ]
    assert len(cors_middlewares) >= 1

    cors_kwargs = cors_middlewares[0].kwargs
    allow_origins = cors_kwargs.get("allow_origins", [])
    assert "http://localhost:5173" in allow_origins
    assert "http://127.0.0.1:5173" in allow_origins
    assert "http://localhost:5174" in allow_origins
    assert "http://127.0.0.1:5174" in allow_origins
    assert cors_kwargs.get("allow_credentials") is True
    assert cors_kwargs.get("allow_methods") == ["*"]
    assert cors_kwargs.get("allow_headers") == ["*"]


def test_openapi_schema_contains_all_mounted_routes():
    """Verify OpenAPI JSON schema includes all cutover routes across databases, chats, and health."""
    schema = app.openapi()
    assert schema["info"]["title"] == "Enterprise Text-to-SQL API"
    assert schema["info"]["version"] == "2.0.0"

    paths = schema.get("paths", {})

    # Health check route
    assert "/api/health" in paths
    assert "get" in paths["/api/health"]

    # Modular Databases routes
    assert "/api/databases" in paths
    assert "get" in paths["/api/databases"]
    assert "/api/databases/upload" in paths
    assert "post" in paths["/api/databases/upload"]
    assert "/api/databases/{db_id}/append-table" in paths
    assert "post" in paths["/api/databases/{db_id}/append-table"]
    assert "/api/databases/{db_id}/append-collection" in paths
    assert "post" in paths["/api/databases/{db_id}/append-collection"]
    assert "/api/databases/{db_id}" in paths
    assert "delete" in paths["/api/databases/{db_id}"]
    assert "/api/tables" in paths
    assert "get" in paths["/api/tables"]

    # Modular Chats routes
    assert "/api/chats" in paths
    assert "get" in paths["/api/chats"]
    assert "post" in paths["/api/chats"]
    assert "/api/chats/{chat_id}" in paths
    assert "patch" in paths["/api/chats/{chat_id}"]
    assert "delete" in paths["/api/chats/{chat_id}"]
    assert "/api/chats/{chat_id}/query" in paths
    assert "post" in paths["/api/chats/{chat_id}/query"]
    assert "/api/chats/convert-code" in paths
    assert "post" in paths["/api/chats/convert-code"]
    assert "/api/chats/languages/{db_id}" in paths
    assert "get" in paths["/api/chats/languages/{db_id}"]


def test_router_integration_and_included_routes():
    """Verify that both databases_router and chat_router routes are integrated into the application."""
    # Check that both routers contain their registered routes
    db_route_paths = [r.path for r in databases_router.routes]
    chat_route_paths = [r.path for r in chat_router.routes]

    assert "/databases" in db_route_paths
    assert "/tables" in db_route_paths
    assert "/databases/upload" in db_route_paths
    assert "/databases/{db_id}" in db_route_paths

    assert "/chats" in chat_route_paths
    assert "/chats/{chat_id}" in chat_route_paths
    assert "/chats/{chat_id}/query" in chat_route_paths
    assert "/chats/convert-code" in chat_route_paths
    assert "/chats/languages/{db_id}" in chat_route_paths

    # Verify that the app's OpenAPI path set contains the full prefixed endpoints
    openapi_paths = set(app.openapi().get("paths", {}).keys())
    for db_path in db_route_paths:
        assert f"/api{db_path}" in openapi_paths
    for chat_path in chat_route_paths:
        assert f"/api{chat_path}" in openapi_paths


def test_backward_compatibility_aliases():
    """Verify database_router alias matches databases_router for legacy consumers."""
    assert database_router is databases_router
    assert databases_router is not None
    assert chat_router is not None
