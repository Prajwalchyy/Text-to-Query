"""
Main Application Entrypoint & API Bootstrap.
Enterprise Text-to-SQL API (v2.0)

Mounts modular routers from the pure functional API layer (src.api.databases_routes
and src.api.chat_routes), configures CORS, handles lifecycle initialization,
and exposes health monitoring and OpenAPI documentation.
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ==============================================================================
# Path Resolution & Environment Bootstrap
# ==============================================================================
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
SRC_DIR = BACKEND_DIR / "src"
for p in [str(PROJECT_ROOT), str(BACKEND_DIR), str(SRC_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Storage & Directory Initialization
try:
    from config import ensure_directories
except ImportError:
    from backend.config import ensure_directories

# API Layer Routers & Schemas
try:
    from src.api.databases_routes import router as databases_router
    from src.api.chat_routes import router as chat_router
    from src.api.schemas import HealthResponse
except ImportError:
    try:
        from backend.src.api.databases_routes import router as databases_router
        from backend.src.api.chat_routes import router as chat_router
        from backend.src.api.schemas import HealthResponse
    except ImportError:
        from api.databases_routes import router as databases_router
        from api.chat_routes import router as chat_router
        from api.schemas import HealthResponse

# Backward compatibility alias for legacy imports
database_router = databases_router


# ==============================================================================
# Lifespan Hook
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown hooks."""
    ensure_directories()
    yield


# ==============================================================================
# FastAPI Application & Bootstrap Configuration
# ==============================================================================
app = FastAPI(
    title="Enterprise Text-to-SQL API",
    description="Multi-Database Text-to-SQL API with dynamic upload, AST guardrails, and persistent chat sessions",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS Configuration for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Modular Routers under /api
app.include_router(databases_router, prefix="/api")
app.include_router(chat_router, prefix="/api")


# ==============================================================================
# Health Check Endpoint
# ==============================================================================
@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
def health_check() -> HealthResponse:
    """Health check endpoint to verify API connectivity and service status."""
    return HealthResponse(
        status="healthy",
        service="Enterprise Text-to-SQL API",
        version="2.0.0",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
