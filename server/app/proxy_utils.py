from __future__ import annotations

import json
import asyncio
from typing import Any
from urllib.parse import quote, urljoin, urlparse, urlunparse

import httpx
from fastapi import HTTPException

from app.config import get_settings


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
    return coerce_json_object(response.text)


def coerce_json_object(payload: Any) -> Any:
    if isinstance(payload, dict):
        return payload
    if not isinstance(payload, str):
        return payload
    try:
        parsed = json.loads(payload)
    except ValueError:
        return payload
    return parsed if isinstance(parsed, dict) else payload


def pick_error_message(payload: Any, fallback: str) -> str:
    if isinstance(payload, str):
        lower_payload = payload.lower()
        if "504 gateway" in lower_payload or "gateway time-out" in lower_payload or "gateway timeout" in lower_payload:
            return "上游服务超时，请稍后重试。"
        if "502 bad gateway" in lower_payload or "bad gateway" in lower_payload:
            return "上游服务暂时不可用，请稍后重试。"
        if "<html" in lower_payload:
            return fallback
    if not isinstance(payload, dict):
        return fallback

    error_value = payload.get("error")
    if isinstance(error_value, str):
        return error_value

    if isinstance(error_value, dict) and (
        error_value.get("type") == "bad_response_body"
        or error_value.get("code") == "bad_response_body"
        or "invalid character '<'" in str(error_value.get("message", "")).lower()
    ):
        return "上游接口返回了非 JSON 内容，请检查模型接口路径或稍后重试。"

    if isinstance(error_value, dict) and (
        error_value.get("message") == "openai_error"
        or error_value.get("type") == "bad_response_status_code"
        or error_value.get("code") == "bad_response_status_code"
    ):
        return "上游模型服务返回异常，请稍后重试或检查模型接口。"

    if isinstance(error_value, dict) and isinstance(error_value.get("message"), str):
        return error_value["message"]

    if isinstance(payload.get("message"), str):
        return payload["message"]

    return fallback


def pick_video_task_error_message(payload: Any, fallback: str) -> str:
    if not isinstance(payload, dict):
        return pick_error_message(payload, fallback)

    containers: list[dict[str, Any]] = []

    def collect(value: Any) -> None:
        if not isinstance(value, dict) or value in containers:
            return
        containers.append(value)
        for key in ("data", "result", "content", "output"):
            collect(value.get(key))

    collect(payload)
    for item in containers:
        error_value = item.get("error")
        if isinstance(error_value, str) and error_value.strip():
            return error_value.strip()
        if isinstance(error_value, dict) and isinstance(error_value.get("message"), str) and error_value["message"].strip():
            return error_value["message"].strip()
        for key in ("error_message", "errorMessage", "fail_reason", "failed_reason", "failure_reason", "reason", "message", "msg"):
            value = item.get(key)
            if not isinstance(value, str):
                continue
            clean = value.strip()
            if clean and clean.lower() not in {"ok", "success", "succeeded"}:
                return clean

    message = pick_error_message(payload, fallback)
    return fallback if message.lower() in {"ok", "success", "succeeded"} else message


def is_non_json_upstream_error(payload: Any) -> bool:
    if isinstance(payload, str):
        lower_payload = payload.lower()
        return "<html" in lower_payload or "invalid character '<'" in lower_payload
    if not isinstance(payload, dict):
        return False
    error_value = payload.get("error")
    if not isinstance(error_value, dict):
        return False
    return (
        error_value.get("type") == "bad_response_body"
        or error_value.get("code") == "bad_response_body"
        or "invalid character '<'" in str(error_value.get("message", "")).lower()
    )


def sanitize_error_raw(payload: Any) -> Any:
    if not isinstance(payload, str):
        return payload
    lower_payload = payload.lower()
    if "<html" in lower_payload or "<body" in lower_payload or "<head" in lower_payload:
        return None
    if len(payload) > 2000:
        return payload[:2000]
    return payload


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
    detail = {"message": pick_error_message(payload, fallback)}
    raw = sanitize_error_raw(payload)
    if raw is not None:
        detail["raw"] = raw
    return HTTPException(
        status_code=status_code or 500,
        detail=detail,
    )


def parse_model_ids(raw: dict[str, Any]) -> list[str]:
    data = raw.get("data") if isinstance(raw.get("data"), list) else []
    return [item["id"] for item in data if isinstance(item, dict) and isinstance(item.get("id"), str)]


def filter_model_ids_for_capability(model_ids: list[str], capability: str | None) -> list[str]:
    if not capability:
        return model_ids
    lower_capability = capability.lower()
    image_tokens = ("image", "img", "gpt-image", "seedream", "sdxl", "flux", "dall-e")
    video_tokens = ("video", "seedance", "veo", "kling", "vidu", "jimeng", "runway", "wan")
    embedding_tokens = ("embedding", "embed", "rerank")

    def has_any(value: str, tokens: tuple[str, ...]) -> bool:
        lower = value.lower()
        return any(token in lower for token in tokens)

    if lower_capability == "image":
        filtered = [model_id for model_id in model_ids if has_any(model_id, image_tokens)]
    elif lower_capability == "video":
        filtered = [model_id for model_id in model_ids if has_any(model_id, video_tokens)]
    elif lower_capability == "text":
        filtered = [
            model_id
            for model_id in model_ids
            if not has_any(model_id, image_tokens) and not has_any(model_id, video_tokens) and not has_any(model_id, embedding_tokens)
        ]
    else:
        filtered = model_ids
    return filtered or model_ids


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


def has_video_task_error(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    message = pick_video_task_error_message(payload, "")
    return bool(message.strip())


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
    status = normalize_video_status(str(status_source))
    if status not in {"completed", "processing"} and has_video_task_error(raw):
        status = "failed"

    return {
        "taskId": raw.get("id") if isinstance(raw.get("id"), str) else seedance_data.get("task_id") or task_id,
        "status": status,
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
    settings = get_settings()
    attempts = max(1, settings.upstream_retry_attempts)
    last_error: httpx.HTTPError | None = None
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, trust_env=False) as client:
        for attempt in range(attempts):
            try:
                response = await client.request(
                    method,
                    url,
                    headers={
                        **auth_headers(api_key),
                        **({"Content-Type": "application/json"} if body is not None else {}),
                    },
                    json=body,
                )
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < attempts - 1:
                    await asyncio.sleep(0.2 * (attempt + 1))
                    continue
                raise
            if response.status_code >= 500 and attempt < attempts - 1:
                await asyncio.sleep(0.2 * (attempt + 1))
                continue
            return response, await parse_upstream(response)
    raise last_error or RuntimeError("Upstream request failed.")


async def forward_multipart(
    url: str,
    api_key: str,
    *,
    data: dict[str, str],
    files: list[tuple[str, tuple[str, bytes, str]]],
) -> tuple[httpx.Response, dict[str, Any] | str]:
    settings = get_settings()
    attempts = max(1, settings.upstream_retry_attempts)
    last_error: httpx.HTTPError | None = None
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, trust_env=False) as client:
        for attempt in range(attempts):
            try:
                response = await client.post(
                    url,
                    headers=auth_headers(api_key),
                    data=data,
                    files=files,
                )
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < attempts - 1:
                    await asyncio.sleep(0.2 * (attempt + 1))
                    continue
                raise
            if response.status_code >= 500 and attempt < attempts - 1:
                await asyncio.sleep(0.2 * (attempt + 1))
                continue
            return response, await parse_upstream(response)
    raise last_error or RuntimeError("Upstream request failed.")
