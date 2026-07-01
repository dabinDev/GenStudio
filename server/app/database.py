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


def _create_model_health_checks_if_missing(connection, inspector) -> None:
    if inspector.has_table("model_health_checks"):
        return
    connection.execute(
        text(
            _column_ddl(
                connection,
                """
                CREATE TABLE model_health_checks (
                    id VARCHAR(64) NOT NULL,
                    model_group_id VARCHAR(64) NOT NULL,
                    sub_model_id VARCHAR(64) NOT NULL DEFAULT '',
                    admin_user_id VARCHAR(64),
                    status VARCHAR(32) NOT NULL,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    message VARCHAR(512) NOT NULL DEFAULT '',
                    raw_json TEXT,
                    created_at DATETIME NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(model_group_id) REFERENCES models (id) ON DELETE CASCADE,
                    FOREIGN KEY(admin_user_id) REFERENCES users (id) ON DELETE SET NULL
                )
                """,
            )
        )
    )
    _create_index_if_missing(connection, "ix_model_health_checks_model_group_id", "model_health_checks", "model_group_id")
    _create_index_if_missing(connection, "ix_model_health_checks_created_at", "model_health_checks", "created_at")
    _create_index_if_missing(connection, "ix_model_health_checks_sub_model_id", "model_health_checks", "sub_model_id")
    _create_index_if_missing(connection, "ix_model_health_checks_admin_user_id", "model_health_checks", "admin_user_id")
    _create_index_if_missing(connection, "ix_model_health_checks_status", "model_health_checks", "status")


def _create_admin_role_assignments_if_missing(connection, inspector) -> None:
    if inspector.has_table("admin_role_assignments"):
        return
    connection.execute(
        text(
            _column_ddl(
                connection,
                """
                CREATE TABLE admin_role_assignments (
                    id VARCHAR(64) NOT NULL,
                    user_id VARCHAR(64) NOT NULL,
                    role VARCHAR(32) NOT NULL DEFAULT 'viewer',
                    assigned_by VARCHAR(64) NOT NULL DEFAULT '',
                    note VARCHAR(512) NOT NULL DEFAULT '',
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    PRIMARY KEY (id),
                    UNIQUE (user_id),
                    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """,
            )
        )
    )
    _create_index_if_missing(connection, "ix_admin_role_assignments_user_id", "admin_role_assignments", "user_id")
    _create_index_if_missing(connection, "ix_admin_role_assignments_role", "admin_role_assignments", "role")
    _create_index_if_missing(connection, "ix_admin_role_assignments_assigned_by", "admin_role_assignments", "assigned_by")


def _create_task_events_if_missing(connection, inspector) -> None:
    if inspector.has_table("task_events"):
        return
    connection.execute(
        text(
            _column_ddl(
                connection,
                """
                CREATE TABLE task_events (
                    id VARCHAR(64) NOT NULL,
                    task_id VARCHAR(128) NOT NULL,
                    event_type VARCHAR(64) NOT NULL DEFAULT 'event',
                    status VARCHAR(32) NOT NULL DEFAULT '',
                    capability VARCHAR(32) NOT NULL DEFAULT '',
                    endpoint VARCHAR(128) NOT NULL DEFAULT '',
                    user_id VARCHAR(64),
                    model_group_id VARCHAR(64),
                    sub_model_id VARCHAR(64),
                    conversation_id VARCHAR(64) NOT NULL DEFAULT '',
                    message_id VARCHAR(64) NOT NULL DEFAULT '',
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    message VARCHAR(512) NOT NULL DEFAULT '',
                    payload_json TEXT,
                    created_at DATETIME NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL,
                    FOREIGN KEY(model_group_id) REFERENCES models (id) ON DELETE SET NULL,
                    FOREIGN KEY(sub_model_id) REFERENCES sub_models (id) ON DELETE SET NULL
                )
                """,
            )
        )
    )
    for column_name in (
        "task_id",
        "event_type",
        "status",
        "capability",
        "user_id",
        "model_group_id",
        "sub_model_id",
        "conversation_id",
        "message_id",
        "created_at",
    ):
        _create_index_if_missing(connection, f"ix_task_events_{column_name}", "task_events", column_name)


def _create_prompt_template_versions_if_missing(connection, inspector) -> None:
    if inspector.has_table("prompt_template_versions"):
        return
    connection.execute(
        text(
            _column_ddl(
                connection,
                """
                CREATE TABLE prompt_template_versions (
                    id VARCHAR(64) NOT NULL,
                    template_id VARCHAR(64) NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    name VARCHAR(128) NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    enabled BOOLEAN NOT NULL DEFAULT 1,
                    updated_by VARCHAR(64) NOT NULL DEFAULT '',
                    created_at DATETIME NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(template_id) REFERENCES prompt_templates (id) ON DELETE CASCADE
                )
                """,
            )
        )
    )
    _create_index_if_missing(connection, "ix_prompt_template_versions_template_id", "prompt_template_versions", "template_id")
    _create_index_if_missing(connection, "ix_prompt_template_versions_updated_by", "prompt_template_versions", "updated_by")
    _create_index_if_missing(connection, "ix_prompt_template_versions_created_at", "prompt_template_versions", "created_at")


def _create_prompt_scene_templates_if_missing(connection, inspector) -> None:
    if not inspector.has_table("prompt_scene_templates"):
        connection.execute(
            text(
                _column_ddl(
                    connection,
                    """
                    CREATE TABLE prompt_scene_templates (
                        id VARCHAR(64) NOT NULL,
                        external_id VARCHAR(128) NOT NULL,
                        category_id VARCHAR(128) NOT NULL DEFAULT '',
                        document_title VARCHAR(255) NOT NULL DEFAULT '',
                        document_url TEXT NOT NULL DEFAULT '',
                        section VARCHAR(255) NOT NULL DEFAULT '',
                        category VARCHAR(255) NOT NULL DEFAULT '',
                        subcategory VARCHAR(255) NOT NULL DEFAULT '',
                        title VARCHAR(255) NOT NULL DEFAULT '',
                        prompt_text TEXT NOT NULL DEFAULT '',
                        prompt_summary TEXT NOT NULL DEFAULT '',
                        tags_json TEXT NOT NULL DEFAULT '[]',
                        source VARCHAR(128) NOT NULL DEFAULT '',
                        original_no VARCHAR(64) NOT NULL DEFAULT '',
                        image_url TEXT NOT NULL DEFAULT '',
                        model VARCHAR(128) NOT NULL DEFAULT '',
                        likes INTEGER NOT NULL DEFAULT 0,
                        views INTEGER NOT NULL DEFAULT 0,
                        weight INTEGER NOT NULL DEFAULT 0,
                        enabled BOOLEAN NOT NULL DEFAULT 1,
                        raw_json TEXT NOT NULL DEFAULT '{}',
                        use_count INTEGER NOT NULL DEFAULT 0,
                        click_count INTEGER NOT NULL DEFAULT 0,
                        impression_count INTEGER NOT NULL DEFAULT 0,
                        imported_at DATETIME NOT NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        PRIMARY KEY (id),
                        UNIQUE (external_id)
                    )
                    """,
                )
            )
        )
        for column_name in (
            "external_id",
            "category_id",
            "section",
            "category",
            "subcategory",
            "title",
            "source",
            "original_no",
            "model",
            "weight",
            "enabled",
        ):
            _create_index_if_missing(connection, f"ix_prompt_scene_templates_{column_name}", "prompt_scene_templates", column_name)

    if not inspector.has_table("prompt_scene_template_events"):
        connection.execute(
            text(
                _column_ddl(
                    connection,
                    """
                    CREATE TABLE prompt_scene_template_events (
                        id VARCHAR(64) NOT NULL,
                        template_id VARCHAR(64) NOT NULL,
                        user_id VARCHAR(64),
                        event_type VARCHAR(32) NOT NULL DEFAULT 'impression',
                        image_url TEXT NOT NULL DEFAULT '',
                        metadata_json TEXT NOT NULL DEFAULT '{}',
                        created_at DATETIME NOT NULL,
                        PRIMARY KEY (id),
                        FOREIGN KEY(template_id) REFERENCES prompt_scene_templates (id) ON DELETE CASCADE,
                        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
                    )
                    """,
                )
            )
        )
        for column_name in ("template_id", "user_id", "event_type", "created_at"):
            _create_index_if_missing(connection, f"ix_prompt_scene_template_events_{column_name}", "prompt_scene_template_events", column_name)


def init_db() -> None:
    from app import db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        inspector = inspect(connection)
        _create_admin_role_assignments_if_missing(connection, inspector)
        _create_model_health_checks_if_missing(connection, inspector)
        _create_task_events_if_missing(connection, inspector)
        _create_prompt_template_versions_if_missing(connection, inspector)
        _create_prompt_scene_templates_if_missing(connection, inspector)
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
        if inspector.has_table("sessions"):
            columns = {column["name"] for column in inspector.get_columns("sessions")}
            _add_column_if_missing(connection, "sessions", columns, "client_ip", "VARCHAR(64) NOT NULL DEFAULT ''")
    with SessionLocal() as db:
        from app.credit_service import ensure_default_pricing_rules

        ensure_default_pricing_rules(db)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
