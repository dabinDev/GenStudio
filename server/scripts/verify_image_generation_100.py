from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_prompt_library import DEFAULT_SOURCE_PATH, parse_yuque_index_source  # noqa: E402

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
MODEL_PROVIDER_URL = "https://token.cylonai.cn/"
DEFAULT_MAX_PROMPT_CHARS = 1800
DEFAULT_POLL_ATTEMPTS = 120
DEFAULT_POLL_INTERVAL_SECONDS = 2.0
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120.0


def write_json_stdout(payload: dict[str, Any], *, stream: Any = sys.stdout) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        try:
            buffer.write((text + "\n").encode("utf-8"))
        except BrokenPipeError:
            pass
        return
    try:
        stream.write(text + "\n")
    except BrokenPipeError:
        pass


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_http_timeout(seconds: float) -> httpx.Timeout:
    request_seconds = max(1.0, float(seconds or DEFAULT_REQUEST_TIMEOUT_SECONDS))
    edge_seconds = min(30.0, request_seconds)
    return httpx.Timeout(
        connect=edge_seconds,
        read=request_seconds,
        write=request_seconds,
        pool=edge_seconds,
    )


def load_existing_results(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    results = payload.get("results") if isinstance(payload, dict) else None
    return [item for item in results if isinstance(item, dict)] if isinstance(results, list) else []


def result_is_complete(result: dict[str, Any]) -> bool:
    try:
        generated = int(result.get("generated") or 0)
    except (TypeError, ValueError):
        return False
    status = str(result.get("status") or "").lower()
    return generated > 0 and status not in {"error", "failed"}


def format_exception_message(exc: Exception) -> str:
    message = str(exc).strip()
    return message or exc.__class__.__name__


def summarize_http_error(exc: Exception) -> dict[str, Any]:
    if not isinstance(exc, httpx.HTTPStatusError):
        return {}
    response = exc.response
    detail: Any
    try:
        detail = response.json()
    except ValueError:
        detail = response.text[:1000]
    return {
        "responseStatus": response.status_code,
        "responseDetail": detail,
    }


def summarize_results(plan: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "requestedImages": sum(item["count"] for item in plan),
        "generatedImages": sum(int(item.get("generated") or 0) for item in results),
        "results": sorted(results, key=lambda item: int(item.get("index") or 0)),
    }


def clean_generation_prompt(text: Any, *, max_chars: int = DEFAULT_MAX_PROMPT_CHARS) -> str:
    clean = str(text or "").strip()
    for marker in ('" }, {   "id":', '" }, { "id":', '"},{ "id":', '"},{"id":'):
        marker_index = clean.find(marker)
        if marker_index > 0:
            clean = clean[:marker_index]
            break
    clean = clean.strip()
    if len(clean) > max_chars:
        clean = clean[:max_chars].rstrip()
    return clean


def build_generation_plan(
    prompts: list[dict[str, Any]],
    *,
    target_images: int = 100,
    max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS,
    single_image_only: bool = False,
    enable_4k_every: int = 10,
) -> list[dict[str, Any]]:
    if not prompts:
        raise ValueError("prompt library is empty")
    size_cycle = ["1024x1024", "1536x1024", "1024x1536", ""]
    ratio_cycle = ["", "", "", "1:1", "16:9", "9:16", "4:3", "3:4"]
    count_cycle = [1, 2, 1, 4, 1, 2, 1, 1]
    plan: list[dict[str, Any]] = []
    produced = 0
    index = 0
    while produced < target_images:
        prompt = prompts[index % len(prompts)]
        remaining = target_images - produced
        count = 1 if single_image_only else min(count_cycle[index % len(count_cycle)], remaining)
        size = size_cycle[index % len(size_cycle)]
        ratio = ratio_cycle[index % len(ratio_cycle)]
        enable_4k = enable_4k_every > 0 and index % enable_4k_every == 0
        plan.append(
            {
                "index": len(plan) + 1,
                "templateId": str(prompt.get("id") or prompt.get("externalId") or index),
                "title": str(prompt.get("title") or "")[:80],
                "prompt": clean_generation_prompt(
                    prompt.get("promptText") or prompt.get("prompt_text") or "",
                    max_chars=max_prompt_chars,
                ),
                "count": count,
                "size": size,
                "ratio": ratio,
                "quality": "auto",
                "enable4k": enable_4k,
            }
        )
        produced += count
        index += 1
    return plan


def image_request_body(item: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "prompt": item["prompt"],
        "n": item["count"],
        "quality": item.get("quality") or "auto",
    }
    if item.get("enable4k"):
        if item.get("ratio"):
            body["size"] = item["ratio"]
        elif item.get("size"):
            body["size"] = item["size"]
        else:
            body["size"] = "1:1"
    elif item.get("size"):
        body["size"] = item["size"]
    elif item.get("ratio"):
        body["size"] = item["ratio"]
    return body


async def api_request(client: httpx.AsyncClient, method: str, path: str, *, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
    response = await client.request(method, path, json=json_body)
    response.raise_for_status()
    return response.json()


def response_conversation_id(payload: dict[str, Any]) -> str:
    conversation = payload.get("conversation")
    if isinstance(conversation, dict):
        return str(conversation.get("id") or "")
    return ""


async def wait_for_image_result(
    client: httpx.AsyncClient,
    image_sub_model_id: str,
    response: dict[str, Any],
    *,
    direct_config: dict[str, Any] | None = None,
    poll_attempts: int = DEFAULT_POLL_ATTEMPTS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> tuple[dict[str, Any], int]:
    task_id = str(response.get("taskId") or "")
    if response.get("images") or not task_id:
        return response, 0
    conversation_id = response_conversation_id(response)
    latest = response
    for attempt in range(1, max(1, poll_attempts) + 1):
        if poll_interval_seconds > 0:
            await asyncio.sleep(poll_interval_seconds)
        query_body = {"taskId": task_id, "conversationId": conversation_id}
        if direct_config is not None:
            query_body["config"] = direct_config
            query_body["adapter"] = "image-openai"
        else:
            query_body["subModelId"] = image_sub_model_id
        latest = await api_request(client, "POST", "/api/proxy/image/query", json_body=query_body)
        status = str(latest.get("status") or "").lower()
        if latest.get("images") or status in {"completed", "failed", "error", "cancelled", "canceled"}:
            return latest, attempt
    return latest, max(1, poll_attempts)


async def ensure_csrf(client: httpx.AsyncClient) -> str:
    payload = await api_request(client, "GET", "/api/auth/csrf")
    token = str(payload["csrfToken"])
    client.headers.update({"X-CSRF-Token": token})
    return token


async def configure_models(client: httpx.AsyncClient, provider_api_key: str) -> tuple[str, str]:
    await api_request(
        client,
        "POST",
        "/api/auth/dev-login",
        json_body={
            "externalUserId": "image-verifier",
            "email": "image-verifier@example.com",
            "nickname": "image-verifier",
        },
    )
    await ensure_csrf(client)
    existing = await api_request(client, "GET", "/api/models")
    models = existing.get("models", [])
    text = next((item for item in models if item.get("primaryModelName") == "gpt-5.5" and item.get("capability") == "text"), None)
    image = next((item for item in models if item.get("primaryModelName") == "gpt-image-2" and item.get("capability") == "image"), None)
    if not text:
        text = (await api_request(
            client,
            "POST",
            "/api/models",
            json_body={
                "name": "Verifier GPT 5.5",
                "vendor": "CylonAI",
                "capability": "text",
                "adapter": "text-chat",
                "description": "Local verification chat model",
                "baseUrl": MODEL_PROVIDER_URL,
                "apiKey": provider_api_key,
                "primaryModelName": "gpt-5.5",
                "availableModelNames": ["gpt-5.5"],
                "isPublic": False,
            },
        ))["model"]
    if not image:
        image = (await api_request(
            client,
            "POST",
            "/api/models",
            json_body={
                "name": "Verifier GPT Image 2",
                "vendor": "CylonAI",
                "capability": "image",
                "adapter": "image-openai",
                "description": "Local verification image model",
                "baseUrl": MODEL_PROVIDER_URL,
                "apiKey": provider_api_key,
                "primaryModelName": "gpt-image-2",
                "availableModelNames": ["gpt-image-2"],
                "isPublic": False,
            },
        ))["model"]
    return str(text["subModels"][0]["id"]), str(image["subModels"][0]["id"])


async def run_plan(
    client: httpx.AsyncClient,
    image_sub_model_id: str,
    plan: list[dict[str, Any]],
    *,
    poll_attempts: int = DEFAULT_POLL_ATTEMPTS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    output_path: Path | None = None,
    resume: bool = False,
    direct_config: dict[str, Any] | None = None,
    max_attempts: int = 0,
    max_seconds: float = 0,
) -> dict[str, Any]:
    existing_results = load_existing_results(output_path) if resume and output_path else []
    results_by_index: dict[int, dict[str, Any]] = {}
    for result in existing_results:
        try:
            result_index = int(result.get("index") or 0)
        except (TypeError, ValueError):
            continue
        if result_index > 0 and result_is_complete(result):
            results_by_index[result_index] = result
    attempted = 0
    run_started = time.perf_counter()
    for item in plan:
        if int(item["index"]) in results_by_index:
            continue
        if max_attempts > 0 and attempted >= max_attempts:
            break
        if max_seconds > 0 and attempted > 0 and time.perf_counter() - run_started >= max_seconds:
            break
        started = time.perf_counter()
        payload = {
            "requestBody": image_request_body(item),
            "enable4k": bool(item.get("enable4k")),
        }
        if direct_config is not None:
            payload.update({"config": direct_config, "adapter": "image-openai", "model": "gpt-image-2"})
        else:
            payload["subModelId"] = image_sub_model_id
        try:
            response = await api_request(client, "POST", "/api/proxy/image", json_body=payload)
            initial_task_id = response.get("taskId") or ""
            response, poll_count = await wait_for_image_result(
                client,
                image_sub_model_id,
                response,
                direct_config=direct_config,
                poll_attempts=poll_attempts,
                poll_interval_seconds=poll_interval_seconds,
            )
            image_count = len(response.get("images") or [])
            results_by_index[int(item["index"])] = {
                "index": item["index"],
                "templateId": item["templateId"],
                "requested": item["count"],
                "generated": image_count,
                "status": response.get("status") or "success",
                "taskId": response.get("taskId") or initial_task_id,
                "polls": poll_count,
                "durationMs": round((time.perf_counter() - started) * 1000),
            }
        except Exception as exc:
            results_by_index[int(item["index"])] = {
                "index": item["index"],
                "templateId": item["templateId"],
                "requested": item["count"],
                "generated": 0,
                "status": "error",
                "errorType": exc.__class__.__name__,
                "error": format_exception_message(exc)[:500],
                **summarize_http_error(exc),
                "durationMs": round((time.perf_counter() - started) * 1000),
            }
        attempted += 1
        if output_path:
            write_json_file(output_path, summarize_results(plan, list(results_by_index.values())))
    return summarize_results(plan, list(results_by_index.values()))


def load_prompt_entries(path: Path) -> list[dict[str, Any]]:
    index = parse_yuque_index_source(path.read_text(encoding="utf-8"))
    prompts = index.get("prompts")
    if not isinstance(prompts, list):
        raise ValueError("prompt index does not contain prompts")
    return [item for item in prompts if isinstance(item, dict) and str(item.get("promptText") or "").strip()]


async def main_async() -> int:
    parser = argparse.ArgumentParser(description="Verify 100 GenStudio image generations against a configured provider.")
    parser.add_argument("--server", default=os.getenv("GENSTUDIO_VERIFY_SERVER", DEFAULT_BASE_URL))
    parser.add_argument("--prompt-path", default=os.getenv("GENSTUDIO_YUQUE_PROMPT_PATH", str(DEFAULT_SOURCE_PATH)))
    parser.add_argument("--target-images", type=int, default=int(os.getenv("GENSTUDIO_VERIFY_IMAGE_COUNT", "100")))
    parser.add_argument("--max-prompt-chars", type=int, default=int(os.getenv("GENSTUDIO_VERIFY_MAX_PROMPT_CHARS", str(DEFAULT_MAX_PROMPT_CHARS))))
    parser.add_argument("--single-image-only", action="store_true")
    parser.add_argument("--enable-4k-every", type=int, default=int(os.getenv("GENSTUDIO_VERIFY_ENABLE_4K_EVERY", "10")))
    parser.add_argument("--direct-config", action="store_true")
    parser.add_argument("--poll-attempts", type=int, default=int(os.getenv("GENSTUDIO_VERIFY_POLL_ATTEMPTS", str(DEFAULT_POLL_ATTEMPTS))))
    parser.add_argument("--poll-interval-seconds", type=float, default=float(os.getenv("GENSTUDIO_VERIFY_POLL_INTERVAL_SECONDS", str(DEFAULT_POLL_INTERVAL_SECONDS))))
    parser.add_argument("--request-timeout-seconds", type=float, default=float(os.getenv("GENSTUDIO_VERIFY_REQUEST_TIMEOUT_SECONDS", str(DEFAULT_REQUEST_TIMEOUT_SECONDS))))
    parser.add_argument("--max-attempts", type=int, default=int(os.getenv("GENSTUDIO_VERIFY_MAX_ATTEMPTS", "0")))
    parser.add_argument("--max-seconds", type=float, default=float(os.getenv("GENSTUDIO_VERIFY_MAX_SECONDS", "0")))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", default=os.getenv("GENSTUDIO_VERIFY_OUTPUT", "image-generation-verify-results.json"))
    args = parser.parse_args()

    provider_api_key = os.getenv("GENSTUDIO_TEST_API_KEY", "").strip()
    prompts = load_prompt_entries(Path(args.prompt_path))
    plan = build_generation_plan(
        prompts,
        target_images=args.target_images,
        max_prompt_chars=args.max_prompt_chars,
        single_image_only=args.single_image_only,
        enable_4k_every=args.enable_4k_every,
    )
    if args.dry_run:
        payload = {"requestedImages": sum(item["count"] for item in plan), "requests": len(plan), "plan": plan}
        write_json_file(Path(args.output), payload)
        write_json_stdout({**payload, "plan": plan[:12], "output": args.output})
        return 0
    if not provider_api_key:
        raise RuntimeError("GENSTUDIO_TEST_API_KEY is required for real generation verification.")

    direct_config = {"baseUrl": MODEL_PROVIDER_URL, "apiKey": provider_api_key} if args.direct_config else None
    async with httpx.AsyncClient(base_url=args.server.rstrip("/"), timeout=build_http_timeout(args.request_timeout_seconds)) as client:
        if args.direct_config:
            image_sub_model_id = ""
        else:
            _text_sub_model_id, image_sub_model_id = await configure_models(client, provider_api_key)
        summary = await run_plan(
            client,
            image_sub_model_id,
            plan,
            poll_attempts=args.poll_attempts,
            poll_interval_seconds=args.poll_interval_seconds,
            output_path=Path(args.output),
            resume=args.resume,
            direct_config=direct_config,
            max_attempts=args.max_attempts,
            max_seconds=args.max_seconds,
        )
    output = Path(args.output)
    write_json_file(output, summary)
    write_json_stdout({k: v for k, v in summary.items() if k != "results"})
    return 0 if summary["generatedImages"] >= args.target_images else 1


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
