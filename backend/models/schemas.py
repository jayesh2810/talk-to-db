"""Pydantic models for API requests and responses."""
from typing import Any
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    pql_query: str
    query_type: str  # "factual" | "predictive"
    results: list[dict[str, Any]]
    summary: str
    columns: list[str]
    total_results: int
