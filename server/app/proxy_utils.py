from __future__ import annotations

from typing import Any
from urllib.parse import quote, urljoin, urlparse, urlunparse

import httpx
from fastapi import HTTPException


def validate_config(config: dict[str, Any] | None) -> tuple[str, str]:
    if not config or not str(config.get("baseUrl", "")).strip():
        raise HTTPException(status_code=400, detail={"message": "缺少 baseURL。"})

    if not str(config.get("apiKey", "")).strip():
        raise HTTPException(status_code=400, detail={"message": "缺少 API Key。"})

    return str(config["baseUrl"]).strip(), str(config["apiKey"]).strip()


def resolve_url(base_url: str, path: str) -> str:
    parsed = urlparse(base_url)
    base_path = parsed.path.rstrip("/") if parsed.path and parsed.path != "/" else ""
    target_path = path if path.startswith("/") else f"/{path}"

    if base_path and target_path.startswith(f"{base_path}/"):
        target_path = target_path[len(base_path) :]
    elif base_path and target_path == base_path:
        target_path = "/"

    joined_path = f"{base_path}{target_path}".replace("//", "/")
    return urlunparse(parsed._replace(path=joined_path, query="", fragment=""))


def auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }


async def parse_upstream(response: httpx.Response) -> dict[str, Any] | str:
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return response.json()
    return response.text


def pick_error_message(payload: Any, fallback: str) -> str:
    if not isinstance(payload, dict):
        return fallback

    error_value = payload.get("error")
    if isinstance(error_value, str):
        return error_value

    if isinstance(error_value, dict) and isinstance(error_value.get("message"), str):
        return error_value["message"]

    if isinstance(payload.get("message"), str):
        return payload["message"]

    return fallback


def _text_from_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        chunks = [_text_from_value(item).strip() for item in value]
        return "\n".join(chunk for chunk in chunks if chunk)
    if isinstance(value, dict):
        for key in ("text", "content", "output_text"):
            text = _text_from_value(value.get(key))
            if text:
                return text
    return ""


def pick_text_content(raw: dict[str, Any]) -> str:
    choices = raw.get("choices") if isinstance(raw.get("choices"), list) else []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        content = _text_from_value(message.get("content"))
        if content:
            return content
        delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
        content = _text_from_value(delta.get("content"))
        if content:
            return content

    content = _text_from_value(raw.get("output_text"))
    if content:
        return content

    output = raw.get("output") if isinstance(raw.get("output"), list) else []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = _text_from_value(item.get("content"))
        if content:
            return content

    return ""


def upstream_error(payload: Any, fallback: str, status_code: int = 500) -> HTTPException:
    return HTTPException(
        status_code=status_code or 500,
        detail={
            "message": pick_error_message(payload, fallback),
            "raw": payload,
        },
    )


def parse_model_ids(raw: dict[str, Any]) -> list[str]:
    data = raw.get("data") if isinstance(raw.get("data"), list) else []
    return [item["id"] for item in data if isinstance(item, dict) and isinstance(item.get("id"), str)]


def resolve_test_path(capability: str, adapter: str | None = None) -> str:
    if capability == "text":
        return "/v1/chat/completions"
    if capability == "image":
        return "/v1/images/generations"
    if adapter == "video-seedance":
        return "/v1/video/generations"
    return "/v1/video/create"


def build_test_body(capability: str, model: str, adapter: str | None = None) -> dict[str, Any]:
    if capability == "text":
        return {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 8,
            "stream": False,
        }

    if capability == "image":
        return {
            "model": model,
            "prompt": "simple ping test image, plain geometric dot",
            "n": 1,
            "size": "1024x1024",
            "response_format": "url",
        }

    if adapter == "video-seedance":
        return {
            "model": model,
            "content": [{"type": "text", "text": "ping test, one second static shot"}],
            "metadata": {
                "duration": 1,
                "resolution": "540p",
                "ratio": "16:9",
                "generate_audio": False,
            },
        }

    return {
        "model": model,
        "prompt": "ping test, one second static shot",
        "aspect_ratio": "16:9",
        "duration": 1,
        "resolution": "540p",
        "audio": False,
    }


def resolve_video_create_path(adapter: str) -> str:
    return "/v1/video/generations" if adapter == "video-seedance" else "/v1/video/create"


def resolve_video_query_path(adapter: str, task_id: str) -> str:
    if adapter == "video-seedance":
        return f"/v1/video/generations/{quote(task_id)}"
    return f"/v1/video/query?id={quote(task_id)}"


def normalize_video_status(value: str) -> str:
    lower = value.lower()
    if "success" in lower or "complete" in lower or "succeed" in lower:
        return "completed"
    if "fail" in lower or "error" in lower or "cancel" in lower:
        return "failed"
    if "processing" in lower or "progress" in lower or "pending" in lower or "queue" in lower:
        return "processing"
    return value


def pick_task_id(raw: dict[str, Any]) -> str:
    if isinstance(raw.get("task_id"), str):
        return raw["task_id"]
    if isinstance(raw.get("id"), str):
        return raw["id"]
    return ""


def pick_video_query_payload(raw: dict[str, Any], task_id: str) -> dict[str, Any]:
    seedance_data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    nested_seedance_data = (
        seedance_data.get("data") if isinstance(seedance_data.get("data"), dict) else {}
    )
    seedance_content = (
        nested_seedance_data.get("content")
        if isinstance(nested_seedance_data.get("content"), dict)
        else {}
    )

    status_source = (
        raw.get("status")
        if isinstance(raw.get("status"), str)
        else seedance_data.get("status")
        if isinstance(seedance_data.get("status"), str)
        else nested_seedance_data.get("status")
        if isinstance(nested_seedance_data.get("status"), str)
        else "processing"
    )
    video_url = raw.get("video_url") if isinstance(raw.get("video_url"), str) else seedance_content.get("video_url")
    thumbnail_url = raw.get("thumbnail_url") if isinstance(raw.get("thumbnail_url"), str) else None
    progress = raw.get("progress")
    if progress is None:
        progress = seedance_data.get("progress")

    return {
        "taskId": raw.get("id") if isinstance(raw.get("id"), str) else seedance_data.get("task_id") or task_id,
        "status": normalize_video_status(str(status_source)),
        "progress": progress if isinstance(progress, (str, int, float)) else None,
        "videoUrl": video_url if isinstance(video_url, str) else None,
        "thumbnailUrl": thumbnail_url,
        "raw": raw,
    }


async def forward_json(
    method: str,
    url: str,
    api_key: str,
    body: dict[str, Any] | None = None,
) -> tuple[httpx.Response, dict[str, Any] | str]:
    async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
        response = await client.request(
            method,
            url,
            headers={
                **auth_headers(api_key),
                **({"Content-Type": "application/json"} if body is not None else {}),
            },
            json=body,
        )
    return response, await parse_upstream(response)
