from __future__ import annotations

import hashlib
import hmac
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse
from uuid import uuid4

import boto3
from botocore.config import Config
from fastapi import HTTPException

from app.config import Settings


class ObjectStorageClient:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._bucket = settings.object_storage_bucket.strip()
        self._public_base_url = settings.object_storage_public_base_url.rstrip("/")
        self._endpoint_url = settings.object_storage_endpoint_url.rstrip("/")
        if not self._bucket or not self._public_base_url or not self._endpoint_url:
            raise ValueError("Object storage is not configured.")
        self._client = client or boto3.client(
            "s3",
            endpoint_url=self._endpoint_url,
            region_name=settings.object_storage_region.strip() or "auto",
            aws_access_key_id=settings.object_storage_access_key_id.strip(),
            aws_secret_access_key=settings.object_storage_secret_access_key.strip(),
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def __repr__(self) -> str:
        return f"ObjectStorageClient(bucket={self._bucket!r}, endpoint={self._endpoint_url!r})"

    def put_file(self, source: str | Path, key: str, content_type: str) -> None:
        self._client.upload_file(
            Filename=str(source),
            Bucket=self._bucket,
            Key=key,
            ExtraArgs={"ContentType": content_type},
        )

    def head(self, key: str) -> dict[str, Any]:
        response = self._client.head_object(Bucket=self._bucket, Key=key)
        if int(response.get("ContentLength") or 0) <= 0:
            raise ValueError(f"Object is missing or empty: {key}")
        return response

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def download_file(self, key: str, destination: str | Path) -> None:
        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        self._client.download_file(Bucket=self._bucket, Key=key, Filename=str(destination_path))

    def object_key_from_public_url(self, value: str) -> str | None:
        public_base = urlparse(self._public_base_url)
        candidate = urlparse(value.strip())
        if (
            candidate.scheme.lower() != public_base.scheme.lower()
            or candidate.netloc.lower() != public_base.netloc.lower()
        ):
            return None
        base_path = public_base.path.rstrip("/")
        prefix = f"{base_path}/" if base_path else "/"
        if not candidate.path.startswith(prefix):
            return None
        object_key = unquote(candidate.path[len(prefix) :])
        return object_key if object_key else None

    def read_image(self, key: str, *, max_bytes: int) -> dict[str, Any]:
        if max_bytes <= 0:
            raise ValueError("Image size limit must be positive.")
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        content_length = int(response.get("ContentLength") or 0)
        if content_length <= 0:
            raise ValueError("Object is empty.")
        if content_length > max_bytes:
            raise ValueError("Object is too large.")
        content_type = str(response.get("ContentType") or "").split(";", 1)[0].strip().lower()
        if not content_type.startswith("image/"):
            raise ValueError("Object is not an image.")
        body = response.get("Body")
        if body is None or not callable(getattr(body, "read", None)):
            raise ValueError("Object is empty.")
        try:
            content = body.read(max_bytes + 1)
        finally:
            close = getattr(body, "close", None)
            if callable(close):
                close()
        if not content:
            raise ValueError("Object is empty.")
        if len(content) > max_bytes:
            raise ValueError("Object is too large.")
        return {
            "content": content,
            "content_type": content_type,
            "filename": key.rstrip("/").rsplit("/", 1)[-1] or "reference.png",
        }

    def public_url(self, key: str) -> str:
        return f"{self._public_base_url}/{quote(key, safe='/-_.~')}"


def _sign(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


def _quote(value: str, safe: str = "-_.~") -> str:
    return quote(value, safe=safe)


def _canonical_query(params: dict[str, str]) -> str:
    return "&".join(f"{_quote(key)}={_quote(value)}" for key, value in sorted(params.items()))


def _safe_file_name(value: str) -> str:
    raw = value.strip().replace("\\", "/").split("/")[-1] or "upload.bin"
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip(".-")
    return sanitized[:120] or "upload.bin"


def make_object_key(file_name: str, prefix: str = "") -> str:
    now = datetime.now(timezone.utc)
    cleaned_prefix = prefix.strip().strip("/")
    safe_name = _safe_file_name(file_name)
    key = f"uploads/{now:%Y/%m/%d}/{uuid4().hex}-{safe_name}"
    return f"{cleaned_prefix}/{key}" if cleaned_prefix else key


def create_presigned_put_url(
    *,
    settings: Settings,
    file_name: str,
    content_type: str,
    expires_in: int = 900,
) -> dict[str, str]:
    endpoint = settings.object_storage_endpoint_url.rstrip("/")
    bucket = settings.object_storage_bucket.strip()
    access_key = settings.object_storage_access_key_id.strip()
    secret_key = settings.object_storage_secret_access_key.strip()
    region = settings.object_storage_region.strip() or "auto"
    public_base_url = settings.object_storage_public_base_url.rstrip("/")

    if not endpoint or not bucket or not access_key or not secret_key or not public_base_url:
        raise HTTPException(status_code=500, detail={"message": "对象存储未正确配置。"})

    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.netloc:
        raise HTTPException(status_code=500, detail={"message": "对象存储地址必须使用 HTTPS。"})

    object_key = make_object_key(file_name, settings.object_storage_key_prefix)
    amz_time = datetime.now(timezone.utc)
    date_stamp = amz_time.strftime("%Y%m%d")
    amz_date = amz_time.strftime("%Y%m%dT%H%M%SZ")
    scope = f"{date_stamp}/{region}/s3/aws4_request"
    canonical_uri = "/" + "/".join(_quote(part) for part in [bucket, *object_key.split("/")])
    host = parsed.netloc
    query_params = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": f"{access_key}/{scope}",
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(max(60, min(expires_in, 3600))),
        "X-Amz-SignedHeaders": "host",
    }
    canonical_query = _canonical_query(query_params)
    canonical_request = "\n".join(
        [
            "PUT",
            canonical_uri,
            canonical_query,
            f"host:{host}\n",
            "host",
            "UNSIGNED-PAYLOAD",
        ]
    )
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signing_key = _sign(
        _sign(_sign(_sign(("AWS4" + secret_key).encode("utf-8"), date_stamp), region), "s3"),
        "aws4_request",
    )
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    upload_url = f"{endpoint}{canonical_uri}?{canonical_query}&X-Amz-Signature={signature}"

    return {
        "uploadUrl": upload_url,
        "method": "PUT",
        "publicUrl": f"{public_base_url}/{_quote(object_key, safe='/-_.~')}",
        "objectKey": object_key,
        "contentType": content_type,
    }
