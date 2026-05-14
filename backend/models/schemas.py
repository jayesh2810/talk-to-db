"""Pydantic models for API requests and responses."""
from typing import Any
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class TraversalStep(BaseModel):
    step: int
    hop: int
    description: str
    detail: str


class ChatResponse(BaseModel):
    pql_query: str = ""
    query_type: str = "factual"  # "factual" | "predictive" | "agent_goal"
    results: list[dict[str, Any]] = []
    traversal_steps: list[TraversalStep] = []
    summary: str = ""
    columns: list[str] = []
    total_results: int = 0
    mode: str = "standard"  # "standard" | "agent_goal"
    workflow_id: str | None = None
    stage: str | None = None
    pending_approval: str | None = None
    proposal: dict[str, Any] | None = None
    execution_summary: dict[str, Any] | None = None
    agent_logs: list[dict[str, Any]] = []


class SchemaTable(BaseModel):
    name: str
    columns: list[str]
    foreign_keys: list[dict[str, str]]


class SchemaResponse(BaseModel):
    tables: list[SchemaTable]


class GraphStatsResponse(BaseModel):
    node_count: int
    edge_count: int
    node_types: dict[str, int]
    edge_types: dict[str, int]
