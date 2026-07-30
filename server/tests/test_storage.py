from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.storage import ObjectStorageClient


class FakeS3Client:
    def __init__(self) -> None:
        self.uploads: list[dict] = []
        self.heads: list[dict] = []
        self.deletes: list[dict] = []
        self.downloads: list[dict] = []
        self.gets: list[dict] = []
        self.content_length = 123
        self.content_type = "image/png"
        self.content = b"image-content"

    def upload_file(self, **kwargs) -> None:
        self.uploads.append(kwargs)

    def head_object(self, **kwargs) -> dict:
        self.heads.append(kwargs)
        return {"ContentLength": self.content_length, "ContentType": "image/png", "ETag": '"etag"'}

    def delete_object(self, **kwargs) -> None:
        self.deletes.append(kwargs)

    def download_file(self, **kwargs) -> None:
        self.downloads.append(kwargs)

    def get_object(self, **kwargs) -> dict:
        self.gets.append(kwargs)
        return {
            "ContentLength": self.content_length,
            "ContentType": self.content_type,
            "Body": io.BytesIO(self.content),
        }


def storage_settings():
    return SimpleNamespace(
        object_storage_endpoint_url="https://account.r2.cloudflarestorage.com",
        object_storage_region="auto",
        object_storage_bucket="genstudio-assets",
        object_storage_access_key_id="access-key-secret",
        object_storage_secret_access_key="private-secret-value",
        object_storage_public_base_url="https://cdn.example.com/assets",
    )


def test_put_file_sends_exact_bucket_key_and_content_type(tmp_path) -> None:
    source = tmp_path / "image.png"
    source.write_bytes(b"image-content")
    fake = FakeS3Client()
    client = ObjectStorageClient(storage_settings(), client=fake)

    client.put_file(source, "2026/07/30/image.png", "image/png")

    assert fake.uploads == [
        {
            "Filename": str(source),
            "Bucket": "genstudio-assets",
            "Key": "2026/07/30/image.png",
            "ExtraArgs": {"ContentType": "image/png"},
        }
    ]


def test_head_requires_a_nonempty_object() -> None:
    fake = FakeS3Client()
    client = ObjectStorageClient(storage_settings(), client=fake)

    assert client.head("2026/07/30/image.png")["ContentLength"] == 123
    fake.content_length = 0
    with pytest.raises(ValueError, match="empty"):
        client.head("2026/07/30/empty.png")


def test_delete_and_download_target_the_exact_key(tmp_path) -> None:
    fake = FakeS3Client()
    client = ObjectStorageClient(storage_settings(), client=fake)
    destination = tmp_path / "downloaded.png"

    client.download_file("folder/original.png", destination)
    client.delete("folder/original.png")

    assert fake.downloads == [
        {"Bucket": "genstudio-assets", "Key": "folder/original.png", "Filename": str(destination)}
    ]
    assert fake.deletes == [{"Bucket": "genstudio-assets", "Key": "folder/original.png"}]


def test_public_url_encodes_path_components_but_preserves_slashes() -> None:
    client = ObjectStorageClient(storage_settings(), client=FakeS3Client())

    assert client.public_url("folder/space name/图.png") == (
        "https://cdn.example.com/assets/folder/space%20name/%E5%9B%BE.png"
    )


def test_object_key_from_public_url_accepts_only_the_configured_public_path() -> None:
    client = ObjectStorageClient(storage_settings(), client=FakeS3Client())

    assert client.object_key_from_public_url(
        "https://cdn.example.com/assets/folder/space%20name/reference.png?cache=1"
    ) == "folder/space name/reference.png"
    assert client.object_key_from_public_url("https://cdn.example.com/assets") is None
    assert client.object_key_from_public_url("https://cdn.example.com/assets-evil/reference.png") is None
    assert client.object_key_from_public_url("https://other.example.com/assets/reference.png") is None


def test_read_image_returns_bounded_image_content() -> None:
    fake = FakeS3Client()
    fake.content_length = len(fake.content)
    client = ObjectStorageClient(storage_settings(), client=fake)

    result = client.read_image("uploads/reference.png", max_bytes=1024)

    assert result == {
        "content": b"image-content",
        "content_type": "image/png",
        "filename": "reference.png",
    }
    assert fake.gets == [{"Bucket": "genstudio-assets", "Key": "uploads/reference.png"}]


@pytest.mark.parametrize(
    ("content", "content_length", "content_type", "message"),
    [
        (b"", 0, "image/png", "empty"),
        (b"not-an-image", 12, "text/plain", "image"),
        (b"too-large", 2048, "image/png", "large"),
    ],
)
def test_read_image_rejects_invalid_objects(content, content_length, content_type, message) -> None:
    fake = FakeS3Client()
    fake.content = content
    fake.content_length = content_length
    fake.content_type = content_type
    client = ObjectStorageClient(storage_settings(), client=fake)

    with pytest.raises(ValueError, match=message):
        client.read_image("uploads/reference.png", max_bytes=1024)


def test_repr_does_not_expose_credentials() -> None:
    client = ObjectStorageClient(storage_settings(), client=FakeS3Client())

    representation = repr(client)
    assert "access-key-secret" not in representation
    assert "private-secret-value" not in representation
    assert "genstudio-assets" in representation
