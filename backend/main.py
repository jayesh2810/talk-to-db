"""
Talk-to-DB FastAPI backend.

Startup:
  1. Load .env (API keys + optional BASIC_AUTH_*)
  2. Load the Kumo relational model bundle (cached parquet, LocalGraph pickle, model)

Analytics data is only the Kumo online-shopping dataset (users/items/orders parquet).
HTTP Basic login uses environment variables; no SQLite.

Usage:
  cd backend
  uvicorn main:app --reload
  uvicorn main:app --reload -- --rebuild-rfm-graph   # rebuild LocalGraph pickle
"""

import ipaddress
import os
import secrets
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import httpx

load_dotenv(Path(__file__).parent / ".env", override=True)

from agent.workflow import handle_goal_message
from llm.claude import generate_pql, get_client, summarize_results
from models.schemas import (
    ChatRequest,
    ChatResponse,
    GraphStatsResponse,
    SchemaResponse,
    SchemaTable,
    TraversalStep,
    WebhookRequest,
)
from pql.executor import execute
from rfm.cache import RFMBundle, load_rfm_bundle

RFM_BUNDLE: RFMBundle | None = None

security = HTTPBasic()


def _basic_expected() -> tuple[str, str]:
    return (
        os.environ.get("BASIC_AUTH_USER", "1028@admin"),
        os.environ.get("BASIC_AUTH_PASSWORD", "1028@admin"),
    )


def _basic_auth_ok(username: str, password: str) -> bool:
    u, p = _basic_expected()
    return secrets.compare_digest(username, u) and secrets.compare_digest(password, p)


async def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify HTTP Basic credentials from environment (see BASIC_AUTH_* in .env.example)."""
    if not _basic_auth_ok(credentials.username, credentials.password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def _init_kumo_model() -> None:
    import kumoai.experimental.rfm as rfm

    if not os.environ.get("KUMO_API_KEY"):
        raise RuntimeError(
            "KUMO_API_KEY is not set. Add it to backend/.env."
        )
    rfm.init()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global RFM_BUNDLE

    try:
        get_client()
    except RuntimeError as e:
        print(f"\n[ERROR] {e}\n")
        sys.exit(1)

    try:
        _init_kumo_model()
    except RuntimeError as e:
        print(f"\n[ERROR] {e}\n")
        sys.exit(1)

    rebuild_rfm = "--rebuild-rfm-graph" in sys.argv
    if rebuild_rfm:
        print("Rebuilding Kumo LocalGraph from cached parquet (--rebuild-rfm-graph).")

    print("Loading Kumo relational model bundle (S3 parquet cache + LocalGraph pickle)...")
    RFM_BUNDLE = load_rfm_bundle(force_rebuild_graph=rebuild_rfm)
    print("Kumo relational model ready.")

    yield

    RFM_BUNDLE = None


app = FastAPI(
    title="Talk-to-DB",
    description="Natural language interface for relational predictive analytics",
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
async def chat(request: ChatRequest, user: str = Depends(get_current_user)) -> ChatResponse:
    if RFM_BUNDLE is None:
        raise HTTPException(status_code=503, detail="Kumo relational model bundle not initialized")

    goal_response = handle_goal_message(user, request.message, RFM_BUNDLE)
    if goal_response is not None:
        return ChatResponse(
            mode=goal_response.get("mode", "agent_goal"),
            summary=goal_response.get("summary", ""),
            query_type=goal_response.get("query_type", "agent_goal"),
            workflow_id=goal_response.get("workflow_id"),
            stage=goal_response.get("stage"),
            pending_approval=goal_response.get("pending_approval"),
            proposal=goal_response.get("proposal"),
            execution_summary=goal_response.get("execution_summary"),
            agent_logs=goal_response.get("agent_logs", []),
        )

    history = [{"role": m.role, "content": m.content} for m in request.history]

    try:
        pql_query = generate_pql(request.message, history)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error (PQL generation): {e}")

    try:
        exec_result = execute(pql_query, RFM_BUNDLE)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {e}")

    results = exec_result["results"]
    traversal_steps_raw = exec_result.get("traversal_steps", [])

    try:
        summary = summarize_results(
            question=request.message,
            pql_query=pql_query,
            results=results,
            traversal_steps=traversal_steps_raw,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error (summarization): {e}")

    traversal_steps = [TraversalStep(**s) for s in traversal_steps_raw]

    return ChatResponse(
        mode="standard",
        pql_query=pql_query,
        query_type=exec_result["query_type"],
        results=results,
        traversal_steps=traversal_steps,
        summary=summary,
        columns=exec_result["columns"],
        total_results=exec_result["total_results"],
    )


# ── Schema endpoint ─────────────────────────────────────────────────────

@app.get("/api/schema", response_model=SchemaResponse)
async def get_schema(user: str = Depends(get_current_user)) -> SchemaResponse:
    if RFM_BUNDLE is None:
        raise HTTPException(status_code=503, detail="Kumo relational model bundle not initialized")

    b = RFM_BUNDLE
    tables = [
        SchemaTable(name="users", columns=list(b.users.columns), foreign_keys=[]),
        SchemaTable(name="items", columns=list(b.items.columns), foreign_keys=[]),
        SchemaTable(
            name="orders",
            columns=list(b.orders.columns),
            foreign_keys=[
                {"from": "user_id", "to_table": "users", "to_col": "user_id"},
                {"from": "item_id", "to_table": "items", "to_col": "item_id"},
            ],
        ),
    ]
    return SchemaResponse(tables=tables)


# ── Graph endpoints ─────────────────────────────────────────────────────

@app.get("/api/graph/stats", response_model=GraphStatsResponse)
async def graph_stats(user: str = Depends(get_current_user)) -> GraphStatsResponse:
    if RFM_BUNDLE is None:
        raise HTTPException(status_code=503, detail="Kumo relational model bundle not initialized")

    from rfm.viz import graph_stats as gs

    raw = gs(RFM_BUNDLE)
    return GraphStatsResponse(
        node_count=raw["node_count"],
        edge_count=raw["edge_count"],
        node_types=raw["node_types"],
        edge_types=raw["edge_types"],
    )


@app.get("/api/graph/data")
async def graph_data(limit: int = 200, user: str = Depends(get_current_user)) -> dict:
    if RFM_BUNDLE is None:
        raise HTTPException(status_code=503, detail="Kumo relational model bundle not initialized")

    from rfm.viz import graph_sample

    return graph_sample(RFM_BUNDLE, limit=min(max(limit, 1), 500))


# ── User deep-dive endpoint ──────────────────────────────────────────────

@app.get("/api/user/{user_id}")
@app.get("/api/customer/{user_id}")
async def get_user_detail(user_id: str, user: str = Depends(get_current_user)):
    """
    Fetch a user profile, recent orders, and a churn prediction.
    Powers the CustomerDrawer in the frontend.
    Accessible via both /api/user/{id} and /api/customer/{id}.
    """
    if RFM_BUNDLE is None:
        raise HTTPException(status_code=503, detail="Kumo relational model bundle not initialized")

    from rfm.user_profile import build_user_profile

    try:
        return build_user_profile(RFM_BUNDLE, user_id)
    except ValueError as e:
        msg = str(e).lower()
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=str(e)) from e
        raise HTTPException(status_code=400, detail=str(e)) from e


# ── Health ───────────────────────────────────────────────────────────────

def _webhook_allowed_hosts() -> set[str]:
    raw = os.environ.get("WEBHOOK_ALLOWED_HOSTS", "")
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def _validate_webhook_url(url: str) -> None:
    """Reject anything that isn't an http(s) URL pointing at an allow-listed
    public host. Closes the SSRF that this proxy used to be."""
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid webhook URL: {e}") from e

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Webhook URL must use http or https")

    host = (parsed.hostname or "").lower()
    if not host:
        raise HTTPException(status_code=400, detail="Webhook URL missing host")

    # Block raw IP literals pointing at private / loopback / link-local ranges
    # so an allow-listed name can't be bypassed via http://127.0.0.1.
    try:
        ip = ipaddress.ip_address(host)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise HTTPException(
                status_code=403,
                detail="Webhook URL cannot target private/loopback IPs",
            )
    except ValueError:
        pass  # not a raw IP literal — fall through to the host allow-list

    allowed = _webhook_allowed_hosts()
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="Webhook proxy is disabled. Set WEBHOOK_ALLOWED_HOSTS in .env to enable it.",
        )
    if host not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Webhook host '{host}' is not allow-listed (see WEBHOOK_ALLOWED_HOSTS).",
        )


@app.post("/api/webhook/send", response_model=dict)
async def send_webhook(request: WebhookRequest, user: str = Depends(get_current_user)):
    """Proxy a payload to an allow-listed external webhook URL."""
    _validate_webhook_url(request.webhook_url)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                request.webhook_url,
                json=request.payload,
                timeout=10.0,
                follow_redirects=False,
            )
            response.raise_for_status()
            return {"status": "success", "response": response.text}
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Webhook returned error: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Webhook failed: {e}")


@app.get("/api/health")
async def health(
    credentials: HTTPBasicCredentials | None = Depends(HTTPBasic(auto_error=False)),
) -> dict:
    """Health check; validates Basic credentials when the client sends them (login probe)."""
    out: dict = {"status": "ok", "model_ready": RFM_BUNDLE is not None}
    if credentials is not None:
        out["authenticated"] = _basic_auth_ok(credentials.username, credentials.password)
    else:
        out["authenticated"] = False
    return out
