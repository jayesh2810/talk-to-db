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
    pql_query: str
    query_type: str  # "factual" | "predictive"
    results: list[dict[str, Any]]
    traversal_steps: list[TraversalStep] = []
    summary: str
    columns: list[str]
    total_results: int


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
