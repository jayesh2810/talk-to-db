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

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from dotenv import load_dotenv

# Load environment variables from .env before anything else
load_dotenv(Path(__file__).parent / ".env", override=True)

from data.db import get_connection, DB_PATH
from data.seed import seed, DB_PATH as SEED_DB_PATH
from data.seed import SCHEMA_PATH
from graph.builder import load_or_build_graph
from graph.traversal import collect_churn_signals
from prediction.engine import score_churn
from pql.executor import execute, _apply_filters
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

security = HTTPBasic()

async def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify admin credentials from the database."""
    from data.db import get_connection
    conn = get_connection()
    user = conn.execute(
        "SELECT 1 FROM admin WHERE user_id = ? AND password = ?", 
        (credentials.username, credentials.password)
    ).fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(
            status_code=401, 
            detail="Incorrect username or password", 
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


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
async def chat(request: ChatRequest, user: str = Depends(get_current_user)) -> ChatResponse:
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


@app.post("/api/compare")
async def compare(request: ChatRequest, user: str = Depends(get_current_user)):
    """
    Compare Graph-native predictive scoring vs flat SQL scoring.
    Currently only supports churn_probability.
    """
    if G is None:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    # 1. NL → PQL
    history = [{"role": m.role, "content": m.content} for m in request.history]
    try:
        pql_query = generate_pql(request.message, history)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error (PQL generation): {e}")

    # 2. Execute PQL to check type and get candidates
    try:
        exec_result = execute(G, pql_query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {e}")

    if exec_result["query_type"] != "predictive":
        raise HTTPException(status_code=400, detail="Comparison only available for predictive queries")
    
    # check if it's churn_probability (we can check pql_query or execute_result)
    # pql_query usually contains PREDICT churn_probability
    if "churn_probability" not in pql_query.lower():
        raise HTTPException(status_code=400, detail="Comparison only available for churn_probability queries")

    # 3. Compute Graph vs SQL scores for ALL matching customers
    # We reuse the logic from _run_churn in executor.py
    from pql.parser import parse_pql
    plan = parse_pql(pql_query)
    filters = plan.get("filters", [])

    customer_nodes = [
        n for n, attrs in G.nodes(data=True)
        if attrs.get("node_type") == "customer"
        and _apply_filters(attrs, filters)
    ]

    graph_scores = []

    sql_scores = []

    for node in customer_nodes:
        name = G.nodes[node].get("name", "Unknown")
        signals, _ = collect_churn_signals(G, node)
        
        g_score, _, _ = score_churn(signals, sql_mode=False)
        s_score, _, _ = score_churn(signals, sql_mode=True)
        
        graph_scores.append({"name": name, "score": g_score})
        sql_scores.append({"name": name, "score": s_score})

    # Sort and Rank
    graph_scores.sort(key=lambda x: x["score"], reverse=True)
    sql_scores.sort(key=lambda x: x["score"], reverse=True)

    for i, item in enumerate(graph_scores):
        item["rank"] = i + 1
    for i, item in enumerate(sql_scores):
        item["rank"] = i + 1

    # Compute Deltas
    graph_rank_map = {item["name"]: item["rank"] for item in graph_scores}
    sql_rank_map = {item["name"]: item["rank"] for item in sql_scores}
    graph_score_map = {item["name"]: item["score"] for item in graph_scores}
    sql_score_map = {item["name"]: item["score"] for item in sql_scores}

    deltas = []
    for name in graph_rank_map:
        g_rank = graph_rank_map[name]
        s_rank = sql_rank_map[name]
        rank_change = s_rank - g_rank # Positive if graph is higher (better risk detection)
        
        if abs(rank_change) >= 1:
            deltas.append({
                "name": name,
                "graph_rank": g_rank,
                "sql_rank": s_rank,
                "rank_change": rank_change,
                "score_delta": round(graph_score_map[name] - sql_score_map[name], 3)
            })

    deltas.sort(key=lambda x: abs(x["rank_change"]), reverse=True)

    # 4. Summary
    try:
        summary = summarize_results(
            question=request.message,
            pql_query=pql_query,
            results=graph_scores,
            traversal_steps=[],
        )
    except Exception:
        summary = "Comparison results generated."

    return {
        "graph_results": graph_scores,
        "sql_results": sql_scores,
        "deltas": deltas,
        "pql_query": pql_query,
        "summary": summary
    }

@app.get("/api/schema", response_model=SchemaResponse)
async def get_schema(user: str = Depends(get_current_user)) -> SchemaResponse:
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
async def graph_stats(user: str = Depends(get_current_user)) -> GraphStatsResponse:
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
async def graph_data(
    limit: int = 200,
    user: str = Depends(get_current_user),
) -> dict:
    """Return graph nodes and edges for visualization (limited for performance)."""
    if G is None:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    priority_types = ["customer", "product", "order"]
    nodes = []
    seen_nodes = set()

    for nid, attrs in G.nodes(data=True):
        node_type = attrs.get("node_type", "unknown")
        if node_type in priority_types and len(nodes) < limit:
            label = attrs.get("name") or attrs.get("customer_id") or attrs.get("product_id") or attrs.get("order_id") or nid
            nodes.append({
                "id": nid,
                "label": str(label),
                "type": node_type,
            })
            seen_nodes.add(nid)

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


@app.get("/api/customer/{customer_id}")
async def get_customer_profile(customer_id: str, user: str = Depends(get_current_user)):
    """
    Fetch a complete customer profile and churn risk from the graph.
    """
    node_id = f"customer:{customer_id}"
    if G is None:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    if node_id not in G.nodes:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer_node = G.nodes[node_id]
    if customer_node.get("node_type") != "customer":
        raise HTTPException(status_code=400, detail="Node is not a customer")

    profile = {
        "id": customer_id,
        "name": customer_node.get("name", ""),
        "segment": customer_node.get("segment", ""),
        "city": customer_node.get("city", ""),
        "lifetime_value": customer_node.get("lifetime_value", 0),
        "signup_date": customer_node.get("signup_date", ""),
        "acq_channel": customer_node.get("acq_channel", ""),
    }

    orders = []
    order_nodes = [n for n in G.successors(node_id) if G.nodes[n].get("node_type") == "order"]
    order_nodes.sort(key=lambda n: G.nodes[n].get("order_date", ""), reverse=True)

    for on in order_nodes:
        o_attrs = G.nodes[on]
        items = []
        for pn in G.successors(on):
            if G.nodes[pn].get("node_type") == "product":
                p_attrs = G.nodes[pn]
                edge_attrs = G.edges[on, pn]
                items.append({
                    "product_name": p_attrs.get("name", ""),
                    "category": p_attrs.get("category", ""),
                    "quantity": edge_attrs.get("quantity", 1),
                    "unit_price": edge_attrs.get("unit_price", 0.0),
                    "returned": edge_attrs.get("returned", False),
                })

        orders.append({
            "order_id": on,
            "order_date": o_attrs.get("order_date", ""),
            "total_amount": o_attrs.get("total_amount", 0),
            "status": o_attrs.get("status", ""),
            "delivery_days": o_attrs.get("delivery_days", 0),
            "promised_days": o_attrs.get("promised_days", 0),
            "items": items,
        })

    interactions = []
    interaction_nodes = [n for n in G.successors(node_id) if G.nodes[n].get("node_type") == "interaction"]
    interaction_nodes.sort(key=lambda n: G.nodes[n].get("date", ""), reverse=True)
    for in_node in interaction_nodes:
        i_attrs = G.nodes[in_node]
        interactions.append({
            "date": i_attrs.get("date", ""),
            "channel": i_attrs.get("channel", ""),
            "topic": i_attrs.get("topic", ""),
            "sentiment": i_attrs.get("sentiment", ""),
            "resolved": i_attrs.get("resolved", False),
            "resolution_hours": i_attrs.get("resolution_hours", 0),
        })

    campaigns = []
    campaign_nodes = [n for n in G.successors(node_id) if G.nodes[n].get("node_type") == "campaign"]
    campaign_nodes.sort(key=lambda n: G.nodes[n].get("sent_date", ""), reverse=True)
    for cn in campaign_nodes:
        c_attrs = G.nodes[cn]
        campaigns.append({
            "campaign_name": c_attrs.get("campaign_name", ""),
            "campaign_type": c_attrs.get("campaign_type", ""),
            "sent_date": c_attrs.get("sent_date", ""),
            "opened": c_attrs.get("opened", False),
            "clicked": c_attrs.get("clicked", False),
            "converted": c_attrs.get("converted", False),
        })

    raw_signals, _ = collect_churn_signals(G, node_id)
    score, confidence, factors = score_churn(raw_signals)

    return {
        "profile": profile,
        "orders": orders,
        "interactions": interactions,
        "campaigns": campaigns,
        "churn": {
            "score": score,
            "confidence": confidence,
            "top_factors": factors,
            "raw_signals": raw_signals,
        },
    }


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "graph_loaded": G is not None}
