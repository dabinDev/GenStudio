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


def _column_ddl(connection, ddl: str) -> str:
    if connection.dialect.name == "sqlite":
        return ddl.replace("BOOL", "BOOLEAN").replace("TRUE", "1").replace("FALSE", "0")
    return ddl


def _add_column_if_missing(connection, table_name: str, columns: set[str], column_name: str, ddl: str) -> None:
    if column_name in columns:
        return
    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {_column_ddl(connection, ddl)}"))
    columns.add(column_name)


def _create_index_if_missing(connection, index_name: str, table_name: str, column_name: str) -> None:
    try:
        connection.execute(text(f"CREATE INDEX {index_name} ON {table_name} ({column_name})"))
    except Exception:
        pass


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
                columns.add("is_public")
            model_columns = {
                "public_display_name": "VARCHAR(255) NOT NULL DEFAULT ''",
                "public_description": "TEXT",
                "input_hint": "TEXT",
                "icon_url": "TEXT",
                "public_tags_json": "TEXT",
                "prompt_optimize_enabled": "BOOL NOT NULL DEFAULT TRUE",
                "default_parameters_json": "TEXT",
            }
            for column_name, ddl in model_columns.items():
                _add_column_if_missing(connection, "models", columns, column_name, ddl)
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
        if inspector.has_table("call_logs"):
            columns = {column["name"] for column in inspector.get_columns("call_logs")}
            call_log_columns = {
                "request_params_json": "TEXT",
                "response_summary_json": "TEXT",
                "conversation_id": "VARCHAR(64) NOT NULL DEFAULT ''",
                "message_id": "VARCHAR(64) NOT NULL DEFAULT ''",
                "is_public_model": "BOOL NOT NULL DEFAULT FALSE",
            }
            for column_name, ddl in call_log_columns.items():
                _add_column_if_missing(connection, "call_logs", columns, column_name, ddl)
            _create_index_if_missing(connection, "ix_call_logs_conversation_id", "call_logs", "conversation_id")
            _create_index_if_missing(connection, "ix_call_logs_message_id", "call_logs", "message_id")
            _create_index_if_missing(connection, "ix_call_logs_is_public_model", "call_logs", "is_public_model")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
