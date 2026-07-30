from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.credit_service import json_dumps_safe, parse_json_object
from app.db_models import GeneratedAsset, SystemSetting, User, utcnow


ASSET_CLEANUP_RETENTION_DAYS_KEY = "asset_cleanup_retention_days"
ASSET_CLEANUP_ENABLED_KEY = "asset_cleanup_enabled"
ASSET_CLEANUP_LAST_RUN_KEY = "asset_cleanup_last_run"
ASSET_CLEANUP_LAST_AUTO_RUN_KEY = "asset_cleanup_last_auto_run"
DEFAULT_ASSET_CLEANUP_RETENTION_DAYS = 7
MIN_ASSET_CLEANUP_RETENTION_DAYS = 1
MAX_ASSET_CLEANUP_RETENTION_DAYS = 365
ASSET_CLEANUP_TARGETS = (
    ("generated", "生成图片缓存"),
    ("uploaded", "上传参考图缓存"),
)


@dataclass(frozen=True)
class CleanupTarget:
    key: str
    label: str
    directory: Path


def _setting_value(db: Session, key: str, default: str = "") -> str:
    item = db.get(SystemSetting, key)
    return item.value if item and item.value not in (None, "") else default


def _set_setting(db: Session, key: str, value: str, *, admin: User | None = None) -> SystemSetting:
    item = db.get(SystemSetting, key)
    if not item:
        item = SystemSetting(key=key)
        db.add(item)
    item.value = value
    item.updated_by = admin.id if admin else item.updated_by
    item.updated_at = utcnow()
    db.commit()
    db.refresh(item)
    return item


def normalize_retention_days(value: Any) -> int:
    try:
        days = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail={"message": "缓存保留天数必须是整数。"})
    if days < MIN_ASSET_CLEANUP_RETENTION_DAYS:
        raise HTTPException(status_code=400, detail={"message": "缓存保留天数不能小于 1 天。"})
    if days > MAX_ASSET_CLEANUP_RETENTION_DAYS:
        raise HTTPException(status_code=400, detail={"message": "缓存保留天数不能超过 365 天。"})
    return days


def asset_cleanup_settings(db: Session) -> dict[str, Any]:
    raw_days = _setting_value(db, ASSET_CLEANUP_RETENTION_DAYS_KEY, str(DEFAULT_ASSET_CLEANUP_RETENTION_DAYS))
    try:
        retention_days = normalize_retention_days(raw_days)
    except HTTPException:
        retention_days = DEFAULT_ASSET_CLEANUP_RETENTION_DAYS
    enabled = _setting_value(db, ASSET_CLEANUP_ENABLED_KEY, "true").strip().lower() != "false"
    last_run = parse_json_object(_setting_value(db, ASSET_CLEANUP_LAST_RUN_KEY, "{}"), {})
    return {
        "enabled": enabled,
        "retentionDays": retention_days,
        "defaultRetentionDays": DEFAULT_ASSET_CLEANUP_RETENTION_DAYS,
        "minRetentionDays": MIN_ASSET_CLEANUP_RETENTION_DAYS,
        "maxRetentionDays": MAX_ASSET_CLEANUP_RETENTION_DAYS,
        "lastRun": last_run if isinstance(last_run, dict) else {},
    }


def update_asset_cleanup_settings(
    db: Session,
    *,
    admin: User,
    enabled: bool | None = None,
    retention_days: Any = None,
) -> dict[str, Any]:
    if enabled is not None:
        _set_setting(db, ASSET_CLEANUP_ENABLED_KEY, "true" if enabled else "false", admin=admin)
    if retention_days is not None:
        _set_setting(
            db,
            ASSET_CLEANUP_RETENTION_DAYS_KEY,
            str(normalize_retention_days(retention_days)),
            admin=admin,
        )
    return asset_cleanup_settings(db)


def build_cleanup_targets(generated_dir: Path, uploaded_dir: Path) -> list[CleanupTarget]:
    return [
        CleanupTarget("generated", "生成图片缓存", generated_dir),
        CleanupTarget("uploaded", "上传参考图缓存", uploaded_dir),
    ]


def _safe_files(directory: Path) -> list[Path]:
    try:
        root = directory.resolve()
    except OSError:
        return []
    if not root.exists() or not root.is_dir():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if not resolved.is_file() or root not in resolved.parents:
            continue
        files.append(resolved)
    return files


def _file_row(path: Path, cutoff_ts: float) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "name": path.name,
        "sizeBytes": stat.st_size,
        "mtime": stat.st_mtime,
        "expired": stat.st_mtime < cutoff_ts,
    }


def _path_key(path: str | Path) -> str:
    try:
        return str(Path(path).resolve()).casefold()
    except OSError:
        return ""


def tracked_unsynced_asset_paths(db: Session) -> set[str]:
    protected: set[str] = set()
    assets = db.query(GeneratedAsset).filter(
        (GeneratedAsset.local_path != "") | (GeneratedAsset.local_thumbnail_path != "")
    ).all()
    for asset in assets:
        has_verified_r2_copy = bool(
            asset.storage_status == "r2_synced"
            and asset.r2_object_key
            and asset.r2_thumbnail_key
            and asset.r2_url
            and asset.r2_thumbnail_url
        )
        if has_verified_r2_copy:
            continue
        for value in (asset.local_path, asset.local_thumbnail_path):
            key = _path_key(value) if value else ""
            if key:
                protected.add(key)
    return protected


def preview_asset_cleanup(
    *,
    targets: list[CleanupTarget],
    retention_days: int,
    now_ts: float | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    clean_days = normalize_retention_days(retention_days)
    resolved_now = time.time() if now_ts is None else float(now_ts)
    cutoff_ts = resolved_now - clean_days * 86400
    target_rows: list[dict[str, Any]] = []
    total_files = 0
    expired_files = 0
    total_bytes = 0
    expired_bytes = 0
    protected_files = 0
    protected_paths = tracked_unsynced_asset_paths(db) if db is not None else set()
    for target in targets:
        files = []
        for file_path in _safe_files(target.directory):
            try:
                row = _file_row(file_path, cutoff_ts)
            except OSError:
                continue
            files.append(row)
            total_files += 1
            total_bytes += int(row["sizeBytes"])
            row["protected"] = _path_key(file_path) in protected_paths
            if row["protected"]:
                protected_files += 1
            if row["expired"] and not row["protected"]:
                expired_files += 1
                expired_bytes += int(row["sizeBytes"])
        target_rows.append(
            {
                "key": target.key,
                "label": target.label,
                "path": str(target.directory),
                "totalFiles": len(files),
                "expiredFiles": sum(1 for item in files if item["expired"] and not item["protected"]),
                "protectedFiles": sum(1 for item in files if item["protected"]),
                "totalBytes": sum(int(item["sizeBytes"]) for item in files),
                "expiredBytes": sum(
                    int(item["sizeBytes"])
                    for item in files
                    if item["expired"] and not item["protected"]
                ),
            }
        )
    return {
        "retentionDays": clean_days,
        "cutoffTs": cutoff_ts,
        "totalFiles": total_files,
        "expiredFiles": expired_files,
        "protectedFiles": protected_files,
        "totalBytes": total_bytes,
        "expiredBytes": expired_bytes,
        "targets": target_rows,
    }


def run_asset_cleanup(
    db: Session,
    *,
    targets: list[CleanupTarget],
    retention_days: int,
    admin: User | None = None,
    now_ts: float | None = None,
) -> dict[str, Any]:
    clean_days = normalize_retention_days(retention_days)
    resolved_now = time.time() if now_ts is None else float(now_ts)
    cutoff_ts = resolved_now - clean_days * 86400
    protected_paths = tracked_unsynced_asset_paths(db)
    preview = preview_asset_cleanup(
        targets=targets,
        retention_days=clean_days,
        now_ts=resolved_now,
        db=db,
    )
    deleted_files = 0
    deleted_bytes = 0
    failed: list[dict[str, Any]] = []
    for target in targets:
        for file_path in _safe_files(target.directory):
            try:
                stat = file_path.stat()
            except OSError as exc:
                failed.append({"path": str(file_path), "message": str(exc)[:200]})
                continue
            if stat.st_mtime >= cutoff_ts:
                continue
            if _path_key(file_path) in protected_paths:
                continue
            try:
                file_path.unlink()
                deleted_files += 1
                deleted_bytes += stat.st_size
            except OSError as exc:
                failed.append({"path": str(file_path), "message": str(exc)[:200]})
    summary = {
        **preview,
        "deletedFiles": deleted_files,
        "deletedBytes": deleted_bytes,
        "failedFiles": len(failed),
        "failures": failed[:20],
        "ranAt": utcnow().isoformat(),
    }
    _set_setting(db, ASSET_CLEANUP_LAST_RUN_KEY, json_dumps_safe(summary), admin=admin)
    return summary


def maybe_run_scheduled_asset_cleanup(
    db: Session,
    *,
    targets: list[CleanupTarget],
    now_ts: float | None = None,
) -> dict[str, Any] | None:
    settings = asset_cleanup_settings(db)
    if not settings["enabled"]:
        return None
    resolved_now = time.time() if now_ts is None else float(now_ts)
    last_auto_raw = _setting_value(db, ASSET_CLEANUP_LAST_AUTO_RUN_KEY, "0")
    try:
        last_auto_ts = float(last_auto_raw)
    except (TypeError, ValueError):
        last_auto_ts = 0
    if resolved_now - last_auto_ts < 86400:
        return None
    _set_setting(db, ASSET_CLEANUP_LAST_AUTO_RUN_KEY, str(resolved_now))
    try:
        return run_asset_cleanup(
            db,
            targets=targets,
            retention_days=int(settings["retentionDays"]),
            now_ts=resolved_now,
        )
    except Exception as exc:
        failure = {
            "status": "failed",
            "message": str(exc)[:300] or exc.__class__.__name__,
            "ranAt": utcnow().isoformat(),
            "retentionDays": int(settings["retentionDays"]),
        }
        _set_setting(db, ASSET_CLEANUP_LAST_RUN_KEY, json_dumps_safe(failure))
        return None
