"""Shared Claude/LangChain helper for the agents.

Centralizes model construction and robust JSON extraction. If no API key is
configured (or a call fails), callers are expected to fall back to a
deterministic heuristic so the pipeline always produces a result.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional


DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


def have_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


_llm_cache: dict[str, Any] = {}


def get_llm(temperature: float = 0.0, max_tokens: int = 1024):
    """Return a cached ChatAnthropic instance, or None if unavailable."""
    if not have_api_key():
        return None
    key = f"{DEFAULT_MODEL}:{temperature}:{max_tokens}"
    if key in _llm_cache:
        return _llm_cache[key]
    try:
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(
            model=DEFAULT_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=60,
        )
        _llm_cache[key] = llm
        return llm
    except Exception:
        return None


def call_text(system: str, user: str, temperature: float = 0.0, max_tokens: int = 1024) -> Optional[str]:
    """Call Claude and return raw text, or None if no LLM / on failure."""
    llm = get_llm(temperature=temperature, max_tokens=max_tokens)
    if llm is None:
        return None
    try:
        resp = llm.invoke([("system", system), ("human", user)])
        content = resp.content
        if isinstance(content, list):
            # Anthropic may return a list of content blocks.
            content = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        return str(content).strip()
    except Exception:
        return None


def extract_json(text: str) -> Any:
    """Best-effort: pull the first JSON object/array out of an LLM response."""
    if text is None:
        raise ValueError("no text to parse")
    cleaned = text.strip()
    # Strip ```json ... ``` fences.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Fall back to grabbing the outermost {...} or [...].
    match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    raise ValueError(f"could not parse JSON from model output: {text[:200]}")


def call_json(system: str, user: str, temperature: float = 0.0, max_tokens: int = 1024) -> Optional[Any]:
    """Call Claude expecting JSON. Returns parsed value, or None on any failure."""
    raw = call_text(system, user, temperature=temperature, max_tokens=max_tokens)
    if raw is None:
        return None
    try:
        return extract_json(raw)
    except Exception:
        return None
