"""
Anthropic Claude API integration.

Two standard calls per user message:
  1. NL -> PQL: generate the query from natural language
  2. Results -> Summary: write plain English from query results

The goal agent also uses ``chat_json`` for strict JSON planning/actions.
"""

import json
import os
import re
from typing import Any

import anthropic

from llm.prompts import (
    PQL_GENERATION_SYSTEM,
    SUMMARIZATION_SYSTEM,
    build_summarization_message,
)

_client: anthropic.Anthropic | None = None

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MAX_TOKENS_PQL = 512
MAX_TOKENS_SUMMARY = 512
MAX_TOKENS_AGENT = 4096


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
    system_prompt: str | None = None,
) -> str:
    """Call Claude to translate a natural language question into PQL.

    ``system_prompt`` lets the caller pass a schema-aware prompt built from
    the live bundle; if omitted, the static fallback is used.
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
        system=system_prompt or PQL_GENERATION_SYSTEM,
        messages=messages,
    )

    return response.content[0].text.strip()


def summarize_results(
    question: str,
    pql_query: str,
    results: list[dict[str, Any]],
    traversal_steps: list[dict[str, Any]] | None = None,
) -> str:
    """Call Claude to write a plain English summary of query results."""
    client = get_client()

    try:
        user_message = build_summarization_message(question, pql_query, results, traversal_steps or [])
    except TypeError:
        user_message = build_summarization_message(question, pql_query, results)

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS_SUMMARY,
        system=SUMMARIZATION_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text.strip()


def _json_candidates(raw: str) -> list[str]:
    candidates: list[str] = []
    fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)```", raw, flags=re.IGNORECASE)
    candidates.extend([c.strip() for c in fenced if c.strip()])
    candidates.append(raw.strip())

    text = raw.strip()
    starts = [i for i, ch in enumerate(text) if ch == "{"]
    for start in starts:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : i + 1].strip())
                    break
    return candidates


def _extract_json(text: str) -> dict[str, Any]:
    raw = text.replace("\ufeff", "").strip()
    if not raw:
        raise ValueError("Empty model response.")

    last_err: Exception | None = None
    for candidate in _json_candidates(raw):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception as e:
            last_err = e
    raise ValueError(f"Model response did not contain valid JSON object. Last error: {last_err}")


def chat_json(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    max_tokens: int = MAX_TOKENS_AGENT,
    debug_tag: str = "",
) -> dict[str, Any]:
    """Call Anthropic and parse a strict JSON object from the response."""
    client = get_client()
    system = ""
    anthropic_messages: list[dict[str, str]] = []
    for msg in messages:
        if msg.get("role") == "system":
            system = msg.get("content", "")
        else:
            anthropic_messages.append({"role": msg["role"], "content": msg["content"]})

    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=anthropic_messages,
    )

    text_parts: list[str] = []
    for block in response.content:
        if getattr(block, "type", "") == "text":
            text_parts.append(block.text)
    text = "".join(text_parts).strip()

    tag = debug_tag or "agent"
    snippet = text.replace("\n", "\\n")[:300]
    print(f"[anthropic-agent][{tag}] content_len={len(text)} snippet={snippet}")
    return _extract_json(text)
