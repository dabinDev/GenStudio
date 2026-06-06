from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseModel):
    database_url: str = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://genstudio:genstudio@127.0.0.1:3306/genstudio?charset=utf8mb4",
    )
    secret_key: str = os.getenv("GENSTUDIO_SECRET_KEY", "dev-genstudio-secret-change-me")
    session_cookie_name: str = os.getenv("GENSTUDIO_SESSION_COOKIE", "genstudio_session")
    session_ttl_days: int = int(os.getenv("GENSTUDIO_SESSION_TTL_DAYS", "14"))
    cookie_secure: bool = _bool_env("GENSTUDIO_COOKIE_SECURE", False)
    frontend_url: str = os.getenv("GENSTUDIO_FRONTEND_URL", "http://127.0.0.1:5173")
    official_auth_exchange_url: str = os.getenv("OFFICIAL_AUTH_EXCHANGE_URL", "")
    official_auth_client_id: str = os.getenv("OFFICIAL_AUTH_CLIENT_ID", "genstudio")
    official_auth_client_secret: str = os.getenv("OFFICIAL_AUTH_CLIENT_SECRET", "")
    auto_create_tables: bool = _bool_env("GENSTUDIO_AUTO_CREATE_TABLES", True)
    enable_dev_login: bool = _bool_env("GENSTUDIO_ENABLE_DEV_LOGIN", True)
    csrf_ttl_minutes: int = int(os.getenv("GENSTUDIO_CSRF_TTL_MINUTES", "120"))
    login_max_failed_attempts: int = int(os.getenv("GENSTUDIO_LOGIN_MAX_FAILED_ATTEMPTS", "5"))
    login_lock_minutes: int = int(os.getenv("GENSTUDIO_LOGIN_LOCK_MINUTES", "15"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
