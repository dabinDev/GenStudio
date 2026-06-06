from __future__ import annotations

import os
import sys
import tempfile

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

db_path = os.path.join(tempfile.gettempdir(), "genstudio-rate-limit-test.sqlite3")
if os.path.exists(db_path):
    os.remove(db_path)

os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["GENSTUDIO_SECRET_KEY"] = "test-secret"

from app.database import Base, engine  # noqa: E402
import app.main as main_module  # noqa: E402
from app.main import app  # noqa: E402


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    main_module.rate_limiter.clear()


def test_login_route_is_rate_limited(monkeypatch) -> None:
    settings = main_module.get_settings()
    monkeypatch.setattr(settings, "rate_limit_login_per_window", 1)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60)
    client = TestClient(app)

    first = client.post("/api/auth/login", json={"identifier": "missing@example.com", "password": "WrongPass123!"})
    second = client.post("/api/auth/login", json={"identifier": "missing@example.com", "password": "WrongPass123!"})

    assert first.status_code == 401
    assert second.status_code == 429
    assert second.json()["detail"]["message"] == "请求过于频繁，请稍后再试。"
