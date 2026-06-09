import json
import os
from typing import Dict, Any
from urllib.parse import quote
from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Fernet | None:
    key = os.environ.get("FERNET_KEY")
    if not key:
        return None
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_connection_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Encrypt connection config dict. Returns original dict if FERNET_KEY not set."""
    f = _get_fernet()
    if not f:
        return config
    payload = f.encrypt(json.dumps(config).encode()).decode()
    return {"encrypted_payload": payload}


def decrypt_connection_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """If config contains an 'encrypted_payload' field, decrypt it using FERNET_KEY.

    Otherwise returns config unchanged. Expects decrypted payload to be a JSON-like dict
    that may include 'connection_url'.
    """
    if not isinstance(config, dict):
        return config

    key = os.environ.get("FERNET_KEY")
    if not key:
        return config

    payload = config.get("encrypted_payload")
    if not payload:
        return config

    try:
        f = Fernet(key.encode() if isinstance(key, str) else key)
        decrypted = f.decrypt(payload.encode())
        return json.loads(decrypted)
    except (InvalidToken, ValueError):
        return config


def build_connection_url(config: Dict[str, Any], dialect: str = "postgres") -> str | None:
    """Construct a SQLAlchemy async connection URL from config dict.

    Supports keys: connection_url, host, port, database, user, password, driver
    For postgres returns postgresql+asyncpg://user:pass@host:port/db
    """
    if not isinstance(config, dict):
        return None
    if config.get("connection_url"):
        return config.get("connection_url")

    # Trim stray whitespace that creeps in from copy/paste (a leading space in
    # the host yields an unresolvable name -> getaddrinfo failed).
    def _clean(v: Any) -> str:
        return str(v).strip() if v is not None else ""

    host = _clean(config.get("host") or config.get("hostname"))
    port = _clean(config.get("port"))
    database = _clean(config.get("database") or config.get("db") or config.get("dbname"))
    user = _clean(config.get("user") or config.get("username"))
    password = _clean(config.get("password") or config.get("pass"))
    if not host or not database:
        return None

    if dialect and dialect.lower().startswith("postgres"):
        driver = "asyncpg"
        proto = f"postgresql+{driver}"
    elif dialect and dialect.lower().startswith("mysql"):
        driver = _clean(config.get("driver")) or "asyncmy"
        proto = f"mysql+{driver}"
    else:
        proto = dialect

    # Percent-encode credentials so special chars (@ : / etc., common in
    # Supabase/RDS passwords) don't corrupt URL parsing.
    creds = ""
    if user:
        creds = quote(user, safe="")
        if password:
            creds += ":" + quote(password, safe="")
        creds += "@"

    port_part = f":{port}" if port else ""
    return f"{proto}://{creds}{host}{port_part}/{database}"
