# KKYi Catalog Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store KKYi model catalog details, parameters, options, and channel groups in GenStudio, then link user sub-models to that catalog metadata.

**Architecture:** Add normalized global catalog tables with `raw_json` preservation, expose a sync endpoint for KKYi list/detail APIs, and extend user model creation/sync to attach catalog IDs. Existing user-owned `api_keys`, `models`, `sub_models`, conversations, and call logs remain the ownership boundary.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pydantic, MySQL/SQLite tests, Vue TypeScript frontend.

---

### Task 1: Backend Catalog Tables And Serialization

**Files:**
- Modify: `server/app/db_models.py`
- Modify: `server/app/schemas.py`
- Create: `server/app/catalog_service.py`
- Test: `server/tests/test_kkyi_catalog.py`

- [ ] Write a failing test that upserts a KKYi detail payload and verifies `catalog_models`, parameters, options, and channel group rows are persisted.
- [ ] Run `python -m pytest server/tests/test_kkyi_catalog.py::test_upsert_kkyi_catalog_detail_persists_parameters_and_channel_groups -q` and confirm it fails because catalog code is missing.
- [ ] Add SQLAlchemy models:
  - `CatalogModel`
  - `CatalogModelParameter`
  - `CatalogModelParameterOption`
  - `CatalogModelChannelGroup`
- [ ] Add Pydantic output schemas for catalog model metadata.
- [ ] Implement `upsert_catalog_model_detail(db, detail)` and `serialize_catalog_model(model)`.
- [ ] Re-run the focused test and confirm it passes.

### Task 2: Link User Sub-Models To Catalog Entries

**Files:**
- Modify: `server/app/db_models.py`
- Modify: `server/app/schemas.py`
- Modify: `server/app/model_service.py`
- Test: `server/tests/test_kkyi_catalog.py`

- [ ] Write a failing test that creates a user model with `catalogModelId` and expects the created sub-model to return catalog metadata.
- [ ] Run the focused test and confirm it fails because `catalogModelId` is not accepted/serialized.
- [ ] Add nullable `catalog_model_id` to `models` and `sub_models`.
- [ ] Extend `ModelCreate`, `ModelUpdate`, `SubModelOut`, and `ModelOut` with catalog fields.
- [ ] Update `create_model_group`, `update_model_group`, and `upsert_fetched_sub_models` to attach matching catalog rows by `catalogModelId` or `model_name`.
- [ ] Re-run the focused test and confirm it passes.

### Task 3: KKYi Sync API

**Files:**
- Modify: `server/app/config.py`
- Modify: `server/app/main.py`
- Modify: `server/app/catalog_service.py`
- Test: `server/tests/test_kkyi_catalog.py`

- [ ] Write a failing API test using a fake async transport that returns one model list page and one detail payload.
- [ ] Add settings for `KKYI_CATALOG_BASE_URL` and optional `KKYI_CATALOG_BEARER_TOKEN`.
- [ ] Implement `sync_kkyi_catalog(db, bearer_token, model_type)` to fetch list pages and details.
- [ ] Add `GET /api/catalog/models` with optional `capability` filter.
- [ ] Add `POST /api/catalog/kkyi/sync`, requiring auth and CSRF.
- [ ] Re-run the API test and confirm it passes.

### Task 4: Frontend Model Metadata Consumption

**Files:**
- Modify: `fronted/src/types.ts`
- Modify: `fronted/src/api.ts`
- Modify: `fronted/src/App.vue`
- Test: existing frontend test suite

- [ ] Extend frontend types with catalog metadata and parameter definitions.
- [ ] Add API helpers for catalog list and sync.
- [ ] Update settings model creation flow so fetched catalog models can be selected and the selected `catalogModelId` is sent when saving.
- [ ] Display model parameters compactly in the model list and test response area.
- [ ] Run `npm run test` in `fronted`.

### Task 5: Verification And Real Provider Probing

**Files:**
- Modify only if verification reveals a defect.

- [ ] Run backend tests: `python -m pytest server/tests/test_auth_models.py server/tests/test_conversations.py server/tests/test_video_local_references.py server/tests/test_kkyi_catalog.py -q`.
- [ ] Run frontend tests: `npm run test`.
- [ ] Restart backend and frontend.
- [ ] Sync KKYi catalog using the provided bearer token without printing the token.
- [ ] Probe each provided `https://ai-api.kkidc.com` key against `/v1/models`, recording label, masked suffix, count, and capability guesses.
- [ ] Test representative text, image, and video requests with real keys and report successes/failures without exposing full secrets.
