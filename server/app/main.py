from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.proxy_utils import (
    build_test_body,
    forward_json,
    parse_model_ids,
    pick_task_id,
    pick_video_query_payload,
    resolve_test_path,
    resolve_url,
    resolve_video_create_path,
    resolve_video_query_path,
    upstream_error,
    validate_config,
)

app = FastAPI(title="GenStudio Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:3001",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/proxy/models")
async def proxy_models(payload: dict[str, Any]) -> dict[str, Any]:
    base_url, api_key = validate_config(payload.get("config"))
    target_url = resolve_url(base_url, "/v1/models")
    started_at = time.perf_counter()
    response, raw = await forward_json("GET", target_url, api_key)
    duration_ms = round((time.perf_counter() - started_at) * 1000)

    if not response.is_success or not isinstance(raw, dict):
        raise upstream_error(raw, "获取模型列表失败。", response.status_code)

    return {
        "models": parse_model_ids(raw),
        "durationMs": duration_ms,
        "raw": raw,
    }


@app.post("/api/proxy/test")
async def proxy_test(payload: dict[str, Any]) -> dict[str, Any]:
    base_url, api_key = validate_config(payload.get("config"))
    capability = payload.get("capability")
    model = str(payload.get("model", "")).strip()
    adapter = payload.get("adapter")

    if not capability:
        raise HTTPException(status_code=400, detail={"message": "缺少模型能力类型。"})
    if not model:
        raise HTTPException(status_code=400, detail={"message": "缺少模型标识。"})

    target_url = resolve_url(base_url, resolve_test_path(str(capability), str(adapter) if adapter else None))
    body = build_test_body(str(capability), model, str(adapter) if adapter else None)
    started_at = time.perf_counter()
    response, raw = await forward_json("POST", target_url, api_key, body)
    duration_ms = round((time.perf_counter() - started_at) * 1000)
    request = {"url": target_url, "body": body}

    if not response.is_success or not isinstance(raw, dict):
        raise HTTPException(
            status_code=response.status_code or 500,
            detail={
                "message": "测试请求失败。",
                "request": request,
                "durationMs": duration_ms,
                "raw": raw,
            },
        )

    return {
        "ok": True,
        "status": response.status_code,
        "request": request,
        "durationMs": duration_ms,
        "raw": raw,
    }


@app.post("/api/proxy/text")
async def proxy_text(payload: dict[str, Any]) -> dict[str, Any]:
    base_url, api_key = validate_config(payload.get("config"))
    model = str(payload.get("model", "")).strip()
    if not model:
        raise HTTPException(status_code=400, detail={"message": "缺少模型标识。"})

    target_url = resolve_url(base_url, "/v1/chat/completions")
    body = {"model": model, **(payload.get("requestBody") or {})}
    response, raw = await forward_json("POST", target_url, api_key, body)

    if not response.is_success or not isinstance(raw, dict):
        raise upstream_error(raw, "文案请求失败。", response.status_code)

    choices = raw.get("choices") if isinstance(raw.get("choices"), list) else []
    message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
    content = message.get("content") if isinstance(message, dict) and isinstance(message.get("content"), str) else ""

    return {
        "content": content,
        "usage": raw.get("usage"),
        "raw": raw,
    }


@app.post("/api/proxy/image")
async def proxy_image(payload: dict[str, Any]) -> dict[str, Any]:
    base_url, api_key = validate_config(payload.get("config"))
    model = str(payload.get("model", "")).strip()
    if not model:
        raise HTTPException(status_code=400, detail={"message": "缺少模型标识。"})

    target_url = resolve_url(base_url, "/v1/images/generations")
    body = {"model": model, **(payload.get("requestBody") or {})}
    response, raw = await forward_json("POST", target_url, api_key, body)

    if not response.is_success or not isinstance(raw, dict):
        raise upstream_error(raw, "图片请求失败。", response.status_code)

    images = []
    for item in raw.get("data", []) if isinstance(raw.get("data"), list) else []:
        if not isinstance(item, dict):
            continue
        src = item.get("url") if isinstance(item.get("url"), str) else ""
        if not src and isinstance(item.get("b64_json"), str):
            src = f"data:image/png;base64,{item['b64_json']}"
        if src:
            images.append(
                {
                    "src": src,
                    "revisedPrompt": item.get("revised_prompt")
                    if isinstance(item.get("revised_prompt"), str)
                    else None,
                }
            )

    return {"images": images, "raw": raw}


@app.post("/api/proxy/video/create")
async def proxy_video_create(payload: dict[str, Any]) -> dict[str, Any]:
    base_url, api_key = validate_config(payload.get("config"))
    adapter = str(payload.get("adapter", "")).strip()
    if not adapter:
        raise HTTPException(status_code=400, detail={"message": "缺少视频适配器。"})

    target_url = resolve_url(base_url, resolve_video_create_path(adapter))
    response, raw = await forward_json("POST", target_url, api_key, payload.get("requestBody") or {})

    if not response.is_success or not isinstance(raw, dict):
        raise upstream_error(raw, "视频任务提交失败。", response.status_code)

    return {
        "taskId": pick_task_id(raw),
        "status": raw.get("status") if isinstance(raw.get("status"), str) else raw.get("code") if isinstance(raw.get("code"), str) else "submitted",
        "raw": raw,
    }


@app.post("/api/proxy/video/query")
async def proxy_video_query(payload: dict[str, Any]) -> dict[str, Any]:
    base_url, api_key = validate_config(payload.get("config"))
    adapter = str(payload.get("adapter", "")).strip()
    task_id = str(payload.get("taskId", "")).strip()
    if not adapter:
        raise HTTPException(status_code=400, detail={"message": "缺少视频适配器。"})
    if not task_id:
        raise HTTPException(status_code=400, detail={"message": "缺少任务 ID。"})

    target_url = resolve_url(base_url, resolve_video_query_path(adapter, task_id))
    response, raw = await forward_json("GET", target_url, api_key)

    if not response.is_success or not isinstance(raw, dict):
        raise upstream_error(raw, "任务查询失败。", response.status_code)

    return pick_video_query_payload(raw, task_id)


@app.post("/api/proxy/upload/presign")
async def proxy_upload_presign(payload: dict[str, Any]) -> dict[str, Any]:
    base_url, api_key = validate_config(payload.get("config"))
    target_url = resolve_url(base_url, "/api/upload/presign")
    body = {
        "file_name": payload.get("fileName") or "upload.bin",
        "content_type": payload.get("contentType") or "application/octet-stream",
        "expires_in": 900,
    }
    response, raw = await forward_json("POST", target_url, api_key, body)

    if not response.is_success or not isinstance(raw, dict):
        raise upstream_error(raw, "获取上传地址失败。", response.status_code)

    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    if not raw.get("success") or not data:
        raise upstream_error(raw, "上传服务未正确返回预签名地址。", 500)

    return {
        "uploadUrl": data.get("upload_url") if isinstance(data.get("upload_url"), str) else "",
        "method": data.get("method") if isinstance(data.get("method"), str) else "PUT",
        "publicUrl": data.get("public_url") if isinstance(data.get("public_url"), str) else "",
        "objectKey": data.get("object_key") if isinstance(data.get("object_key"), str) else "",
        "contentType": data.get("content_type") if isinstance(data.get("content_type"), str) else body["content_type"],
    }
