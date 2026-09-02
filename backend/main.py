import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add backend/src to Python path
SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from routes.database_routes import router as database_router
from routes.chat_routes import router as chat_router

# ==============================================================================
# FastAPI Application & Bootstrap Configuration
# ==============================================================================
app = FastAPI(
    title="Enterprise Text-to-SQL API",
    description="Multi-Database Text-to-SQL API with dynamic upload, AST guardrails, and persistent chat sessions",
    version="2.0.0",
)

# CORS Configuration for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Modular Routers under /api
app.include_router(database_router, prefix="/api")
app.include_router(chat_router, prefix="/api")


# Health Check
@app.get("/api/health")
def health_check():
    """Health check endpoint to verify API connectivity."""
    return {"status": "healthy", "service": "Enterprise Text-to-SQL API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
