"""
KumoRFM Demo — FastAPI backend.

Startup sequence:
  1. Load .env (ANTHROPIC_API_KEY)
  2. Seed database if it doesn't exist
  3. Load or build the NetworkX graph
  4. Serve REST endpoints

Usage:
  cd backend
  uvicorn main:app --reload
  uvicorn main:app --reload -- --rebuild-graph   # force graph rebuild
"""

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables from .env before anything else
load_dotenv(Path(__file__).parent / ".env", override=True)

from data.db import get_connection, DB_PATH
from data.seed import seed, DB_PATH as SEED_DB_PATH
from data.seed import SCHEMA_PATH
from graph.builder import load_or_build_graph
from pql.executor import execute
from llm.claude import generate_pql, summarize_results, get_client
from models.schemas import (
    ChatRequest,
    ChatResponse,
    SchemaResponse,
    SchemaTable,
    GraphStatsResponse,
    TraversalStep,
)

import networkx as nx

# Global graph instance (loaded at startup)
G: nx.DiGraph | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global G

    # Validate API key early so startup fails loudly if missing
    try:
        get_client()
    except RuntimeError as e:
        print(f"\n[ERROR] {e}\n")
        sys.exit(1)

    # Seed database if it doesn't exist
    if not DB_PATH.exists():
        print("Database not found — seeding...")
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = __import__("sqlite3").Row
        seed(conn)
        conn.close()

    # Load or build graph
    conn = get_connection()
    G = load_or_build_graph(conn)
    conn.close()

    yield  # app runs here

    G = None


app = FastAPI(
    title="KumoRFM Demo",
    description="Relational Predictive Analytics via graph-native multi-hop traversal",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Main chat endpoint.

    1. Claude converts NL question → PQL
    2. Executor runs PQL against the graph
    3. Claude summarizes results in plain English
    """
    if G is None:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    # Step 1: NL → PQL
    history = [{"role": m.role, "content": m.content} for m in request.history]
    try:
        pql_query = generate_pql(request.message, history)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error (PQL generation): {e}")

    # Step 2: Execute PQL against graph
    try:
        exec_result = execute(G, pql_query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {e}")

    results = exec_result["results"]
    traversal_steps_raw = exec_result.get("traversal_steps", [])

    # Step 3: Summarize results
    try:
        summary = summarize_results(
            question=request.message,
            pql_query=pql_query,
            results=results,
            traversal_steps=traversal_steps_raw,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error (summarization): {e}")

    traversal_steps = [
        TraversalStep(**s) for s in traversal_steps_raw
    ]

    return ChatResponse(
        pql_query=pql_query,
        query_type=exec_result["query_type"],
        results=results,
        traversal_steps=traversal_steps,
        summary=summary,
        columns=exec_result["columns"],
        total_results=exec_result["total_results"],
    )


@app.get("/api/schema", response_model=SchemaResponse)
async def get_schema() -> SchemaResponse:
    """Return table names, columns, and foreign key relationships."""
    conn = get_connection()
    tables = []

    for table_name in ["customers", "products", "orders", "order_items", "interactions", "campaign_touchpoints"]:
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        columns = [row["name"] for row in cursor.fetchall()]

        cursor = conn.execute(f"PRAGMA foreign_key_list({table_name})")
        fks = [
            {"from": row["from"], "to_table": row["table"], "to_col": row["to"]}
            for row in cursor.fetchall()
        ]
        tables.append(SchemaTable(name=table_name, columns=columns, foreign_keys=fks))

    conn.close()
    return SchemaResponse(tables=tables)


@app.get("/api/graph/stats", response_model=GraphStatsResponse)
async def graph_stats() -> GraphStatsResponse:
    """Return graph node/edge counts to prove the graph is real."""
    if G is None:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    node_types: dict[str, int] = {}
    for _, attrs in G.nodes(data=True):
        nt = attrs.get("node_type", "unknown")
        node_types[nt] = node_types.get(nt, 0) + 1

    edge_types: dict[str, int] = {}
    for _, _, attrs in G.edges(data=True):
        et = attrs.get("edge_type", "unknown")
        edge_types[et] = edge_types.get(et, 0) + 1

    return GraphStatsResponse(
        node_count=G.number_of_nodes(),
        edge_count=G.number_of_edges(),
        node_types=node_types,
        edge_types=edge_types,
    )


@app.get("/api/graph/data")
async def graph_data(limit: int = 200) -> dict:
    """Return graph nodes and edges for visualization (limited for performance)."""
    if G is None:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    # Prioritize customers and products, then include their related nodes
    priority_types = ["customer", "product", "order"]
    nodes = []
    seen_nodes = set()

    for node_id, attrs in G.nodes(data=True):
        node_type = attrs.get("node_type", "unknown")
        if node_type in priority_types and len(nodes) < limit:
            label = attrs.get("name") or attrs.get("customer_id") or attrs.get("product_id") or attrs.get("order_id") or node_id
            nodes.append({
                "id": node_id,
                "label": str(label),
                "type": node_type,
            })
            seen_nodes.add(node_id)

    # Include edges only between nodes we have
    edges = []
    for source, target, attrs in G.edges(data=True):
        if source in seen_nodes and target in seen_nodes:
            edges.append({
                "source": source,
                "target": target,
                "type": attrs.get("edge_type", "unknown"),
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
    }


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "graph_loaded": G is not None}
