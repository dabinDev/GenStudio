from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import mimetypes
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import and_, func, or_

from app.asset_images import create_thumbnail, resolve_managed_path
from app.asset_storage import materialize_remote_asset
from app.db_models import GeneratedAsset, utcnow


@dataclass(frozen=True)
class AssetSyncConfig:
    interval_seconds: int = 60
    local_ttl: timedelta = timedelta(hours=24)
    syncing_timeout: timedelta = timedelta(minutes=15)
    batch_size: int = 8


def retry_delay_for_attempt(attempts: int) -> timedelta:
    if attempts <= 1:
        return timedelta(minutes=1)
    if attempts == 2:
        return timedelta(minutes=5)
    return timedelta(minutes=30)


class AssetSyncService:
    def __init__(
        self,
        session_factory,
        object_store,
        generated_root: str | Path,
        uploaded_root: str | Path,
        *,
        config: AssetSyncConfig | None = None,
        key_prefix: str = "genstudio",
    ) -> None:
        self._session_factory = session_factory
        self._object_store = object_store
        self._generated_root = Path(generated_root).resolve()
        self._uploaded_root = Path(uploaded_root).resolve()
        self.config = config or AssetSyncConfig()
        self._key_prefix = key_prefix.strip().strip("/")

    def _eligibility(self, now):
        stale_before = now - self.config.syncing_timeout
        return or_(
            GeneratedAsset.storage_status.in_(("local_pending", "remote_pending")),
            and_(GeneratedAsset.storage_status == "syncing", GeneratedAsset.storage_updated_at <= stale_before),
            and_(
                GeneratedAsset.storage_status == "sync_failed",
                or_(
                    and_(GeneratedAsset.sync_attempts <= 1, GeneratedAsset.storage_updated_at <= now - timedelta(minutes=1)),
                    and_(GeneratedAsset.sync_attempts == 2, GeneratedAsset.storage_updated_at <= now - timedelta(minutes=5)),
                    and_(GeneratedAsset.sync_attempts >= 3, GeneratedAsset.storage_updated_at <= now - timedelta(minutes=30)),
                ),
            ),
        )

    def _claim(self, asset_id: str, now=None) -> bool:
        current_time = now or utcnow()
        with self._session_factory() as db:
            updated = (
                db.query(GeneratedAsset)
                .filter(GeneratedAsset.id == asset_id, self._eligibility(current_time))
                .update(
                    {
                        GeneratedAsset.storage_status: "syncing",
                        GeneratedAsset.sync_attempts: func.coalesce(GeneratedAsset.sync_attempts, 0) + 1,
                        GeneratedAsset.storage_updated_at: current_time,
                    },
                    synchronize_session=False,
                )
            )
            db.commit()
            return updated == 1

    def _managed_path(self, value: str) -> Path:
        candidate = Path(value).resolve()
        if not any(candidate.is_relative_to(root) for root in (self._generated_root, self._uploaded_root)):
            raise ValueError("Asset path is outside the managed roots.")
        return candidate

    def _root_for(self, path: Path) -> Path:
        for root in (self._generated_root, self._uploaded_root):
            if path.is_relative_to(root):
                return root
        raise ValueError("Asset path is outside the managed roots.")

    def _object_keys(self, asset: GeneratedAsset, source: Path) -> tuple[str, str]:
        created_at = asset.created_at or utcnow()
        prefix = f"{self._key_prefix}/" if self._key_prefix else ""
        base = f"{prefix}assets/{created_at:%Y/%m/%d}/{asset.id}"
        suffix = source.suffix.lower() if source.suffix.lower() in {".gif", ".jpeg", ".jpg", ".png", ".webp"} else ".img"
        return f"{base}/original{suffix}", f"{base}/thumbnail.webp"

    def _ensure_local_files(self, asset: GeneratedAsset) -> tuple[Path, Path]:
        if not asset.local_path:
            with httpx.Client(
                timeout=httpx.Timeout(connect=5.0, read=20.0, write=20.0, pool=5.0),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                materialize_remote_asset(asset, client, self._generated_root)
        source = self._managed_path(asset.local_path)
        if not source.is_file():
            raise FileNotFoundError(source)
        if not asset.local_thumbnail_path:
            root = self._root_for(source)
            thumbnail = resolve_managed_path(root, Path("thumbnails") / f"{asset.id}.webp")
            create_thumbnail(source, thumbnail)
            asset.local_thumbnail_path = str(thumbnail)
        thumbnail = self._managed_path(asset.local_thumbnail_path)
        if not thumbnail.is_file():
            raise FileNotFoundError(thumbnail)
        return source, thumbnail

    def _mark_failed(self, asset: GeneratedAsset, error: Exception, now) -> None:
        asset.storage_status = "sync_failed"
        asset.last_sync_error = str(error)[:2000] or error.__class__.__name__
        asset.storage_updated_at = now

    def _remove_expired_local_copy(self, asset: GeneratedAsset, now=None) -> bool:
        current_time = now or utcnow()
        if (
            asset.storage_status != "r2_synced"
            or not asset.r2_object_key
            or not asset.r2_thumbnail_key
            or not asset.r2_url
            or not asset.r2_thumbnail_url
            or not asset.local_expires_at
            or asset.local_expires_at > current_time
        ):
            return False
        paths = [value for value in (asset.local_path, asset.local_thumbnail_path) if value]
        if not paths:
            return False
        managed_paths = [self._managed_path(value) for value in paths]
        for path in managed_paths:
            path.unlink(missing_ok=True)
        asset.local_path = ""
        asset.local_thumbnail_path = ""
        asset.storage_updated_at = current_time
        return True

    def _sync_claimed(self, asset_id: str, now) -> tuple[bool, bool]:
        with self._session_factory() as db:
            asset = db.get(GeneratedAsset, asset_id)
            if not asset or asset.storage_status != "syncing":
                return False, False
            try:
                source, thumbnail = self._ensure_local_files(asset)
                original_key, thumbnail_key = self._object_keys(asset, source)
                original_content_type = asset.content_type or mimetypes.guess_type(source.name)[0] or "application/octet-stream"
                self._object_store.put_file(source, original_key, original_content_type)
                self._object_store.put_file(thumbnail, thumbnail_key, "image/webp")
                self._object_store.head(original_key)
                self._object_store.head(thumbnail_key)
                asset.r2_object_key = original_key
                asset.r2_thumbnail_key = thumbnail_key
                asset.r2_url = self._object_store.public_url(original_key)
                asset.r2_thumbnail_url = self._object_store.public_url(thumbnail_key)
                asset.storage_status = "r2_synced"
                asset.synced_at = now
                asset.storage_updated_at = now
                asset.last_sync_error = ""
                removed = self._remove_expired_local_copy(asset, now)
                db.commit()
                return True, removed
            except Exception as exc:
                self._mark_failed(asset, exc, now)
                db.commit()
                return False, False

    def _cleanup_synced(self, now) -> int:
        removed = 0
        with self._session_factory() as db:
            assets = (
                db.query(GeneratedAsset)
                .filter(
                    GeneratedAsset.storage_status == "r2_synced",
                    GeneratedAsset.local_expires_at.is_not(None),
                    GeneratedAsset.local_expires_at <= now,
                    or_(GeneratedAsset.local_path != "", GeneratedAsset.local_thumbnail_path != ""),
                )
                .order_by(GeneratedAsset.local_expires_at.asc())
                .limit(self.config.batch_size)
                .all()
            )
            for asset in assets:
                if self._remove_expired_local_copy(asset, now):
                    removed += 1
            db.commit()
        return removed

    def sync_once(self, now=None) -> dict[str, int]:
        current_time = now or utcnow()
        with self._session_factory() as db:
            candidate_ids = [
                asset_id
                for (asset_id,) in (
                    db.query(GeneratedAsset.id)
                    .filter(self._eligibility(current_time))
                    .order_by(GeneratedAsset.storage_updated_at.asc(), GeneratedAsset.id.asc())
                    .limit(self.config.batch_size)
                    .all()
                )
            ]

        summary = {"claimed": 0, "synced": 0, "failed": 0, "removed": 0}
        for asset_id in candidate_ids:
            if not self._claim(asset_id, current_time):
                continue
            summary["claimed"] += 1
            synced, removed = self._sync_claimed(asset_id, current_time)
            summary["synced" if synced else "failed"] += 1
            summary["removed"] += int(removed)
        summary["removed"] += self._cleanup_synced(current_time)
        return summary
