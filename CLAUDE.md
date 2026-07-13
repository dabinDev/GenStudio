# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

GenStudio (塞隆studio) is an AI creative workbench: users generate text/images/video by proxying
through upstream AI providers. Production: `https://studio.cylonai.cn`.

The repo contains a legacy Next.js app (`.next/`, root `node_modules/`) kept only as migration
reference — **the live project is `fronted/` + `admin/` + `server/`**. Ignore the Next.js code.

## Three deployables

- `fronted/` — Vue 3 + Vite creator workbench (text/image/video generation, model settings). No router; single `App.vue`. Dev port 5175, preview 4173.
- `admin/` — Vue 3 + Vite + Element Plus + Pinia + vue-router admin console. Served under base path `/admin/`. Dev port 5174, preview 4174. Reuses the same session cookie and `/api/admin/*` backend.
- `server/` — FastAPI backend. This is a **proxy** to upstream AI APIs, not a model host. Serves both SPAs' `/api` and `/auth` routes. Runs on port 8000.

## Commands

Backend (from `server/`):
```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
python -m pytest                      # all backend tests
python -m pytest tests/test_auth_models.py::test_name   # single test
python -m compileall server           # quick syntax check (run from repo root)
```
Backend tests set `DATABASE_URL=sqlite:///<tmp>` **before importing the app** and run against a
temp SQLite DB — no MySQL needed. There is no pytest.ini; run pytest from inside `server/`.

Frontend (`fronted/` or `admin/`, identical scripts):
```bash
npm install
npm run dev
npm run build      # runs `vue-tsc -b` typecheck THEN `vite build` — build fails on type errors
npm run test       # vitest run
```

Node smoke/coverage tests live in `scripts/*.test.mjs` (run with `node --test` or the paired `.mjs`).

Local MySQL: `docker compose up -d mysql` (db `genstudio`, user/pass `genstudio/genstudio`).
Same-domain static preview of built SPAs: `docker compose --profile app up -d web` → `http://127.0.0.1:8080/` and `/admin/`.

## Backend architecture

- `app/main.py` (~6200 lines) is the monolithic router: all `/api/*` and `/auth/*` endpoints. Route groups: `/api/auth/*`, `/api/proxy/*` (generation), `/api/catalog/*` (KKYi sync), `/api/credits/*`, `/api/admin/*`. It also serves generation flows with long-running async handoff (`long_request_handoff_seconds`).
- Business logic is split into service modules called by `main.py`: `admin_service`, `catalog_service` (KKYi catalog sync), `credit_service`, `conversation_service`, `model_service`, `prompt_library_service`, `asset_cleanup`, `user_maintenance`.
- `config.py` — all settings from env (prefix `GENSTUDIO_*`). `get_settings()` is `lru_cache`d; loads `server/.env` unless `DATABASE_URL` is sqlite. Production startup **hard-fails** unless safety env is set (secure cookies, dev-login off, auto-create off, real storage) — see `docs/OPERATIONS.md`.
- `database.py` — SQLAlchemy engine (`pool_pre_ping=True`). Contains **manual, idempotent schema-patch helpers** (`_add_column_if_missing`, `_create_*_if_missing`) run at startup in addition to the numbered SQL files in `server/migrations/`. When adding columns/tables, update BOTH: a new `server/migrations/00N_*.sql` file AND the startup patch helpers if dev auto-create must keep working. `GENSTUDIO_AUTO_CREATE_TABLES=false` in production.
- `security.py` — Argon2 password hashing; session/CSRF tokens HMAC-hashed with `secret_key`; **user API keys encrypted with Fernet derived from `SHA256(GENSTUDIO_SECRET_KEY)`**. Losing/changing `GENSTUDIO_SECRET_KEY` makes all stored keys and sessions unrecoverable — it must be backed up with any DB dump.
- `auth.py` — three login paths: local (register/login), official SSO (`exchange_official_code`, code→user via `OFFICIAL_AUTH_EXCHANGE_URL`), and dev-login (`POST /api/auth/dev-login`, disabled in prod). Session written to `genstudio_session` HttpOnly cookie. Mutating routes require CSRF (`require_csrf`). Admins resolved from `GENSTUDIO_ADMIN_EMAILS` / `GENSTUDIO_ADMIN_IDENTIFIERS`.
- `admin_permissions.py` — role→permission matrix (`can()`, `resolve_admin_role`); check before adding admin routes.
- `rate_limit.py` — per-window limits for login/generation/model-test/upload.

## Domain concepts

- **Models**: private per-user model configs vs. public models an admin publishes (`publish_model`/`unpublish_model`). Sub-models carry per-model `baseURL` + encrypted API key. Catalog synced from KKYi via `catalog_service`.
- **Credits**: usage billing (`credit_service`, `/api/credits/*`, admin adjust/batch-adjust). Per-model credit pricing configurable in admin.
- **Assets**: generated/uploaded assets go to object storage (S3-compatible, `storage.py`); `asset_cleanup` prunes them. `generated_assets/` and `uploaded_assets/` at repo root are local dev output dirs.

## Deployment

Production is the Guangzhou server `175.178.189.234`, Docker container `genstudio-api` (backend, port 8000), MySQL container `genstudio-mysql`, behind the shared `nginx` container. Backend image built from `server/Dockerfile` (uses a China PyPI mirror via `PIP_INDEX_URL` build arg). Frontends are built (`npm run build`) and served as static files. See `docs/OPERATIONS.md` for the full production env contract, migration, and backup procedure.
