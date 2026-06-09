"""Read-only SQL guardrail.

A last line of defense between the (LLM-driven) Query Writer and any database.
Even though the Query Writer is *prompted* to emit read-only SELECTs and runs a
light `validate_sql` check, an LLM can still hallucinate a mutating statement —
so before a query touches Postgres, MySQL, or the materialized-SQLite store that
backs MongoDB/API/Sheets/CSV sources, we re-check it here with a strict regex.

The contract is fail-closed: anything that is not an unambiguous, single
read-only statement is rejected with :class:`UnsafeQueryError`. A false positive
(refusing a safe query) is acceptable; a false negative (running an UPDATE or
DELETE) is a potential catastrophe.
"""
from __future__ import annotations

import re

# Statement keywords that mutate data or schema, or otherwise must never run from
# an analytics query. Matched as whole words (so a column like ``updated_at`` or
# ``is_deleted`` does NOT trip the guard — ``_`` is a word char, killing the \b).
_FORBIDDEN_KEYWORDS = (
    "update", "delete", "insert", "drop", "alter", "truncate", "create",
    "replace", "merge", "upsert", "grant", "revoke", "rename",
    "exec", "execute", "call", "attach", "detach", "vacuum", "pragma",
    "commit", "rollback", "savepoint", "set", "copy", "load", "lock",
)

# A forbidden word only counts as a *statement* when it is NOT immediately a
# function call: ``REPLACE(...)`` and ``TRUNCATE(x, d)`` are legitimate read-only
# scalar functions in MySQL/SQLite, whereas ``REPLACE INTO`` / ``TRUNCATE TABLE``
# are mutations. The negative lookahead ``(?!\s*\()`` lets the functions through
# while still catching every mutating/DDL statement form.
_FORBIDDEN_RE = re.compile(
    r"\b(" + "|".join(_FORBIDDEN_KEYWORDS) + r")\b(?!\s*\()", re.IGNORECASE
)

# Strip /* ... */ block comments and -- / # line comments so a mutation can't be
# smuggled past the keyword scan inside a comment that the DB later ignores.
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"(--|#)[^\n]*")


class UnsafeQueryError(Exception):
    """Raised when a query is not a single, read-only SELECT/WITH statement."""


def _strip_comments(sql: str) -> str:
    sql = _BLOCK_COMMENT_RE.sub(" ", sql)
    sql = _LINE_COMMENT_RE.sub(" ", sql)
    return sql


def assert_read_only(sql: str) -> str:
    """Return ``sql`` unchanged if it is a safe read-only query, else raise.

    Raises :class:`UnsafeQueryError` when the query is empty, contains a
    forbidden (mutating/DDL/admin) keyword, or chains multiple statements.
    """
    if not sql or not sql.strip():
        raise UnsafeQueryError("empty query")

    cleaned = _strip_comments(sql).strip()

    # Must begin as a read query. WITH covers CTEs that resolve to a SELECT.
    if not re.match(r"^\s*(select|with)\b", cleaned, re.IGNORECASE):
        raise UnsafeQueryError("only read-only SELECT queries are allowed")

    # Reject statement chaining: a ';' followed by anything other than trailing
    # whitespace means a second statement could ride along (e.g. piggy-backed
    # `; DROP TABLE ...`).
    if ";" in cleaned.rstrip().rstrip(";"):
        raise UnsafeQueryError("multiple statements are not allowed")

    match = _FORBIDDEN_RE.search(cleaned)
    if match:
        raise UnsafeQueryError(
            f"forbidden keyword '{match.group(1).upper()}' detected; "
            "only read-only queries may run"
        )

    return sql
