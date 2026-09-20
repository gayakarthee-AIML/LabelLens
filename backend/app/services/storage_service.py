"""
S3-compatible object storage (MinIO in local/dev, any S3-compatible bucket in
production). All original and processed inspection images are stored here —
the database only holds the object key, never the image bytes.
"""
import io
import uuid

import boto3
from botocore.client import Config

from app.core.config import get_settings

settings = get_settings()

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(signature_version="s3v4"),
        )
        try:
            _client.head_bucket(Bucket=settings.s3_bucket)
        except Exception:
            _client.create_bucket(Bucket=settings.s3_bucket)
    return _client


def put_object(data: bytes, prefix: str, content_type: str = "image/jpeg") -> str:
    key = f"{prefix}/{uuid.uuid4()}.jpg"
    client = _get_client()
    client.upload_fileobj(io.BytesIO(data), settings.s3_bucket, key, ExtraArgs={"ContentType": content_type})
    return key


def get_object(key: str) -> bytes:
    client = _get_client()
    buf = io.BytesIO()
    client.download_fileobj(settings.s3_bucket, key, buf)
    return buf.getvalue()


def presigned_url(key: str, expires_in: int = 3600) -> str:
    client = _get_client()
    return client.generate_presigned_url(
        "get_object", Params={"Bucket": settings.s3_bucket, "Key": key}, ExpiresIn=expires_in
    )
