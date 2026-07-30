from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import httpx
import os
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace

from PIL import Image
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.gettempdir()) / 'genstudio-asset-storage-test.sqlite3'}"

NOW = datetime(2026, 7, 30, 8, 0, 0)

from app.asset_storage import (
    backfill_asset_storage,
    materialize_remote_asset,
    register_asset_storage,
    resolve_asset_delivery,
)
from app.conversation_service import serialize_asset
from app.database import Base
from app.db_models import GeneratedAsset


def test_generated_asset_defaults_to_local_pending() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        asset = GeneratedAsset(
            user_id="user-1",
            conversation_id="conversation-1",
            message_id="message-1",
            capability="image",
            asset_type="image",
            url="/api/assets/generated/result.png",
        )
        db.add(asset)
        db.flush()

        assert asset.storage_status == "local_pending"
        assert asset.local_expires_at is None
        assert asset.size_bytes == 0
        assert asset.sync_attempts == 0


def storage_settings():
    return SimpleNamespace(
        object_storage_public_base_url="https://cdn.example.com/assets",
    )


def add_test_asset(db: Session, url: str) -> GeneratedAsset:
    asset = GeneratedAsset(
        user_id="user-1",
        conversation_id="conversation-1",
        message_id=f"message-{hash(url)}",
        capability="image",
        asset_type="image",
        url=url,
    )
    db.add(asset)
    db.flush()
    return asset


def write_png(path: Path) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 400), color=(40, 80, 120)).save(path, format="PNG")
    return path.read_bytes()


def public_resolver(_host: str, port: int, type=socket.SOCK_STREAM):
    return [(socket.AF_INET, type, 6, "", ("93.184.216.34", port))]


def test_register_local_asset_records_hash_thumbnail_and_expiry(tmp_path) -> None:
    generated_root = tmp_path / "generated_assets"
    uploaded_root = tmp_path / "uploaded_assets"
    image_bytes = write_png(generated_root / "result.png")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        asset = add_test_asset(db, "/api/assets/generated/result.png")

        register_asset_storage(asset, generated_root, uploaded_root, storage_settings(), asset.created_at)

        assert asset.storage_status == "local_pending"
        assert Path(asset.local_path) == (generated_root / "result.png").resolve()
        assert Path(asset.local_thumbnail_path).is_file()
        assert asset.sha256 == hashlib.sha256(image_bytes).hexdigest()
        assert asset.size_bytes == len(image_bytes)
        assert asset.local_expires_at == asset.created_at + timedelta(hours=24)


def test_backfill_classifies_local_r2_and_unknown_remote_assets(tmp_path) -> None:
    generated_root = tmp_path / "generated_assets"
    uploaded_root = tmp_path / "uploaded_assets"
    write_png(generated_root / "legacy.png")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        local = add_test_asset(db, "/api/assets/generated/legacy.png")
        r2 = add_test_asset(db, "https://cdn.example.com/assets/2026/07/r2.png")
        remote = add_test_asset(db, "https://provider.example.com/result.png")

        assert backfill_asset_storage(
            db,
            generated_root,
            uploaded_root,
            storage_settings(),
            local.created_at,
            batch_size=10,
        ) == 3

        assert local.storage_status == "local_pending"
        assert r2.storage_status == "r2_synced"
        assert r2.r2_url == r2.url
        assert r2.r2_object_key == "2026/07/r2.png"
        assert remote.storage_status == "remote_pending"
        assert remote.url == "https://provider.example.com/result.png"

        assert backfill_asset_storage(
            db,
            generated_root,
            uploaded_root,
            storage_settings(),
            local.created_at,
            batch_size=10,
        ) == 0


def test_backfill_skips_missing_local_files_and_continues(tmp_path) -> None:
    generated_root = tmp_path / "generated_assets"
    uploaded_root = tmp_path / "uploaded_assets"
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        missing = add_test_asset(db, "/api/assets/uploads/missing.png")
        remote = add_test_asset(db, "https://provider.example.com/result.png")

        assert backfill_asset_storage(
            db,
            generated_root,
            uploaded_root,
            storage_settings(),
            missing.created_at,
            batch_size=10,
        ) == 2

        assert missing.storage_status == "unmanaged"
        assert missing.last_sync_error == "Local asset file not found."
        assert remote.storage_status == "remote_pending"

        assert backfill_asset_storage(
            db,
            generated_root,
            uploaded_root,
            storage_settings(),
            missing.created_at,
            batch_size=10,
        ) == 0


def test_materialize_remote_asset_keeps_original_url_and_creates_local_thumbnail(tmp_path) -> None:
    generated_root = tmp_path / "generated_assets"
    source = tmp_path / "source.png"
    image_bytes = write_png(source)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, headers={"Content-Type": "image/png"}, content=image_bytes)
    )

    with Session(engine) as db, httpx.Client(transport=transport) as client:
        asset = add_test_asset(db, "https://provider.example.com/result.png")

        materialized = materialize_remote_asset(
            asset,
            client,
            generated_root,
            now=asset.created_at,
            resolver=public_resolver,
        )

        assert materialized.read_bytes() == image_bytes
        assert Path(asset.local_thumbnail_path).is_file()
        assert asset.storage_status == "local_pending"
        assert asset.content_type == "image/png"
        assert asset.url == "https://provider.example.com/result.png"


def test_materialize_remote_asset_removes_content_that_cannot_be_decoded(tmp_path) -> None:
    generated_root = tmp_path / "generated_assets"
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, headers={"Content-Type": "image/png"}, content=b"not-a-real-png")
    )

    with Session(engine) as db, httpx.Client(transport=transport) as client:
        asset = add_test_asset(db, "https://provider.example.com/forged.png")

        with pytest.raises(ValueError, match="supported image"):
            materialize_remote_asset(
                asset,
                client,
                generated_root,
                now=asset.created_at,
                resolver=public_resolver,
            )

        assert not list((generated_root / "materialized").glob("*"))
        assert not asset.local_path


def delivery_asset() -> GeneratedAsset:
    return GeneratedAsset(
        id="asset-delivery",
        user_id="user-1",
        conversation_id="conversation-1",
        message_id="message-delivery",
        capability="image",
        asset_type="image",
        url="/api/assets/generated/result.png",
        thumbnail_url="",
        metadata_json='{"role":"result"}',
        storage_status="r2_synced",
        local_path="C:/managed/result.png",
        local_thumbnail_path="C:/managed/result.webp",
        r2_object_key="assets/result.png",
        r2_thumbnail_key="assets/result.webp",
        r2_url="https://cdn.example.com/assets/result.png",
        r2_thumbnail_url="https://cdn.example.com/assets/result.webp",
        local_expires_at=NOW + timedelta(hours=24),
        created_at=NOW,
        storage_updated_at=NOW,
    )


def test_delivery_uses_local_routes_until_the_cache_boundary() -> None:
    asset = delivery_asset()

    assert resolve_asset_delivery(asset, NOW + timedelta(hours=23, minutes=59, seconds=59)) == {
        "url": "/api/assets/asset-delivery/content",
        "thumbnail_url": "/api/assets/asset-delivery/thumbnail",
    }


def test_delivery_switches_to_r2_at_exactly_twenty_four_hours() -> None:
    asset = delivery_asset()

    assert resolve_asset_delivery(asset, NOW + timedelta(hours=24)) == {
        "url": "https://cdn.example.com/assets/result.png",
        "thumbnail_url": "https://cdn.example.com/assets/result.webp",
    }


def test_failed_delivery_keeps_local_routes_and_serializes_only_safe_status_metadata() -> None:
    asset = delivery_asset()
    asset.storage_status = "sync_failed"
    asset.last_sync_error = "secret-bearing-provider-error"

    delivery = resolve_asset_delivery(asset, NOW + timedelta(days=2))
    serialized = serialize_asset(asset, now=NOW + timedelta(days=2))

    assert delivery["url"] == "/api/assets/asset-delivery/content"
    assert serialized.metadata == {"role": "result", "storageStatus": "sync_failed"}
    serialized_json = serialized.model_dump_json()
    assert "secret-bearing-provider-error" not in serialized_json
    assert "r2_object_key" not in serialized_json
