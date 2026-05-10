"""
Anthropic Claude API integration.

Two calls per user message:
  1. NL → PQL: generate the query from natural language
  2. Results → Summary: write plain English from query results
"""

import os
from typing import Any

import anthropic

from llm.prompts import (
    PQL_GENERATION_SYSTEM,
    SUMMARIZATION_SYSTEM,
    build_summarization_message,
)

_client: anthropic.Anthropic | None = None

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS_PQL = 512
MAX_TOKENS_SUMMARY = 512


def get_client() -> anthropic.Anthropic:
    """Return a cached Anthropic client, failing fast if key is missing."""
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to backend/.env before starting the server."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def generate_pql(
    question: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    """
    Call Claude to translate a natural language question into PQL.

    Returns a PQL query string (either PREDICT ... FOR or MATCH ...).
    """
    client = get_client()

    messages = []
    if history:
        for msg in history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": question})

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS_PQL,
        system=PQL_GENERATION_SYSTEM,
        messages=messages,
    )

    return response.content[0].text.strip()


def summarize_results(
    question: str,
    pql_query: str,
    results: list[dict[str, Any]],
) -> str:
    """
    Call Claude to write a plain English summary of query results.
    """
    client = get_client()

    user_message = build_summarization_message(question, pql_query, results)

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS_SUMMARY,
        system=SUMMARIZATION_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text.strip()
