from __future__ import annotations

import socket
from urllib.parse import parse_qs

import httpx
import pytest

from app.asset_fetch import RemoteImageFetchError, download_remote_image, validate_public_image_url


def resolver_for(address: str):
    def resolve(_host: str, port: int, type=socket.SOCK_STREAM):
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        sockaddr = (address, port, 0, 0) if family == socket.AF_INET6 else (address, port)
        return [(family, type, 6, "", sockaddr)]

    return resolve


@pytest.mark.parametrize(
    ("url", "address"),
    [
        ("http://localhost/image.png", "127.0.0.1"),
        ("https://private.test/image.png", "10.10.0.1"),
        ("https://private.test/image.png", "172.16.0.1"),
        ("https://private.test/image.png", "192.168.1.20"),
        ("https://link-local.test/image.png", "169.254.1.2"),
        ("https://loopback-v6.test/image.png", "::1"),
    ],
)
def test_validate_public_image_url_rejects_non_public_targets(url, address) -> None:
    with pytest.raises(RemoteImageFetchError, match="public"):
        validate_public_image_url(url, resolver=resolver_for(address))


def test_validate_public_image_url_rejects_non_http_schemes() -> None:
    with pytest.raises(RemoteImageFetchError, match="HTTP"):
        validate_public_image_url("file:///etc/passwd")


def test_download_remote_image_rejects_excessive_redirects(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        hop = int(parse_qs(request.url.query.decode()).get("hop", ["0"])[0])
        return httpx.Response(302, headers={"Location": f"https://images.test/file.png?hop={hop + 1}"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RemoteImageFetchError, match="redirect"):
            download_remote_image(
                "https://images.test/file.png?hop=0",
                tmp_path / "image.png",
                client=client,
                resolver=resolver_for("93.184.216.34"),
                max_redirects=3,
            )


def test_download_remote_image_rejects_oversized_streams(tmp_path) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, headers={"Content-Type": "image/png"}, content=b"12345")
    )

    with httpx.Client(transport=transport) as client:
        with pytest.raises(RemoteImageFetchError, match="25 MiB"):
            download_remote_image(
                "https://images.test/file.png",
                tmp_path / "image.png",
                client=client,
                resolver=resolver_for("93.184.216.34"),
                max_bytes=4,
            )


def test_download_remote_image_rejects_non_image_mime(tmp_path) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, headers={"Content-Type": "text/html"}, content=b"not an image")
    )

    with httpx.Client(transport=transport) as client:
        with pytest.raises(RemoteImageFetchError, match="image MIME"):
            download_remote_image(
                "https://images.test/file.png",
                tmp_path / "image.png",
                client=client,
                resolver=resolver_for("93.184.216.34"),
            )


def test_download_remote_image_rejects_active_svg_content(tmp_path) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            headers={"Content-Type": "image/svg+xml"},
            content=b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        )
    )

    with httpx.Client(transport=transport) as client:
        with pytest.raises(RemoteImageFetchError, match="image MIME"):
            download_remote_image(
                "https://images.test/file.svg",
                tmp_path / "image.svg",
                client=client,
                resolver=resolver_for("93.184.216.34"),
            )


def test_download_remote_image_streams_a_valid_response(tmp_path) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, headers={"Content-Type": "image/png"}, content=b"png-bytes")
    )
    destination = tmp_path / "nested" / "image.png"

    with httpx.Client(transport=transport) as client:
        result = download_remote_image(
            "https://images.test/file.png",
            destination,
            client=client,
            resolver=resolver_for("93.184.216.34"),
        )

    assert destination.read_bytes() == b"png-bytes"
    assert result.content_type == "image/png"
    assert result.size_bytes == 9
