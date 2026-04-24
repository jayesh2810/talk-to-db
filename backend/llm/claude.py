"""
Anthropic Claude API integration.

Two calls per user message:
  1. NL → PQL: generate the query from natural language
  2. Results → Summary: write plain English from query results + traversal steps
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

MODEL = "claude-sonnet-4-6"
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

    Args:
        question: The user's natural language question.
        history: Optional prior messages for context (role/content dicts).

    Returns:
        A PQL query string.
    """
    client = get_client()

    messages = []
    if history:
        for msg in history[-6:]:  # keep last 3 turns for context
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
    traversal_steps: list[dict[str, Any]],
) -> str:
    """
    Call Claude to write a plain English summary of query results.

    Args:
        question: The original user question.
        pql_query: The PQL query that was executed.
        results: The raw result rows.
        traversal_steps: Graph traversal steps (empty for factual queries).

    Returns:
        A 3-5 sentence plain English summary.
    """
    client = get_client()

    user_message = build_summarization_message(question, pql_query, results, traversal_steps)

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS_SUMMARY,
        system=SUMMARIZATION_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text.strip()
