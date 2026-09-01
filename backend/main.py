import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add backend/src to Python path so pipeline modules are found
SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from F06_pipeline import TextToSQLPipeline

# ==============================================================================
# FastAPI Application & CORS Configuration
# ==============================================================================
app = FastAPI(
    title="Enterprise Text-to-SQL API",
    description="Backend API with 4-layer guardrails, self-correction, and hallucination scoring",
    version="1.0.0",
)

# Allow React frontend (Vite running on localhost:5173 or 5174) to communicate
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

# Initialize the master Text-to-SQL pipeline instance
pipeline = TextToSQLPipeline()


# ==============================================================================
# Request & Response Models
# ==============================================================================
class QueryRequest(BaseModel):
    question: str


# ==============================================================================
# API Endpoints
# ==============================================================================
@app.get("/api/health")
def health_check():
    """Health check endpoint to verify API and database connectivity."""
    return {"status": "healthy", "service": "Text-to-SQL Pipeline API"}


@app.get("/api/tables")
def get_tables():
    """Returns live database tables and their schema for the React sidebar."""
    try:
        table_names = pipeline.db_engine.get_table_names()
        schema_data = []
        for table in table_names:
            cols = pipeline.db_engine.get_table_schema(table)
            col_list = [f"{c['name']} ({c['type']})" for c in cols]
            schema_data.append({"name": table, "cols": col_list})
        return {"tables": schema_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database introspection failed: {str(e)}")


@app.post("/api/query")
def execute_query(payload: QueryRequest):
    """
    Executes the full Text-to-SQL pipeline:
    1. SQL Generation
    2. 4-Layer Guardrail Validation
    3. Safe Database Execution & Self-Correction
    4. Hallucination Detection & Executive Summary
    """
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        result = pipeline.run_pipeline(payload.question)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline execution error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
