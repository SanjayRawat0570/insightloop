"""Shared LLM helper for the agents.

Centralizes model construction and robust JSON extraction. The call chain is:

    1. Anthropic Claude  (if ANTHROPIC_API_KEY is set and the call succeeds)
    2. Local LLM via Ollama  (if reachable — used when Claude is unavailable
       or out of credits)
    3. Caller's deterministic heuristic  (call_text/call_json return None)

This means the pipeline always produces a result, and when the hosted API is
down/out of credits we still get real generative AI from a locally running
model instead of falling straight back to dumb heuristics.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional


DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# Local LLM (Ollama) configuration.
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:1b")
LOCAL_LLM_ENABLED = os.environ.get("LOCAL_LLM_ENABLED", "1").lower() not in (
    "0",
    "false",
    "no",
    "",
)

# Records which backend served the most recent successful call: one of
# "anthropic", "ollama", or None (heuristic). Useful for /health diagnostics.
last_backend: Optional[str] = None


def have_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def fast_pipeline() -> bool:
    """When on, agents that can be deterministic skip the LLM for speed.

    Defaults on for the slow local model; set FAST_PIPELINE=0 to force the full
    LLM path on every agent (e.g. when running on Claude).
    """
    return os.environ.get("FAST_PIPELINE", "1").lower() not in ("0", "false", "no", "")


_llm_cache: dict[str, Any] = {}
_local_available: Optional[bool] = None


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


def ollama_available(force: bool = False) -> bool:
    """Check (and cache) whether a local Ollama server is reachable."""
    global _local_available
    if not LOCAL_LLM_ENABLED:
        return False
    if _local_available is not None and not force:
        return _local_available
    try:
        import httpx

        resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2.0)
        _local_available = resp.status_code == 200
    except Exception:
        _local_available = False
    return _local_available


def call_local(
    system: str, user: str, temperature: float = 0.0, max_tokens: int = 1024
) -> Optional[str]:
    """Call a local Ollama model and return raw text, or None on failure."""
    if not ollama_available():
        return None
    try:
        import httpx

        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        resp = httpx.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=180.0)
        resp.raise_for_status()
        data = resp.json()
        content = (data.get("message") or {}).get("content", "")
        content = str(content).strip()
        return content or None
    except Exception:
        return None


def call_text(
    system: str, user: str, temperature: float = 0.0, max_tokens: int = 1024
) -> Optional[str]:
    """Generate text, preferring Claude then a local model.

    Returns None only if every backend is unavailable/failing, signalling the
    caller to use its heuristic fallback.
    """
    global last_backend

    llm = get_llm(temperature=temperature, max_tokens=max_tokens)
    if llm is not None:
        try:
            resp = llm.invoke([("system", system), ("human", user)])
            content = resp.content
            if isinstance(content, list):
                # Anthropic may return a list of content blocks.
                content = "".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                )
            text = str(content).strip()
            if text:
                last_backend = "anthropic"
                return text
        except Exception:
            # Hosted API failed (e.g. out of credits) — fall through to local.
            pass

    text = call_local(system, user, temperature=temperature, max_tokens=max_tokens)
    if text:
        last_backend = "ollama"
        return text

    last_backend = None
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


def call_json(
    system: str, user: str, temperature: float = 0.0, max_tokens: int = 1024
) -> Optional[Any]:
    """Call the model expecting JSON. Returns parsed value, or None on failure."""
    raw = call_text(system, user, temperature=temperature, max_tokens=max_tokens)
    if raw is None:
        return None
    try:
        return extract_json(raw)
    except Exception:
        return None


def backend_label() -> str:
    """Human-readable description of the backend that served the last call."""
    if last_backend == "anthropic":
        return f"Claude ({DEFAULT_MODEL})"
    if last_backend == "ollama":
        return f"local model ({OLLAMA_MODEL})"
    return "heuristic fallback"


def llm_status() -> dict:
    """Snapshot of available LLM backends for diagnostics."""
    return {
        "anthropic_key": have_api_key(),
        "local_enabled": LOCAL_LLM_ENABLED,
        "local_available": ollama_available(force=True),
        "local_model": OLLAMA_MODEL,
        "last_backend": last_backend,
    }
