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

import pandas as pd
from kumo_rfm.client import init_model, get_schema_info, get_dataframes, predict
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


# ── User deep-dive endpoint ──────────────────────────────────────────────

@app.get("/api/user/{user_id}")
async def get_user_profile(user_id: int) -> dict:
    """
    Fetch a user profile, their recent orders, and a KumoRFM churn prediction.
    Powers the CustomerDrawer in the frontend.
    """
    dfs = get_dataframes()
    users_df = dfs.get("users", pd.DataFrame())
    orders_df = dfs.get("orders", pd.DataFrame())
    items_df = dfs.get("items", pd.DataFrame())

    user_rows = users_df[users_df["user_id"] == user_id].to_dict(orient="records")
    if not user_rows:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    user = user_rows[0]

    # Join orders with item names for this user
    user_orders: list[dict] = []
    if not orders_df.empty and "user_id" in orders_df.columns:
        uorders = orders_df[orders_df["user_id"] == user_id].copy()
        if not items_df.empty and "item_id" in items_df.columns:
            uorders = uorders.merge(
                items_df[["item_id", "item_name", "category"]],
                on="item_id",
                how="left",
            )
        uorders = uorders.sort_values("date", ascending=False).head(15)
        for _, row in uorders.iterrows():
            user_orders.append({
                "order_id": int(row.get("order_id", 0)),
                "item_id": int(row.get("item_id", 0)),
                "item_name": str(row.get("item_name", f"Item #{row.get('item_id', '?')}")),
                "category": str(row.get("category", "")),
                "date": str(row.get("date", ""))[:10],
                "price": round(float(row.get("price", 0)), 2),
            })

    # KumoRFM 90-day churn prediction for this user
    churn_score = None
    try:
        pql = f"PREDICT COUNT(orders.*, 0, 90, days)=0 FOR users.user_id={user_id}"
        pred_df = predict(pql)
        if isinstance(pred_df, pd.DataFrame) and len(pred_df) > 0:
            score_cols = [c for c in pred_df.columns if c != "user_id"]
            if score_cols:
                churn_score = round(float(pred_df.iloc[0][score_cols[0]]), 4)
    except Exception as exc:
        print(f"[user_profile] Churn prediction failed for user {user_id}: {exc}")

    return {
        "profile": {
            "user_id": user_id,
            "active": bool(user.get("active", True)),
            "age": int(user["age"]) if pd.notna(user.get("age")) else None,
        },
        "churn_score": churn_score,
        "orders": user_orders,
    }


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
