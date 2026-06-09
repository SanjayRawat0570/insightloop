"""Source materialization.

Turns *any* configured data source into something the SQL pipeline can query:

  * ``postgres`` / ``mysql`` — queried in place; we just hand back the live URL.
  * ``api`` / ``sheets`` / ``csv`` / ``mongodb`` — fetched for real and
    *materialized* into a per-source SQLite file so the uniform SQL pipeline runs
    against the user's actual data instead of a bundled sample database. For
    MongoDB each collection becomes one table (nested fields flattened).

The key contract: when a source is selected, we use THAT source's data. If the
real data can't be fetched we raise :class:`SourceLoadError` — we never silently
substitute sample data.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
import time
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

try:
    from backend.utils.crypto import build_connection_url
    from backend.utils.logging_config import get_logger
except ModuleNotFoundError:
    from utils.crypto import build_connection_url
    from utils.logging_config import get_logger

log = get_logger("connector")


class SourceLoadError(Exception):
    """Raised when a source's real data cannot be fetched or materialized."""


@dataclass
class MaterializedSource:
    """Result of resolving a source into a queryable store."""

    db_url: str                       # SQLAlchemy async URL the pipeline executes against
    dialect: str                      # dialect for the query writer ("sqlite" when materialized)
    table_names: List[str] = field(default_factory=list)
    live: bool = False                # True when db_url is the user's own SQL DB (not materialized)


# Directory holding materialized SQLite DBs — one file per source, reused across
# queries and overwritten on each refresh so data stays current.
CACHE_DIR = Path(
    os.environ.get("MATERIALIZE_DIR") or (Path(tempfile.gettempdir()) / "insightloop_sources")
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _cache_path(source_id: Optional[str]) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", source_id or "adhoc")
    return CACHE_DIR / f"{safe}.db"


def _sqlite_async_url(path: Path) -> str:
    # Forward slashes keep the SQLAlchemy URL valid on Windows too.
    return f"sqlite+aiosqlite:///{path.as_posix()}"


def _sanitize_table(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]", "_", str(name).strip()) or "data"
    if name[0].isdigit():
        name = f"t_{name}"
    return name.lower()


def _sanitize_col(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]", "_", str(name).strip()).strip("_") or "col"
    if name[0].isdigit():
        name = f"c_{name}"
    return name


def _flatten_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Make a DataFrame SQLite-safe: clean column names, JSON-encode nested cells."""
    df = df.copy()
    df.columns = [_sanitize_col(c) for c in df.columns]
    # De-duplicate any column names that collapsed to the same value.
    seen: Dict[str, int] = {}
    new_cols: List[str] = []
    for c in df.columns:
        if c in seen:
            seen[c] += 1
            new_cols.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            new_cols.append(c)
    df.columns = new_cols
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(
                lambda v: json.dumps(v, default=str) if isinstance(v, (dict, list)) else v
            )
    return df


def _write_frames(path: Path, frames: Dict[str, pd.DataFrame]) -> List[str]:
    """(Re)create the SQLite file and write each DataFrame as a table."""
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(str(path))
    written: List[str] = []
    try:
        for raw_name, df in frames.items():
            if df is None or len(df.columns) == 0:
                continue
            table = _sanitize_table(raw_name)
            _flatten_frame(df).to_sql(table, conn, if_exists="replace", index=False)
            written.append(table)
        conn.commit()
    finally:
        conn.close()
    if not written:
        raise SourceLoadError("source returned no tabular data")
    return written


def _parse_headers(h: Any) -> Dict[str, str]:
    """Accept headers as a dict, a JSON object string, or 'Key: Value' lines."""
    if not h:
        return {}
    if isinstance(h, dict):
        return {str(k): str(v) for k, v in h.items()}
    if isinstance(h, str):
        s = h.strip()
        if not s:
            return {}
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                return {str(k): str(v) for k, v in obj.items()}
        except Exception:
            pass
        out: Dict[str, str] = {}
        for line in s.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip()
        return out
    return {}


def _extract_records(data: Any, path: Optional[str]) -> List[Any]:
    """Locate the list of records inside an arbitrary JSON response.

    ``path`` is an optional dot-path (e.g. ``data.results``) to the array.
    """
    node = data
    if path:
        for part in str(path).split("."):
            part = part.strip()
            if not part:
                continue
            if isinstance(node, dict):
                node = node.get(part)
            elif isinstance(node, list):
                try:
                    node = node[int(part)]
                except (ValueError, IndexError):
                    node = None
                    break
            else:
                node = None
                break
        if node is None:
            raise SourceLoadError(f"json_path '{path}' did not match the API response")
    if isinstance(node, dict):
        # No explicit path: grab the first list value, else treat as one record.
        for v in node.values():
            if isinstance(v, list):
                return v
        return [node]
    if isinstance(node, list):
        if node and not isinstance(node[0], dict):
            return [{"value": v} for v in node]
        return node
    return [{"value": node}]


# ── per-type loaders ─────────────────────────────────────────────────────────

def _load_api(cfg: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    import httpx

    url = cfg.get("url") or cfg.get("connection_url")
    if not url:
        raise SourceLoadError("API source requires a 'url'")
    method = (cfg.get("method") or "GET").upper()
    headers = _parse_headers(cfg.get("headers"))
    params = cfg.get("params") or None
    try:
        resp = httpx.request(method, url, headers=headers, params=params, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
    except SourceLoadError:
        raise
    except Exception as e:
        raise SourceLoadError(f"API request failed: {e}")

    records = _extract_records(data, cfg.get("json_path") or cfg.get("data_path"))
    df = pd.json_normalize(records)
    if df.empty:
        raise SourceLoadError("API returned no records")
    return {cfg.get("table_name") or "api_data": df}


def _load_sheets(cfg: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    import httpx

    url = cfg.get("sheet_url") or cfg.get("url") or cfg.get("connection_url")
    if not url:
        raise SourceLoadError("Sheets source requires a 'sheet_url'")

    last_err = "no readable CSV endpoint"
    for csv_url in _sheets_csv_candidates(url):
        try:
            resp = httpx.get(csv_url, follow_redirects=True, timeout=30.0)
        except Exception as e:
            last_err = str(e)
            continue
        if resp.status_code != 200:
            last_err = f"HTTP {resp.status_code}"
            continue
        text = resp.text
        ctype = resp.headers.get("content-type", "")
        head = text[:200].lstrip().lower()
        # A login / permission page comes back as HTML, not CSV.
        if "text/html" in ctype or head.startswith("<!doctype html") or "<html" in head:
            last_err = "the sheet is not shared publicly (got a sign-in page)"
            continue
        try:
            df = pd.read_csv(StringIO(text))
        except Exception as e:
            last_err = f"could not parse CSV: {e}"
            continue
        if df.empty:
            raise SourceLoadError("Google Sheet has no rows")
        return {cfg.get("table_name") or "sheet_data": df}

    raise SourceLoadError(
        f"Could not read Google Sheet (share it as 'Anyone with the link → Viewer'): {last_err}"
    )


def _sheets_csv_candidates(url: str) -> List[str]:
    """Build CSV export URLs to try, in priority order, for any Sheets link."""
    # Already a direct CSV/export link — use as-is.
    if "format=csv" in url or "output=csv" in url or "tqx=out:csv" in url or url.endswith(".csv"):
        return [url]

    gid_m = re.search(r"[#&?]gid=(\d+)", url)
    gid = gid_m.group(1) if gid_m else "0"

    # Published-to-web links use a different id space: /spreadsheets/d/e/<token>/…
    # Must be checked before the generic /d/<id> pattern (which would match "e").
    pub_m = re.search(r"/spreadsheets/d/e/([A-Za-z0-9-_]+)", url)
    if pub_m:
        token = pub_m.group(1)
        return [
            f"https://docs.google.com/spreadsheets/d/e/{token}/pub?output=csv&gid={gid}",
            f"https://docs.google.com/spreadsheets/d/e/{token}/pub?output=csv",
        ]

    m = re.search(r"/spreadsheets/d/([A-Za-z0-9-_]+)", url)
    if not m:
        raise SourceLoadError("Not a valid Google Sheets URL")
    sheet_id = m.group(1)
    return [
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}",
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}",
    ]


def _mongo_database_name(cfg: Dict[str, Any], uri: str) -> Optional[str]:
    """Resolve the Mongo database name from config, falling back to the URI path."""
    name = cfg.get("database") or cfg.get("db") or cfg.get("dbname")
    if name:
        return str(name)
    # mongodb://host/<db>?opts  or  mongodb+srv://host/<db>
    m = re.search(r"mongodb(?:\+srv)?://[^/]+/([^/?]+)", uri or "")
    if m and m.group(1):
        return m.group(1)
    return None


def _coerce_mongo_value(v: Any) -> Any:
    """Make a single Mongo value SQLite-friendly (stringify ObjectId/UUID/bytes)."""
    from bson import ObjectId
    from bson.decimal128 import Decimal128

    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, Decimal128):
        return float(v.to_decimal())
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8", "replace")
        except Exception:
            return v.hex()
    return v


def _load_mongodb(cfg: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    """Pull real documents out of MongoDB and shape them into tabular frames.

    Each selected collection becomes one table. Documents are flattened with
    ``json_normalize`` so nested fields are reachable as ``parent.child`` columns;
    ObjectIds and other BSON types are coerced to SQLite-safe scalars. Nested
    dict/list values are JSON-encoded later by :func:`_flatten_frame`.
    """
    from pymongo import MongoClient

    uri = cfg.get("connection_url") or cfg.get("uri") or cfg.get("url")
    if not uri:
        host = cfg.get("host") or cfg.get("hostname")
        if not host:
            raise SourceLoadError("MongoDB source requires a connection string ('uri')")
        port = cfg.get("port") or 27017
        user = cfg.get("user") or cfg.get("username")
        password = cfg.get("password") or cfg.get("pass")
        creds = f"{user}:{password}@" if user else ""
        uri = f"mongodb://{creds}{host}:{port}"

    database = _mongo_database_name(cfg, uri)
    if not database:
        raise SourceLoadError("MongoDB source requires a 'database' name")

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=8000, connectTimeoutMS=8000)
    except Exception as e:
        raise SourceLoadError(f"invalid MongoDB connection string: {e}")

    try:
        db = client[database]
        # Force a round-trip so a bad host/credentials fail loudly here.
        try:
            db.command("ping")
        except Exception as e:
            raise SourceLoadError(f"could not connect to MongoDB: {e}")

        requested = cfg.get("collection") or cfg.get("collections")
        if isinstance(requested, str):
            names = [c.strip() for c in requested.split(",") if c.strip()]
        elif isinstance(requested, (list, tuple)):
            names = [str(c) for c in requested]
        else:
            names = [
                n for n in db.list_collection_names()
                if not n.startswith("system.")
            ]
        if not names:
            raise SourceLoadError(f"database '{database}' has no collections")

        try:
            limit = int(cfg.get("limit") or 1000)
        except (TypeError, ValueError):
            limit = 1000
        limit = max(1, min(limit, 5000))

        flt = cfg.get("filter") or cfg.get("query")
        if isinstance(flt, str) and flt.strip():
            try:
                flt = json.loads(flt)
            except Exception:
                raise SourceLoadError("MongoDB 'filter' must be valid JSON")
        if not isinstance(flt, dict):
            flt = {}

        frames: Dict[str, pd.DataFrame] = {}
        for name in names:
            try:
                docs = list(db[name].find(flt, limit=limit))
            except Exception as e:
                raise SourceLoadError(f"could not read collection '{name}': {e}")
            if not docs:
                continue
            docs = [{k: _coerce_mongo_value(v) for k, v in d.items()} for d in docs]
            df = pd.json_normalize(docs)
            if not df.empty:
                frames[name] = df

        if not frames:
            raise SourceLoadError(
                f"no documents found in {', '.join(names)} (collection empty or filter too narrow)"
            )
        return frames
    finally:
        client.close()


def _load_csv(cfg: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    content = cfg.get("content")
    src = cfg.get("file_path") or cfg.get("path") or cfg.get("url") or cfg.get("connection_url")
    try:
        if content:
            df = pd.read_csv(StringIO(content))
        elif src:
            df = pd.read_csv(src)
        else:
            raise SourceLoadError("CSV source requires a 'file_path', 'url', or inline 'content'")
    except SourceLoadError:
        raise
    except Exception as e:
        raise SourceLoadError(f"Could not read CSV: {e}")
    if df.empty:
        raise SourceLoadError("CSV has no rows")
    return {cfg.get("table_name") or "csv_data": df}


_LOADERS = {
    "api": _load_api,
    "sheets": _load_sheets,
    "csv": _load_csv,
    "mongodb": _load_mongodb,
}


# ── public entry point ───────────────────────────────────────────────────────

def materialize_source(
    source_type: str,
    cfg: Dict[str, Any],
    source_id: Optional[str] = None,
) -> MaterializedSource:
    """Resolve a source into a queryable store.

    SQL sources are returned as a live connection; everything else is fetched
    and written to a per-source SQLite file. Raises :class:`SourceLoadError` on
    any failure so callers can surface an honest error instead of fake data.

    Synchronous (does network + disk I/O) — call via ``asyncio.to_thread``.
    """
    st = (source_type or "").lower()
    log.info("materialize start type=%s source=%s", st, source_id or "adhoc")
    start = time.perf_counter()

    if st in ("postgres", "mysql"):
        url = cfg.get("connection_url") or build_connection_url(cfg, st)
        if not url:
            raise SourceLoadError(f"{st} source is missing host/database connection details")
        log.info("materialize live type=%s (queried in place)", st)
        return MaterializedSource(db_url=url, dialect=st, live=True)

    loader = _LOADERS.get(st)
    if not loader:
        raise SourceLoadError(f"unsupported source type: {source_type}")

    frames = loader(cfg)
    total_rows = sum(len(df) for df in frames.values())
    path = _cache_path(source_id)
    tables = _write_frames(path, frames)
    ms = int((time.perf_counter() - start) * 1000)
    log.info(
        "materialize done type=%s tables=%s rows=%d (%dms)",
        st, tables, total_rows, ms,
    )
    return MaterializedSource(
        db_url=_sqlite_async_url(path),
        dialect="sqlite",
        table_names=tables,
        live=False,
    )
