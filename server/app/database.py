from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _connect_args(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


settings = get_settings()
engine = create_engine(
    settings.database_url,
    connect_args=_connect_args(settings.database_url),
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    from app import db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        inspector = inspect(connection)
        if inspector.has_table("models"):
            columns = {column["name"] for column in inspector.get_columns("models")}
            if "is_public" not in columns:
                connection.execute(text("ALTER TABLE models ADD COLUMN is_public BOOL NOT NULL DEFAULT FALSE"))
                connection.execute(text("CREATE INDEX ix_models_is_public ON models (is_public)"))
            connection.execute(
                text(
                    """
                    UPDATE models
                    SET is_public = TRUE
                    WHERE capability = 'text'
                      AND (
                        LOWER(name) LIKE '%gpt-5.5%'
                        OR id IN (
                          SELECT model_group_id
                          FROM sub_models
                          WHERE LOWER(model_name) = 'gpt-5.5'
                        )
                      )
                    """
                )
            )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
