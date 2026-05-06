"""
NVIDIA-hosted Stepfun agent model integration.

Uses:
  - base_url: https://integrate.api.nvidia.com/v1
  - model: stepfun-ai/step-3.5-flash
"""

from __future__ import annotations

import json
import os
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


def _extract_json(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model response did not contain a JSON object.")
    return json.loads(raw[start : end + 1])


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

