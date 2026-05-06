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


def _snippet(s: str, n: int = 300) -> str:
    out = (s or "").replace("\n", "\\n")
    return out[:n]


def _log_debug(tag: str, msg: str) -> None:
    t = tag or "agent"
    print(f"[nvidia-agent][{t}] {msg}")


def chat_json(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.5,
    debug_tag: str = "",
) -> dict[str, Any]:
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
    reasoning_chunks: list[str] = []
    chunk_count = 0
    content_chunk_count = 0
    reasoning_chunk_count = 0

    for chunk in completion:
        chunk_count += 1
        if not getattr(chunk, "choices", None):
            continue
        delta = chunk.choices[0].delta
        if getattr(delta, "content", None):
            content_chunk_count += 1
            chunks.append(delta.content)
        rc = getattr(delta, "reasoning_content", None)
        if rc:
            reasoning_chunk_count += 1
            reasoning_chunks.append(rc)

    text = "".join(chunks).strip()
    reasoning_text = "".join(reasoning_chunks).strip()
    _log_debug(
        debug_tag,
        (
            f"stream chunks={chunk_count}, content_chunks={content_chunk_count}, "
            f"reasoning_chunks={reasoning_chunk_count}, content_len={len(text)}, "
            f"reasoning_len={len(reasoning_text)}"
        ),
    )
    if text:
        _log_debug(debug_tag, f"stream content snippet={_snippet(text)}")
    elif reasoning_text:
        _log_debug(debug_tag, f"stream reasoning snippet={_snippet(reasoning_text)}")

    if not text:
        _log_debug(debug_tag, "empty streamed content; retrying once with stream=False")
        non_stream = client.chat.completions.create(
            model="stepfun-ai/step-3.5-flash",
            messages=messages,
            temperature=temperature,
            top_p=0.9,
            max_tokens=4096,
            stream=False,
        )
        raw = ""
        if getattr(non_stream, "choices", None):
            msg = non_stream.choices[0].message
            raw = getattr(msg, "content", "") or ""
        _log_debug(debug_tag, f"non-stream content_len={len(raw)} snippet={_snippet(raw)}")
        return _extract_json(raw)

    return _extract_json(text)
