"""
Storage Service — supports both MinIO (production) and local filesystem (development).
Falls back to local filesystem if MinIO is not available.
"""
import io
import os
import shutil
from typing import Optional, List
from pathlib import Path
from app.config import settings

# Determine if we use local filesystem (no MinIO)
LOCAL_STORAGE_DIR = Path(settings.temp_dir) / "storage"
USE_LOCAL = True  # Will auto-detect MinIO, fall back to local

def _get_local_path(object_key: str) -> Path:
    p = LOCAL_STORAGE_DIR / object_key
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _try_minio():
    """Try to connect to MinIO, return client or None."""
    # Skip MinIO completely if in local SQLite mode to prevent long connection timeouts
    if settings.database_url.startswith("sqlite"):
        return None
        
    try:
        from minio import Minio
        import urllib3
        http_client = urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=2.0, read=2.0),
            retries=urllib3.Retry(total=0)
        )
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
            http_client=http_client,
        )
        # Quick test
        client.list_buckets()
        return client
    except Exception:
        return None


def ensure_bucket_exists(bucket_name: Optional[str] = None):
    """Create bucket / local folder if needed."""
    LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    client = _try_minio()
    if client:
        bucket = bucket_name or settings.minio_bucket
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)


def upload_file(file_bytes: bytes, object_key: str, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to storage, returns the object key."""
    client = _try_minio()
    if client:
        try:
            bucket = settings.minio_bucket
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)
            client.put_object(
                bucket, object_key, io.BytesIO(file_bytes),
                length=len(file_bytes), content_type=content_type,
            )
            return object_key
        except Exception:
            pass
    # Fallback: local filesystem
    p = _get_local_path(object_key)
    p.write_bytes(file_bytes)
    return object_key


def download_file(object_key: str) -> bytes:
    """Download file bytes from storage."""
    client = _try_minio()
    if client:
        try:
            response = client.get_object(settings.minio_bucket, object_key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except Exception:
            pass
    # Fallback: local filesystem
    p = _get_local_path(object_key)
    if p.exists():
        return p.read_bytes()
    raise FileNotFoundError(f"File not found: {object_key}")


def delete_file(object_key: str):
    """Delete an object from storage."""
    client = _try_minio()
    if client:
        try:
            client.remove_object(settings.minio_bucket, object_key)
            return
        except Exception:
            pass
    p = _get_local_path(object_key)
    if p.exists():
        p.unlink()


def get_presigned_url(object_key: str, expires_seconds: int = 3600) -> str:
    """Get URL for temporary file access."""
    # For local dev, return a direct API path
    return f"/api/v1/files/{object_key}"


def list_objects(prefix: str) -> List[str]:
    """List object keys with a given prefix."""
    client = _try_minio()
    if client:
        try:
            objects = client.list_objects(settings.minio_bucket, prefix=prefix, recursive=True)
            return [obj.object_name for obj in objects]
        except Exception:
            pass
    # Local fallback
    base = LOCAL_STORAGE_DIR / prefix
    if not base.exists():
        return []
    return [str(p.relative_to(LOCAL_STORAGE_DIR)).replace("\\", "/") for p in base.rglob("*") if p.is_file()]
