# R2 Asset Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist generated images and thumbnails to Cloudflare R2, retain local copies for 24 hours, dynamically switch delivery URLs, and expose safe synchronization operations in the admin console.

**Architecture:** Extend `generated_assets` into a storage state machine. A testable service claims rows atomically, materializes remote images when necessary, generates WebP thumbnails, uploads and verifies both objects, and removes local files only after the TTL. Conversation serialization resolves local versus R2 URLs at read time.

**Tech Stack:** FastAPI, SQLAlchemy, MySQL/SQLite, boto3 S3 client, Pillow, httpx, Pytest, Vue 3 admin, Vitest

---

### Task 1: Storage schema and migration

**Files:**
- Create: `server/migrations/009_asset_storage_lifecycle.sql`
- Modify: `server/app/db_models.py`
- Modify: `server/app/database.py`
- Modify: `server/tests/test_migrations.py`
- Create: `server/tests/test_asset_storage.py`

- [ ] **Step 1: Write failing model and migration tests**

Assert a new `GeneratedAsset` has `storage_status == "local_pending"`, `local_expires_at` is nullable during legacy creation, and migration `009` contains all storage columns plus indexes on `storage_status`, `local_expires_at`, and `storage_updated_at`. Extend the startup schema test to inspect the same columns after `init_db()`.

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_migrations.py tests/test_asset_storage.py -q`

Expected: FAIL because storage fields and migration 009 are absent.

- [ ] **Step 3: Add exact schema fields**

Add columns to `GeneratedAsset`:

```python
storage_status: Mapped[str] = mapped_column(String(32), default="local_pending", index=True)
local_path: Mapped[str] = mapped_column(Text, default="")
local_thumbnail_path: Mapped[str] = mapped_column(Text, default="")
r2_object_key: Mapped[str] = mapped_column(Text, default="")
r2_thumbnail_key: Mapped[str] = mapped_column(Text, default="")
r2_url: Mapped[str] = mapped_column(Text, default="")
r2_thumbnail_url: Mapped[str] = mapped_column(Text, default="")
content_type: Mapped[str] = mapped_column(String(128), default="")
size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
sha256: Mapped[str] = mapped_column(String(64), default="")
local_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
sync_attempts: Mapped[int] = mapped_column(Integer, default=0)
last_sync_error: Mapped[str] = mapped_column(Text, default="")
synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
storage_updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
```

Migration defaults preserve existing rows. Startup patching adds every column idempotently for development.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/test_migrations.py tests/test_asset_storage.py -q`

Expected: focused tests pass.

- [ ] **Step 5: Commit**

```powershell
git add server/migrations/009_asset_storage_lifecycle.sql server/app/db_models.py server/app/database.py server/tests/test_migrations.py server/tests/test_asset_storage.py
git commit -m "feat: add asset storage lifecycle schema"
```

### Task 2: Thumbnail generation and safe local paths

**Files:**
- Modify: `server/requirements.txt`
- Create: `server/app/asset_images.py`
- Create: `server/tests/test_asset_images.py`

- [ ] **Step 1: Install the test dependency without editing production code**

Run: `python -m pip install Pillow`

Expected: Pillow imports successfully.

- [ ] **Step 2: Write failing thumbnail tests**

Create a 1600 x 900 JPEG in a temporary directory, call `create_thumbnail`, and assert output is WebP, maximum side is 640, aspect ratio is preserved, and a 320 x 200 input is not enlarged. Assert `resolve_managed_path(root, "../secret")` raises `ValueError`.

- [ ] **Step 3: Run and verify RED**

Run: `python -m pytest tests/test_asset_images.py -q`

Expected: FAIL because `asset_images.py` does not exist.

- [ ] **Step 4: Implement image helpers**

Use `PIL.Image.open`, `ImageOps.exif_transpose`, `thumbnail((640, 640), Image.Resampling.LANCZOS)`, and `save(format="WEBP", quality=78, method=6)`. Reject decompression-bomb warnings as errors, validate supported image formats, and use `Path.resolve().is_relative_to(root.resolve())` for managed paths. Add `Pillow==11.3.0` to `requirements.txt`.

- [ ] **Step 5: Run and verify GREEN**

Run: `python -m pytest tests/test_asset_images.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add server/requirements.txt server/app/asset_images.py server/tests/test_asset_images.py
git commit -m "feat: generate asset thumbnails"
```

### Task 3: Injectable R2 object client

**Files:**
- Modify: `server/requirements.txt`
- Modify: `server/app/storage.py`
- Create: `server/tests/test_storage.py`

- [ ] **Step 1: Install boto3 as environment setup**

Run: `python -m pip install boto3`

Expected: `python -c "import boto3"` exits 0.

- [ ] **Step 2: Write failing storage-client tests**

Use a fake boto client to assert `put_file` sends bucket/key/content type, `head` validates nonzero content length, `delete` targets the exact key, and `public_url` percent-encodes path components without encoding slashes. Assert no secret appears in `repr(client)`.

- [ ] **Step 3: Run and verify RED**

Run: `python -m pytest tests/test_storage.py -q`

Expected: FAIL because `ObjectStorageClient` does not exist.

- [ ] **Step 4: Implement the client**

Add `ObjectStorageClient(settings, client=None)` using `boto3.client("s3", endpoint_url=..., region_name=..., aws_access_key_id=..., aws_secret_access_key=..., config=Config(signature_version="s3v4", s3={"addressing_style": "path"}))`. Provide `put_file`, `head`, `delete`, `download_file`, and `public_url`. Keep existing presign behavior compatible and add `boto3==1.39.0` to `requirements.txt`.

- [ ] **Step 5: Run and verify GREEN**

Run: `python -m pytest tests/test_storage.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add server/requirements.txt server/app/storage.py server/tests/test_storage.py
git commit -m "feat: add cloudflare r2 client"
```

### Task 4: Asset registration and safe remote materialization

**Files:**
- Create: `server/app/asset_fetch.py`
- Create: `server/app/asset_storage.py`
- Create: `server/tests/test_asset_fetch.py`
- Modify: `server/tests/test_asset_storage.py`
- Modify: `server/app/conversation_service.py`

- [ ] **Step 1: Write failing registration and SSRF tests**

Assert loopback, RFC1918, link-local, IPv6 loopback, non-HTTP schemes, oversized responses, excessive redirects, and non-image MIME are rejected. Assert registering `/api/assets/generated/<uuid>.png` records a managed local path, thumbnail path, SHA-256, size, `local_pending`, and expiry at `created_at + 24h`. Assert an R2 public URL is recognized as already synced. Add backfill tests proving legacy local URLs become `local_pending`, known object-storage URLs become `r2_synced`, and unknown remote URLs become retryable materialization rows without changing the original URL.

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_asset_fetch.py tests/test_asset_storage.py -q`

Expected: FAIL because fetch and registration services do not exist.

- [ ] **Step 3: Implement materialization and registration**

`asset_fetch.py` resolves DNS before every request, rejects private/reserved targets, allows at most 3 redirects, streams at most 25 MiB, and uses 5-second connect/20-second read timeouts. `asset_storage.py` provides `register_asset_storage(asset, generated_root, uploaded_root, settings, now)`, `backfill_asset_storage(db, roots, settings, now, batch_size)`, and `materialize_remote_asset(asset, client, root)`. Hook registration into `add_asset` after `db.flush()` and call bounded idempotent backfill from startup before the worker begins; never mutate an existing external URL until R2 synchronization succeeds.

- [ ] **Step 4: Run and verify GREEN**

Run: `python -m pytest tests/test_asset_fetch.py tests/test_asset_storage.py tests/test_conversations.py -q`

Expected: all focused tests pass.

- [ ] **Step 5: Commit**

```powershell
git add server/app/asset_fetch.py server/app/asset_storage.py server/app/conversation_service.py server/tests/test_asset_fetch.py server/tests/test_asset_storage.py
git commit -m "feat: register generated image storage"
```

### Task 5: R2 synchronization state machine

**Files:**
- Create: `server/app/asset_sync.py`
- Create: `server/tests/test_asset_sync.py`
- Modify: `server/app/main.py`

- [ ] **Step 1: Write failing state-machine tests**

Use a temp SQLite database and fake object store to prove: one worker atomically claims a row; a second claim fails; stale `syncing` rows recover after 15 minutes; retries are due after 1/5/30 minutes; upload order is original then thumbnail then HEAD both; failure keeps local files; success keeps local files before 24 hours; success deletes both local files after 24 hours; cleanup never deletes a unique unsynced copy.

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_asset_sync.py -q`

Expected: FAIL because `AssetSyncService` does not exist.

- [ ] **Step 3: Implement the state machine**

Define `AssetSyncConfig(interval_seconds=60, local_ttl=timedelta(hours=24), syncing_timeout=timedelta(minutes=15), batch_size=8)`. Implement `sync_once`, `_claim`, `_sync_claimed`, `_mark_failed`, and `_remove_expired_local_copy`. Object keys use UTC date and asset ID. Start one cancellable loop in FastAPI lifespan and execute blocking work with `asyncio.to_thread`; cancellation must await the task.

- [ ] **Step 4: Run and verify GREEN**

Run: `python -m pytest tests/test_asset_sync.py -q`

Expected: all state-machine tests pass.

- [ ] **Step 5: Commit**

```powershell
git add server/app/asset_sync.py server/tests/test_asset_sync.py server/app/main.py
git commit -m "feat: sync generated assets to r2"
```

### Task 6: Dynamic local/R2 delivery and thumbnail routes

**Files:**
- Modify: `server/app/asset_storage.py`
- Modify: `server/app/conversation_service.py`
- Modify: `server/app/main.py`
- Modify: `server/tests/test_asset_storage.py`
- Modify: `server/tests/test_conversations.py`

- [ ] **Step 1: Write failing 24-hour boundary tests**

At `created_at + 23:59:59`, assert serializer returns local original and local thumbnail. At exactly `created_at + 24h` with `r2_synced`, assert it returns `r2_url` and `r2_thumbnail_url`. With `sync_failed`, assert it keeps the available local URL and exposes storage status only in metadata, not secrets.

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_asset_storage.py tests/test_conversations.py -q`

Expected: FAIL because serialization always returns stored `url` and `thumbnail_url`.

- [ ] **Step 3: Implement delivery resolution**

Add `resolve_asset_delivery(asset, now)` returning `{url, thumbnail_url}`. Add authenticated `GET|HEAD /api/assets/{asset_id}/content` and `/thumbnail` routes that authorize owner or admin and resolve only managed local paths. `serialize_asset` calls the resolver at request time; it never persists the resolved local URL back to the row.

- [ ] **Step 4: Run and verify GREEN**

Run: `python -m pytest tests/test_asset_storage.py tests/test_conversations.py -q`

Expected: all focused tests pass.

- [ ] **Step 5: Commit**

```powershell
git add server/app/asset_storage.py server/app/conversation_service.py server/app/main.py server/tests/test_asset_storage.py server/tests/test_conversations.py
git commit -m "feat: resolve cached and r2 asset urls"
```

### Task 7: Reference upload thumbnails and metadata handoff

**Files:**
- Modify: `fronted/src/api.ts`
- Modify: `fronted/src/api.test.ts`
- Modify: `fronted/src/types.ts`
- Modify: `fronted/src/App.vue`
- Modify: `server/app/main.py`
- Modify: `server/tests/test_conversations.py`

- [ ] **Step 1: Write failing browser-thumbnail and persistence tests**

Mock canvas/blob creation and two presign responses. Assert `uploadAsset` uploads original and a maximum-640 WebP thumbnail, returning both stable URLs and object keys. Assert generation payload carries `referenceAssets` metadata outside the provider `requestBody`, and the backend persists `thumbnailUrl`, one-based index, role, and object keys without forwarding internal metadata upstream.

- [ ] **Step 2: Run and verify RED**

Run frontend: `npm test -- api.test.ts`

Run backend: `python -m pytest tests/test_conversations.py -q`

Expected: both fail on missing thumbnail handoff.

- [ ] **Step 3: Implement thumbnail upload and handoff**

Add `createReferenceThumbnail(file, 640, 0.78)` using `createImageBitmap` and canvas, without upscaling. Request a second presign with a `.webp` name, upload it, and include `referenceAssets` in the top-level proxy payload. Backend removes this field before upstream forwarding and passes its validated entries to `add_reference_assets`.

- [ ] **Step 4: Run and verify GREEN**

Run frontend: `npm test -- api.test.ts referenceMentions.test.ts`

Run backend: `python -m pytest tests/test_conversations.py -q`

Expected: focused tests pass.

- [ ] **Step 5: Commit**

```powershell
git add fronted/src/api.ts fronted/src/api.test.ts fronted/src/types.ts fronted/src/App.vue server/app/main.py server/tests/test_conversations.py
git commit -m "feat: upload reference thumbnails to r2"
```

### Task 8: Admin synchronization controls

**Files:**
- Modify: `server/app/asset_sync.py`
- Modify: `server/app/asset_cleanup.py`
- Modify: `server/app/main.py`
- Modify: `server/tests/test_admin_backend.py`
- Modify: `admin/src/types.ts`
- Modify: `admin/src/api/admin.ts`
- Modify: `admin/src/api/admin.test.ts`
- Modify: `admin/src/views/SystemSettingsView.vue`
- Modify: `admin/src/views/adminContent.test.ts`

- [ ] **Step 1: Write failing backend admin tests**

Assert settings expose enabled, interval, batch size, fixed 24-hour TTL, status counts, bytes, last run, and failures. Assert preview is read-only; run claims eligible assets; retry resets failed rows; viewer can inspect but only `maintenance:asset_cleanup` can mutate; every mutation writes an audit log.

- [ ] **Step 2: Run and verify backend RED**

Run: `python -m pytest tests/test_admin_backend.py -k "asset_sync or asset_cleanup" -q`

Expected: FAIL because sync endpoints and summaries do not exist.

- [ ] **Step 3: Implement backend APIs**

Add:

```text
GET  /api/admin/asset-sync/settings
PUT  /api/admin/asset-sync/settings
GET  /api/admin/asset-sync/preview
POST /api/admin/asset-sync/run
POST /api/admin/asset-sync/retry-failed
```

Persist `asset_sync_enabled`, `asset_sync_interval_seconds`, `asset_sync_batch_size`, `asset_sync_last_run`, and `asset_sync_last_auto_run` in system settings. Keep legacy orphan cleanup separate and prevent it from deleting tracked unsynced files.

- [ ] **Step 4: Run backend GREEN**

Run: `python -m pytest tests/test_admin_backend.py -k "asset_sync or asset_cleanup" -q`

Expected: focused backend tests pass.

- [ ] **Step 5: Write failing admin UI tests**

Assert API methods call all five endpoints and `SystemSettingsView` renders status metrics, fixed “24 小时”, preview, immediate sync, retry-failed, last result, and a failure table.

- [ ] **Step 6: Run admin RED**

Run: `npm test -- api/admin.test.ts views/adminContent.test.ts`

Expected: FAIL because sync UI/types are absent.

- [ ] **Step 7: Implement admin UI**

Replace the old cleanup card heading with “图片存储与同步”, retain orphan cleanup as a subordinate section, use status tags and a compact un-nested metrics grid, disable mutating controls without permission, and show server messages through existing notice/error channels.

- [ ] **Step 8: Run admin GREEN**

Run: `npm test -- api/admin.test.ts views/adminContent.test.ts`

Expected: focused admin tests pass.

- [ ] **Step 9: Commit**

```powershell
git add server/app/asset_sync.py server/app/asset_cleanup.py server/app/main.py server/tests/test_admin_backend.py admin/src/types.ts admin/src/api/admin.ts admin/src/api/admin.test.ts admin/src/views/SystemSettingsView.vue admin/src/views/adminContent.test.ts
git commit -m "feat: manage r2 asset synchronization"
```

### Task 9: Lifecycle verification checkpoint

**Files:**
- Modify: `docs/OPERATIONS.md`

- [ ] **Step 1: Document configuration and recovery**

Document object prefix, public base URL, 24-hour cache, worker settings, health status, test-object procedure, manual retry, and rollback. Do not include credentials.

- [ ] **Step 2: Run all backend tests and compilation**

Run from `server/`: `python -m pytest`.

Run from repo root: `python -m compileall server`.

Expected: all tests pass; compile exits 0.

- [ ] **Step 3: Run frontend/admin tests and builds**

Run `npm test` and `npm run build` in both `fronted/` and `admin/`.

Expected: all commands exit 0.

- [ ] **Step 4: Build the production backend image**

Run: `docker build -f server/Dockerfile -t genstudio-api:newui .`

Expected: image build exits 0 and imports Pillow/boto3 in the runtime layer.

- [ ] **Step 5: Commit docs**

```powershell
git add docs/OPERATIONS.md
git commit -m "docs: document r2 asset lifecycle"
```
