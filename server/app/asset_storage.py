from __future__ import annotations

from datetime import timedelta
import hashlib
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.asset_fetch import download_remote_image
from app.asset_images import create_thumbnail, resolve_managed_path
from app.db_models import GeneratedAsset, utcnow


DEFAULT_GENERATED_ROOT = Path(__file__).resolve().parents[2] / "generated_assets"
DEFAULT_UPLOADED_ROOT = Path(__file__).resolve().parents[2] / "uploaded_assets"
LOCAL_TTL = timedelta(hours=24)


def _local_source(asset_url: str, generated_root: Path, uploaded_root: Path) -> tuple[Path, Path] | None:
    path = urlparse(asset_url).path
    for prefix, root in (
        ("/api/assets/generated/", generated_root),
        ("/api/assets/uploads/", uploaded_root),
    ):
        if not path.startswith(prefix):
            continue
        raw_name = unquote(path.removeprefix(prefix))
        if not raw_name or Path(raw_name).name != raw_name:
            raise ValueError("Asset URL is outside the managed root.")
        return resolve_managed_path(root, raw_name), root
    return None


def _r2_object_key(url: str, public_base_url: str) -> str:
    base = public_base_url.rstrip("/")
    if not base or not (url == base or url.startswith(f"{base}/")):
        return ""
    return unquote(url.removeprefix(base).lstrip("/"))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _set_local_metadata(asset: GeneratedAsset, source: Path, root: Path, now) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    asset.local_path = str(source.resolve())
    asset.size_bytes = source.stat().st_size
    asset.sha256 = _file_sha256(source)
    asset.content_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    asset.local_expires_at = (asset.created_at or now) + LOCAL_TTL
    thumbnail_path = resolve_managed_path(root, Path("thumbnails") / f"{asset.id}.webp")
    try:
        create_thumbnail(source, thumbnail_path)
        asset.local_thumbnail_path = str(thumbnail_path)
        asset.last_sync_error = ""
    except ValueError as exc:
        asset.local_thumbnail_path = ""
        asset.last_sync_error = str(exc)
    asset.storage_status = "local_pending"
    asset.storage_updated_at = now


def register_asset_storage(
    asset: GeneratedAsset,
    generated_root: str | Path,
    uploaded_root: str | Path,
    settings: Any,
    now=None,
) -> GeneratedAsset:
    current_time = now or utcnow()
    generated = Path(generated_root).resolve()
    uploaded = Path(uploaded_root).resolve()
    if asset.asset_type != "image":
        asset.storage_status = "unmanaged"
        asset.storage_updated_at = current_time
        return asset

    local_source = _local_source(asset.url, generated, uploaded)
    if local_source:
        source, root = local_source
        _set_local_metadata(asset, source, root, current_time)
        return asset

    public_base_url = str(getattr(settings, "object_storage_public_base_url", "") or "")
    object_key = _r2_object_key(asset.url, public_base_url)
    if object_key:
        asset.storage_status = "r2_synced"
        asset.r2_url = asset.url
        asset.r2_object_key = object_key
        thumbnail_key = _r2_object_key(asset.thumbnail_url or "", public_base_url)
        if thumbnail_key:
            asset.r2_thumbnail_url = asset.thumbnail_url
            asset.r2_thumbnail_key = thumbnail_key
        asset.synced_at = asset.synced_at or current_time
        asset.storage_updated_at = current_time
        return asset

    asset.storage_status = "remote_pending"
    asset.storage_updated_at = current_time
    return asset


def backfill_asset_storage(
    db: Session,
    generated_root: str | Path,
    uploaded_root: str | Path,
    settings: Any,
    now=None,
    *,
    batch_size: int = 100,
) -> int:
    candidates = (
        db.query(GeneratedAsset)
        .filter(
            GeneratedAsset.asset_type == "image",
            or_(
                GeneratedAsset.storage_status.is_(None),
                GeneratedAsset.storage_status == "",
                and_(
                    GeneratedAsset.storage_status == "local_pending",
                    or_(GeneratedAsset.local_path.is_(None), GeneratedAsset.local_path == ""),
                    or_(GeneratedAsset.r2_url.is_(None), GeneratedAsset.r2_url == ""),
                ),
            ),
        )
        .order_by(GeneratedAsset.created_at.asc(), GeneratedAsset.id.asc())
        .limit(max(1, batch_size))
        .all()
    )
    for asset in candidates:
        register_asset_storage(asset, generated_root, uploaded_root, settings, now)
    db.flush()
    return len(candidates)


def materialize_remote_asset(
    asset: GeneratedAsset,
    client,
    root: str | Path,
    *,
    now=None,
    resolver=None,
) -> Path:
    current_time = now or utcnow()
    managed_root = Path(root).resolve()
    suffix = Path(urlparse(asset.url).path).suffix.lower()
    if suffix not in {".gif", ".jpeg", ".jpg", ".png", ".webp"}:
        suffix = ".img"
    destination = resolve_managed_path(managed_root, Path("materialized") / f"{asset.id}{suffix}")
    fetch_options = {"client": client}
    if resolver is not None:
        fetch_options["resolver"] = resolver
    result = download_remote_image(asset.url, destination, **fetch_options)
    _set_local_metadata(asset, destination, managed_root, current_time)
    if not asset.local_thumbnail_path:
        error_message = asset.last_sync_error or "File is not a supported image."
        destination.unlink(missing_ok=True)
        asset.local_path = ""
        asset.size_bytes = 0
        asset.sha256 = ""
        asset.storage_status = "remote_pending"
        raise ValueError(error_message)
    asset.content_type = result.content_type
    return destination
