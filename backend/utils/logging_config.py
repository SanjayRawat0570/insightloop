"""Central logging setup for the backend.

One call to :func:`setup_logging` (from ``api.main`` at import time) configures a
compact, readable console format and sensible levels. Everything else just does
``log = logging.getLogger("insightloop.<area>")`` and logs normally.

Format (concise but detailed):
    12:01:33 INFO  insightloop.sources    connect type=mongodb ok=True (412ms)

Env knobs:
    LOG_LEVEL   overall level for our own loggers (default INFO; try DEBUG)
    LOG_NOISY   set to 1 to stop silencing chatty third-party libs
"""
from __future__ import annotations

import logging
import os

# Root namespace for all of our loggers — gives one knob to raise/lower verbosity.
ROOT = "insightloop"

_CONFIGURED = False


class _CompactFormatter(logging.Formatter):
    """`HH:MM:SS LEVEL  name  message` with the insightloop. prefix trimmed."""

    def format(self, record: logging.LogRecord) -> str:
        record.short_name = record.name.replace(f"{ROOT}.", "").replace(ROOT, "app")
        return super().format(record)


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(
        _CompactFormatter(
            fmt="%(asctime)s %(levelname)-5s %(short_name)-22s %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    app_logger = logging.getLogger(ROOT)
    app_logger.setLevel(level)
    app_logger.handlers = [handler]
    app_logger.propagate = False

    # Quiet the chatty libraries unless explicitly asked to keep them.
    if os.environ.get("LOG_NOISY", "0").lower() in ("0", "false", "no", ""):
        for noisy in ("httpx", "httpcore", "pymongo", "motor", "uvicorn.access", "asyncio"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(area: str) -> logging.Logger:
    """Return a namespaced logger, e.g. get_logger("sources")."""
    return logging.getLogger(f"{ROOT}.{area}")
