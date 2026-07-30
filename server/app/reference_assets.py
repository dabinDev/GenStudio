from __future__ import annotations

from typing import Any

from fastapi import HTTPException


REFERENCE_KEYS = {
    "image",
    "images",
    "image_url",
    "img_url",
    "reference_image",
    "reference_images",
    "first_frame",
    "last_frame",
    "start_image",
    "end_image",
    "mask",
}


def reference_role_from_key(key: str, fallback: str = "reference") -> str:
    normalized = key.strip().lower()
    if normalized in {"first_frame", "first-frame", "start_image", "start_frame"}:
        return "first_frame"
    if normalized in {"last_frame", "last-frame", "end_image", "end_frame"}:
        return "last_frame"
    if normalized == "mask":
        return "mask"
    return fallback


def reference_label(role: str) -> str:
    return {
        "first_frame": "首帧",
        "last_frame": "尾帧",
        "mask": "蒙版",
    }.get(role, "参考图")


def is_storable_reference_url(value: str) -> bool:
    clean = value.strip()
    return clean.startswith("/api/assets/") or clean.startswith("http://") or clean.startswith("https://")


def _collect_reference_image_assets(value: Any, *, storable_only: bool) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(url: str, role: str) -> None:
        clean = url.strip()
        if not clean or clean in seen or (storable_only and not is_storable_reference_url(clean)):
            return
        seen.add(clean)
        references.append({"url": clean, "role": role, "label": reference_label(role)})

    def collect(item: Any, role: str = "reference", active: bool = False) -> None:
        if isinstance(item, str):
            if active:
                add(item, role)
            return
        if isinstance(item, list):
            for child in item:
                collect(child, role, active)
            return
        if not isinstance(item, dict):
            return

        item_role = str(item.get("role") or role or "reference")
        if isinstance(item.get("image_url"), dict):
            url = item["image_url"].get("url")
            if isinstance(url, str):
                add(url, reference_role_from_key(item_role, item_role))
        if isinstance(item.get("url"), str) and active:
            add(item["url"], reference_role_from_key(item_role, item_role))

        for key, child in item.items():
            lower_key = key.lower()
            if lower_key in REFERENCE_KEYS:
                next_role = reference_role_from_key(lower_key, item_role)
                collect(child, next_role, True)
            elif lower_key in {"content", "input", "metadata"} or isinstance(child, (dict, list)):
                collect(child, item_role, False)

    collect(value)
    return references


def collect_reference_image_assets(value: Any) -> list[dict[str, str]]:
    return _collect_reference_image_assets(value, storable_only=True)


def validate_reference_limit(payload: Any, maximum: int = 10) -> int:
    count = len(_collect_reference_image_assets(payload, storable_only=False))
    if count > maximum:
        raise HTTPException(status_code=400, detail={"message": f"参考图片最多支持 {maximum} 张。"})
    return count


def indexed_reference_metadata(index: int, role: str, label: str) -> dict[str, Any]:
    return {
        "role": role or "reference",
        "label": label or "参考图",
        "source": "input",
        "index": index + 1,
    }
