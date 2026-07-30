from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.asset_storage import register_asset_storage
from app.asset_sync import AssetSyncConfig, AssetSyncService, retry_delay_for_attempt
from app.database import Base
from app.db_models import GeneratedAsset


NOW = datetime(2026, 7, 30, 8, 0, 0)


class FakeObjectStore:
    def __init__(self, fail_on: str = "") -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail_on = fail_on

    def put_file(self, source: Path, key: str, content_type: str) -> None:
        self.calls.append(("put", key))
        if self.fail_on and self.fail_on in key:
            raise RuntimeError("simulated object storage failure")
        assert Path(source).is_file()
        assert content_type

    def head(self, key: str) -> dict:
        self.calls.append(("head", key))
        return {"ContentLength": 10}

    def public_url(self, key: str) -> str:
        return f"https://cdn.example.com/{key}"


def storage_settings():
    return SimpleNamespace(object_storage_public_base_url="https://cdn.example.com")


def make_service(tmp_path, store=None):
    database_path = tmp_path / "sync.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    generated_root = tmp_path / "generated_assets"
    uploaded_root = tmp_path / "uploaded_assets"
    service = AssetSyncService(
        factory,
        store or FakeObjectStore(),
        generated_root,
        uploaded_root,
        config=AssetSyncConfig(batch_size=8),
        key_prefix="genstudio",
    )
    return service, factory, generated_root, uploaded_root


def add_local_asset(factory, generated_root, uploaded_root, *, created_at=NOW, expires_at=None):
    generated_root.mkdir(parents=True, exist_ok=True)
    source = generated_root / f"source-{created_at.timestamp()}.png"
    Image.new("RGB", (800, 400), color=(20, 60, 100)).save(source, format="PNG")
    with factory() as db:
        asset = GeneratedAsset(
            user_id="user-1",
            conversation_id="conversation-1",
            message_id=f"message-{created_at.timestamp()}",
            capability="image",
            asset_type="image",
            url=f"/api/assets/generated/{source.name}",
            created_at=created_at,
        )
        db.add(asset)
        db.flush()
        register_asset_storage(asset, generated_root, uploaded_root, storage_settings(), created_at)
        if expires_at is not None:
            asset.local_expires_at = expires_at
        db.commit()
        return asset.id, Path(asset.local_path), Path(asset.local_thumbnail_path)


def load_asset(factory, asset_id):
    with factory() as db:
        return db.get(GeneratedAsset, asset_id)


def test_only_one_worker_claims_an_asset(tmp_path) -> None:
    service, factory, generated_root, uploaded_root = make_service(tmp_path)
    asset_id, _, _ = add_local_asset(factory, generated_root, uploaded_root)

    assert service._claim(asset_id, NOW) is True
    assert service._claim(asset_id, NOW) is False
    assert load_asset(factory, asset_id).storage_status == "syncing"


def test_stale_syncing_assets_can_be_reclaimed_after_fifteen_minutes(tmp_path) -> None:
    service, factory, generated_root, uploaded_root = make_service(tmp_path)
    asset_id, _, _ = add_local_asset(factory, generated_root, uploaded_root)
    with factory() as db:
        asset = db.get(GeneratedAsset, asset_id)
        asset.storage_status = "syncing"
        asset.storage_updated_at = NOW - timedelta(minutes=16)
        db.commit()

    assert service._claim(asset_id, NOW) is True


def test_sync_does_not_claim_unclassified_local_pending_assets(tmp_path) -> None:
    service, factory, _generated_root, _uploaded_root = make_service(tmp_path)
    with factory() as db:
        asset = GeneratedAsset(
            user_id="user-1",
            conversation_id="conversation-1",
            message_id="message-unclassified",
            capability="image",
            asset_type="image",
            url="/api/assets/uploads/missing.png",
            storage_status="local_pending",
            local_path="",
            r2_url="",
            created_at=NOW,
            storage_updated_at=NOW,
        )
        db.add(asset)
        db.commit()
        asset_id = asset.id

    result = service.sync_once(NOW)

    assert result == {"claimed": 0, "synced": 0, "failed": 0, "removed": 0}
    assert load_asset(factory, asset_id).storage_status == "local_pending"


def test_run_asset_sync_backfills_before_claiming(monkeypatch) -> None:
    from app import main as main_module

    events: list[str] = []
    settings = SimpleNamespace(object_storage_enabled=True, object_storage_key_prefix="genstudio")

    class FakeService:
        def __init__(self, *_args, **_kwargs) -> None:
            events.append("service")

        def sync_once(self):
            events.append("sync")
            return {"claimed": 1, "synced": 1, "failed": 0, "removed": 0}

    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    monkeypatch.setattr(main_module, "backfill_asset_storage_once", lambda: events.append("backfill") or 100)
    monkeypatch.setattr(main_module, "ObjectStorageClient", lambda _settings: object())
    monkeypatch.setattr(main_module, "AssetSyncService", FakeService)

    result = main_module.run_asset_sync_once(config=AssetSyncConfig())

    assert events == ["backfill", "service", "sync"]
    assert result == {"claimed": 1, "synced": 1, "failed": 0, "removed": 0, "backfilled": 100}


def test_retry_delays_are_one_five_then_thirty_minutes() -> None:
    assert retry_delay_for_attempt(1) == timedelta(minutes=1)
    assert retry_delay_for_attempt(2) == timedelta(minutes=5)
    assert retry_delay_for_attempt(3) == timedelta(minutes=30)
    assert retry_delay_for_attempt(8) == timedelta(minutes=30)


def test_sync_uploads_original_then_thumbnail_and_heads_both(tmp_path) -> None:
    store = FakeObjectStore()
    service, factory, generated_root, uploaded_root = make_service(tmp_path, store)
    asset_id, source, thumbnail = add_local_asset(factory, generated_root, uploaded_root)

    result = service.sync_once(NOW + timedelta(hours=1))

    asset = load_asset(factory, asset_id)
    assert result["synced"] == 1
    assert [name for name, _key in store.calls] == ["put", "put", "head", "head"]
    assert store.calls[0][1].endswith(f"/{asset_id}/original.png")
    assert store.calls[1][1].endswith(f"/{asset_id}/thumbnail.webp")
    assert asset.storage_status == "r2_synced"
    assert source.is_file()
    assert thumbnail.is_file()


def test_failed_sync_keeps_both_local_files(tmp_path) -> None:
    service, factory, generated_root, uploaded_root = make_service(tmp_path, FakeObjectStore("thumbnail.webp"))
    asset_id, source, thumbnail = add_local_asset(factory, generated_root, uploaded_root)

    result = service.sync_once(NOW + timedelta(hours=1))

    asset = load_asset(factory, asset_id)
    assert result["failed"] == 1
    assert asset.storage_status == "sync_failed"
    assert "simulated object storage failure" in asset.last_sync_error
    assert source.is_file()
    assert thumbnail.is_file()


def test_successful_sync_removes_expired_local_files(tmp_path) -> None:
    service, factory, generated_root, uploaded_root = make_service(tmp_path)
    asset_id, source, thumbnail = add_local_asset(
        factory,
        generated_root,
        uploaded_root,
        expires_at=NOW - timedelta(seconds=1),
    )

    result = service.sync_once(NOW)

    asset = load_asset(factory, asset_id)
    assert result["removed"] == 1
    assert asset.storage_status == "r2_synced"
    assert asset.local_path == ""
    assert asset.local_thumbnail_path == ""
    assert not source.exists()
    assert not thumbnail.exists()


def test_cleanup_never_deletes_the_only_unsynced_copy(tmp_path) -> None:
    service, factory, generated_root, uploaded_root = make_service(tmp_path)
    asset_id, source, thumbnail = add_local_asset(
        factory,
        generated_root,
        uploaded_root,
        expires_at=NOW - timedelta(days=1),
    )
    with factory() as db:
        asset = db.get(GeneratedAsset, asset_id)

        assert service._remove_expired_local_copy(asset, NOW) is False
        db.commit()

    assert source.is_file()
    assert thumbnail.is_file()
