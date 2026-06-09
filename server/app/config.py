from __future__ import annotations

import os
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import BaseModel, Field


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _csv_env(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if value is None:
        return default
    return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]


def _email_csv_env(name: str, default: list[str]) -> list[str]:
    return [item.strip().lower() for item in _csv_env(name, default) if item.strip()]


def _identity_csv_env(name: str, default: list[str]) -> list[str]:
    return [item.strip().lower() for item in _csv_env(name, default) if item.strip()]


def _default_cors_origins() -> list[str]:
    return _csv_env(
        "GENSTUDIO_CORS_ORIGINS",
        [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:3001",
            "http://localhost:3001",
            "https://studio.cylonai.cn",
        ],
    )


def _is_localhost_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    host = parsed.hostname or ""
    return host in {"127.0.0.1", "localhost", "::1"}


class Settings(BaseModel):
    environment: str = os.getenv("GENSTUDIO_ENV", os.getenv("ENVIRONMENT", "development")).strip().lower()
    database_url: str = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://genstudio:genstudio@127.0.0.1:3306/genstudio?charset=utf8mb4",
    )
    secret_key: str = os.getenv("GENSTUDIO_SECRET_KEY", "dev-genstudio-secret-change-me")
    session_cookie_name: str = os.getenv("GENSTUDIO_SESSION_COOKIE", "genstudio_session")
    session_ttl_days: int = _int_env("GENSTUDIO_SESSION_TTL_DAYS", 14)
    cookie_secure: bool = _bool_env("GENSTUDIO_COOKIE_SECURE", False)
    cookie_samesite: str = os.getenv("GENSTUDIO_COOKIE_SAMESITE", "lax").strip().lower()
    cookie_domain: str = os.getenv("GENSTUDIO_COOKIE_DOMAIN", "").strip()
    frontend_url: str = os.getenv("GENSTUDIO_FRONTEND_URL", "http://127.0.0.1:5173")
    cors_origins: list[str] = Field(default_factory=_default_cors_origins)
    official_auth_exchange_url: str = os.getenv("OFFICIAL_AUTH_EXCHANGE_URL", "")
    official_auth_client_id: str = os.getenv("OFFICIAL_AUTH_CLIENT_ID", "genstudio")
    official_auth_client_secret: str = os.getenv("OFFICIAL_AUTH_CLIENT_SECRET", "")
    auto_create_tables: bool = _bool_env("GENSTUDIO_AUTO_CREATE_TABLES", True)
    enable_dev_login: bool = _bool_env("GENSTUDIO_ENABLE_DEV_LOGIN", True)
    csrf_ttl_minutes: int = _int_env("GENSTUDIO_CSRF_TTL_MINUTES", 120)
    login_max_failed_attempts: int = _int_env("GENSTUDIO_LOGIN_MAX_FAILED_ATTEMPTS", 5)
    login_lock_minutes: int = _int_env("GENSTUDIO_LOGIN_LOCK_MINUTES", 15)
    request_timeout_seconds: float = float(os.getenv("GENSTUDIO_REQUEST_TIMEOUT_SECONDS", "300"))
    long_request_handoff_seconds: float = float(os.getenv("GENSTUDIO_LONG_REQUEST_HANDOFF_SECONDS", "5"))
    upstream_retry_attempts: int = _int_env("GENSTUDIO_UPSTREAM_RETRY_ATTEMPTS", 1)
    rate_limit_window_seconds: int = _int_env("GENSTUDIO_RATE_LIMIT_WINDOW_SECONDS", 60)
    rate_limit_login_per_window: int = _int_env("GENSTUDIO_RATE_LIMIT_LOGIN_PER_WINDOW", 20)
    rate_limit_generation_per_window: int = _int_env("GENSTUDIO_RATE_LIMIT_GENERATION_PER_WINDOW", 30)
    rate_limit_model_test_per_window: int = _int_env("GENSTUDIO_RATE_LIMIT_MODEL_TEST_PER_WINDOW", 30)
    rate_limit_upload_per_window: int = _int_env("GENSTUDIO_RATE_LIMIT_UPLOAD_PER_WINDOW", 40)
    object_storage_public_base_url: str = os.getenv("OBJECT_STORAGE_PUBLIC_BASE_URL", "").strip()
    object_storage_enabled: bool = _bool_env("OBJECT_STORAGE_ENABLED", False)
    object_storage_endpoint_url: str = os.getenv("OBJECT_STORAGE_ENDPOINT_URL", "").strip()
    object_storage_region: str = os.getenv("OBJECT_STORAGE_REGION", "auto").strip()
    object_storage_bucket: str = os.getenv("OBJECT_STORAGE_BUCKET", "").strip()
    object_storage_access_key_id: str = os.getenv("OBJECT_STORAGE_ACCESS_KEY_ID", "").strip()
    object_storage_secret_access_key: str = os.getenv("OBJECT_STORAGE_SECRET_ACCESS_KEY", "").strip()
    object_storage_key_prefix: str = os.getenv("OBJECT_STORAGE_KEY_PREFIX", "genstudio").strip().strip("/")
    kkyi_catalog_base_url: str = os.getenv("KKYI_CATALOG_BASE_URL", "https://www.kkyi.com").strip()
    kkyi_catalog_bearer_token: str = os.getenv("KKYI_CATALOG_BEARER_TOKEN", "").strip()
    admin_emails: list[str] = Field(
        default_factory=lambda: _email_csv_env("GENSTUDIO_ADMIN_EMAILS", ["cage_ben@sina.com"])
    )
    admin_identifiers: list[str] = Field(
        default_factory=lambda: _identity_csv_env("GENSTUDIO_ADMIN_IDENTIFIERS", [])
    )

    @property
    def is_production(self) -> bool:
        return self.environment in {"prod", "production"}

    def validate_startup(self) -> None:
        if not self.is_production:
            return

        errors: list[str] = []
        if self.secret_key == "dev-genstudio-secret-change-me" or len(self.secret_key) < 32:
            errors.append("GENSTUDIO_SECRET_KEY must be a long random secret in production.")
        if not self.cookie_secure:
            errors.append("GENSTUDIO_COOKIE_SECURE must be true in production.")
        if self.enable_dev_login:
            errors.append("GENSTUDIO_ENABLE_DEV_LOGIN must be false in production.")
        if self.auto_create_tables:
            errors.append("GENSTUDIO_AUTO_CREATE_TABLES must be false in production; run migrations before deploy.")
        if not self.frontend_url.startswith("https://"):
            errors.append("GENSTUDIO_FRONTEND_URL must use HTTPS in production.")
        if not self.official_auth_exchange_url:
            errors.append("OFFICIAL_AUTH_EXCHANGE_URL must be configured in production.")
        if not self.official_auth_client_id:
            errors.append("OFFICIAL_AUTH_CLIENT_ID must be configured in production.")
        if not self.official_auth_client_secret:
            errors.append("OFFICIAL_AUTH_CLIENT_SECRET must be configured in production.")
        if not self.cors_origins or any(_is_localhost_origin(origin) for origin in self.cors_origins):
            errors.append("GENSTUDIO_CORS_ORIGINS must be a production HTTPS domain whitelist without localhost.")
        if any(not origin.startswith("https://") for origin in self.cors_origins):
            errors.append("GENSTUDIO_CORS_ORIGINS must only contain HTTPS origins in production.")
        if self.cookie_samesite not in {"lax", "strict", "none"}:
            errors.append("GENSTUDIO_COOKIE_SAMESITE must be lax, strict, or none.")
        if self.cookie_samesite == "none" and not self.cookie_secure:
            errors.append("GENSTUDIO_COOKIE_SECURE must be true when SameSite=None.")
        if not self.object_storage_enabled:
            errors.append("OBJECT_STORAGE_ENABLED must be true in production.")
        if not self.object_storage_public_base_url.startswith("https://"):
            errors.append("OBJECT_STORAGE_PUBLIC_BASE_URL must be configured with HTTPS in production.")
        if not self.object_storage_endpoint_url.startswith("https://"):
            errors.append("OBJECT_STORAGE_ENDPOINT_URL must be configured with HTTPS in production.")
        if not self.object_storage_bucket:
            errors.append("OBJECT_STORAGE_BUCKET must be configured in production.")
        if not self.object_storage_access_key_id:
            errors.append("OBJECT_STORAGE_ACCESS_KEY_ID must be configured in production.")
        if not self.object_storage_secret_access_key:
            errors.append("OBJECT_STORAGE_SECRET_ACCESS_KEY must be configured in production.")
        if errors:
            raise ValueError("Production configuration is unsafe: " + " ".join(errors))


@lru_cache
def get_settings() -> Settings:
    return Settings()
