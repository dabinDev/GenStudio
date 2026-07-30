from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import os
from pathlib import Path
import socket
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import httpx


MAX_REMOTE_IMAGE_BYTES = 25 * 1024 * 1024
ALLOWED_REMOTE_IMAGE_TYPES = {"image/gif", "image/jpeg", "image/png", "image/webp"}
Resolver = Callable[..., list[Any]]


class RemoteImageFetchError(ValueError):
    pass


@dataclass(frozen=True)
class RemoteImageResult:
    path: Path
    content_type: str
    size_bytes: int
    final_url: str


def validate_public_image_url(url: str, *, resolver: Resolver = socket.getaddrinfo) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise RemoteImageFetchError("Remote image URL must use HTTP or HTTPS.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise RemoteImageFetchError("Remote image URL is invalid.")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = resolver(parsed.hostname, port, type=socket.SOCK_STREAM)
    except (OSError, ValueError) as exc:
        raise RemoteImageFetchError("Remote image host could not be resolved.") from exc
    if not addresses:
        raise RemoteImageFetchError("Remote image host could not be resolved.")
    for address in addresses:
        try:
            resolved_ip = ipaddress.ip_address(address[4][0])
        except (IndexError, TypeError, ValueError) as exc:
            raise RemoteImageFetchError("Remote image host resolution is invalid.") from exc
        if not resolved_ip.is_global:
            raise RemoteImageFetchError("Remote image host must resolve only to public addresses.")


def download_remote_image(
    url: str,
    destination: str | Path,
    *,
    client: httpx.Client | None = None,
    resolver: Resolver = socket.getaddrinfo,
    max_bytes: int = MAX_REMOTE_IMAGE_BYTES,
    max_redirects: int = 3,
) -> RemoteImageResult:
    destination_path = Path(destination)
    partial_path = destination_path.with_name(f".{destination_path.name}.part")
    owned_client = client is None
    session = client or httpx.Client(
        timeout=httpx.Timeout(connect=5.0, read=20.0, write=20.0, pool=5.0),
        follow_redirects=False,
        trust_env=False,
    )
    current_url = url
    try:
        for redirect_count in range(max_redirects + 1):
            validate_public_image_url(current_url, resolver=resolver)
            with session.stream("GET", current_url, headers={"Accept": "image/*"}) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location", "").strip()
                    if not location or redirect_count >= max_redirects:
                        raise RemoteImageFetchError("Remote image exceeded the redirect limit.")
                    current_url = urljoin(current_url, location)
                    continue
                if not response.is_success:
                    raise RemoteImageFetchError(f"Remote image request failed with status {response.status_code}.")

                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if content_type not in ALLOWED_REMOTE_IMAGE_TYPES:
                    raise RemoteImageFetchError("Remote response does not have an image MIME type.")
                content_length = response.headers.get("content-length", "")
                if content_length.isdigit() and int(content_length) > max_bytes:
                    raise RemoteImageFetchError("Remote image exceeds the 25 MiB limit.")

                destination_path.parent.mkdir(parents=True, exist_ok=True)
                size_bytes = 0
                with partial_path.open("wb") as output:
                    for chunk in response.iter_bytes():
                        size_bytes += len(chunk)
                        if size_bytes > max_bytes:
                            raise RemoteImageFetchError("Remote image exceeds the 25 MiB limit.")
                        output.write(chunk)
                if size_bytes <= 0:
                    raise RemoteImageFetchError("Remote image is empty.")
                os.replace(partial_path, destination_path)
                return RemoteImageResult(destination_path, content_type, size_bytes, current_url)
        raise RemoteImageFetchError("Remote image exceeded the redirect limit.")
    except Exception:
        partial_path.unlink(missing_ok=True)
        raise
    finally:
        if owned_client:
            session.close()
