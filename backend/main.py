"""
Talk-to-DB — FastAPI backend powered by KumoRFM.

Startup sequence:
  1. Load .env (ANTHROPIC_API_KEY, KUMO_API_KEY)
  2. Load e-commerce Parquet (local cache if present, else S3 → cache)
  3. Init KumoRFM (restores from local model pickle if data unchanged, else materialize)
  4. Serve REST endpoints

Usage:
  cd backend
  uvicorn main:app --reload
"""

import sys
import traceback
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

from kumo_rfm.client import init_model, get_schema_info, get_dataframes
from kumo_rfm.executor import execute
from llm.claude import generate_pql, summarize_results, get_client
from pql.parser import parse_pql
from models.schemas import ChatRequest, ChatResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate API keys early
    try:
        get_client()
    except RuntimeError as e:
        print(f"\n[ERROR] {e}\n")
        sys.exit(1)

    try:
        init_model()
    except RuntimeError as e:
        print(f"\n[ERROR] {e}\n")
        sys.exit(1)

    yield


app = FastAPI(
    title="Talk-to-DB",
    description="KumoRFM-powered natural language database interface",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Chat endpoint ─────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """
    NL → PQL → KumoRFM prediction or pandas lookup → Claude summary.
    """
    history = [{"role": m.role, "content": m.content} for m in req.history]

    # Step 1: NL → PQL
    try:
        pql_query = generate_pql(req.message, history)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    # Step 2: Parse PQL
    try:
        plan = parse_pql(pql_query)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"PQL parse error: {e}")

    # Step 3: Execute
    try:
        result = execute(pql_query, plan)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Execution error: {e}")

    # Step 4: Summarize
    try:
        summary = summarize_results(req.message, pql_query, result["results"])
    except Exception as e:
        summary = f"Query executed successfully. {result['total_results']} results returned."

    return ChatResponse(
        pql_query=pql_query,
        query_type=result["query_type"],
        results=result["results"],
        summary=summary,
        columns=result["columns"],
        total_results=result["total_results"],
    )


# ── Schema endpoint ─────────────────────────────────────────────────────

@app.get("/api/schema")
async def schema() -> dict:
    """Return metadata about the loaded e-commerce tables."""
    return get_schema_info()


# ── Health ───────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health() -> dict:
    """Health check."""
    try:
        dfs = get_dataframes()
        return {
            "status": "ok",
            "tables": list(dfs.keys()),
            "total_rows": sum(len(df) for df in dfs.values()),
        }
    except Exception:
        return {"status": "ok", "tables": [], "total_rows": 0}
