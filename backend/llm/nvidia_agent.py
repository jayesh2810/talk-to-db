"""
NVIDIA-hosted Stepfun agent model integration.

Uses:
  - base_url: https://integrate.api.nvidia.com/v1
  - model: stepfun-ai/step-3.5-flash
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

_client: OpenAI | None = None


def get_nvidia_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("NVIDIA_API_KEY")
        if not api_key:
            raise RuntimeError(
                "NVIDIA_API_KEY is not set. Add it to backend/.env before starting the server."
            )
        _client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key,
        )
    return _client


def _json_candidates(raw: str) -> list[str]:
    candidates: list[str] = []
    fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)```", raw, flags=re.IGNORECASE)
    candidates.extend([c.strip() for c in fenced if c.strip()])
    candidates.append(raw.strip())

    text = raw.strip()
    starts = [i for i, ch in enumerate(text) if ch == "{"]
    for s in starts:
        depth = 0
        for i in range(s, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    block = text[s : i + 1].strip()
                    if block:
                        candidates.append(block)
                    break
    return candidates


def _extract_json(text: str) -> dict[str, Any]:
    raw = text.replace("\ufeff", "").strip()
    if not raw:
        raise ValueError("Empty model response.")

    last_err: Exception | None = None
    for cand in _json_candidates(raw):
        try:
            parsed = json.loads(cand)
            if isinstance(parsed, dict):
                return parsed
        except Exception as e:
            last_err = e
            continue
    raise ValueError(f"Model response did not contain valid JSON object. Last error: {last_err}")


def chat_json(messages: list[dict[str, str]], *, temperature: float = 0.5) -> dict[str, Any]:
    """
    Run Step-3.5-Flash with streaming enabled and return parsed JSON payload.
    """
    client = get_nvidia_client()

    completion = client.chat.completions.create(
        model="stepfun-ai/step-3.5-flash",
        messages=messages,
        temperature=temperature,
        top_p=0.9,
        max_tokens=4096,
        stream=True,
    )

    chunks: list[str] = []
    for chunk in completion:
        if not getattr(chunk, "choices", None):
            continue
        delta = chunk.choices[0].delta
        if getattr(delta, "content", None):
            chunks.append(delta.content)

    return _extract_json("".join(chunks))
