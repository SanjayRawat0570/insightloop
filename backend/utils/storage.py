import os
import uuid
from pathlib import Path
from typing import BinaryIO

from supabase import create_client, Client


def _get_supabase_client() -> Client:
    supabase_url = os.environ.get("SUPABASE_URL")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured")
    return create_client(supabase_url, service_role_key)


def upload_file_to_supabase(file_obj: BinaryIO, bucket: str | None = None, path: str | None = None, content_type: str | None = None) -> str:
    """Upload a file-like object to Supabase Storage and return a public URL if available.

    If the bucket is private, callers should use the returned path with signed URL logic.
    """
    supabase_bucket = bucket or os.environ.get("SUPABASE_BUCKET")
    if not supabase_bucket:
        raise RuntimeError("SUPABASE_BUCKET must be configured")

    client = _get_supabase_client()
    filename = path or f"uploads/{uuid.uuid4().hex}-{Path(getattr(file_obj, 'name', 'file')).name}"

    payload = file_obj.read()
    if hasattr(file_obj, "seek"):
        file_obj.seek(0)

    client.storage.from_(supabase_bucket).upload(
        filename,
        payload,
        file_options={"content-type": content_type} if content_type else None,
    )

    public_url = client.storage.from_(supabase_bucket).get_public_url(filename)
    return public_url
