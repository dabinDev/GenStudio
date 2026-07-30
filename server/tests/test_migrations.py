from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker


ASSET_STORAGE_COLUMNS = {
    "storage_status",
    "local_path",
    "local_thumbnail_path",
    "r2_object_key",
    "r2_thumbnail_key",
    "r2_url",
    "r2_thumbnail_url",
    "content_type",
    "size_bytes",
    "sha256",
    "local_expires_at",
    "sync_attempts",
    "last_sync_error",
    "synced_at",
    "storage_updated_at",
}


def test_credit_system_migration_creates_required_tables() -> None:
    sql = (Path(__file__).resolve().parents[1] / "migrations" / "005_credit_system.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS system_settings" in sql
    assert "CREATE TABLE IF NOT EXISTS user_credit_accounts" in sql
    assert "CREATE TABLE IF NOT EXISTS credit_transactions" in sql
    assert "CREATE TABLE IF NOT EXISTS credit_pricing_rules" in sql
    assert "INSERT INTO credit_pricing_rules" in sql


def test_admin_runtime_migration_creates_required_tables() -> None:
    sql = (Path(__file__).resolve().parents[1] / "migrations" / "006_admin_runtime_tables.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS admin_role_assignments" in sql
    assert "CREATE TABLE IF NOT EXISTS model_health_checks" in sql
    assert "CREATE TABLE IF NOT EXISTS task_events" in sql
    assert "ix_admin_role_assignments_user_id" in sql
    assert "ix_model_health_checks_status" in sql
    assert "ix_task_events_task_id" in sql


def test_prompt_scene_template_migration_creates_library_tables() -> None:
    sql = (Path(__file__).resolve().parents[1] / "migrations" / "007_prompt_scene_templates.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS prompt_scene_templates" in sql
    assert "CREATE TABLE IF NOT EXISTS prompt_scene_template_events" in sql
    assert "CONSTRAINT uq_prompt_scene_template_external_id UNIQUE (external_id)" in sql
    assert "ix_prompt_scene_templates_enabled" in sql
    assert "ix_prompt_scene_template_events_template_id" in sql
    assert "FOREIGN KEY(template_id) REFERENCES prompt_scene_templates" in sql


def test_public_model_accent_migration_and_startup_patch_add_the_color_column() -> None:
    root = Path(__file__).resolve().parents[1]
    migration_sql = (root / "migrations" / "008_public_model_accent_color.sql").read_text(encoding="utf-8")
    database_source = (root / "app" / "database.py").read_text(encoding="utf-8")

    assert "ALTER TABLE models ADD COLUMN public_accent_color VARCHAR(7) NOT NULL DEFAULT '';" in migration_sql
    assert '"public_accent_color": "VARCHAR(7) NOT NULL DEFAULT \'\'"' in database_source


def test_asset_storage_lifecycle_migration_adds_columns_and_indexes() -> None:
    sql = (Path(__file__).resolve().parents[1] / "migrations" / "009_asset_storage_lifecycle.sql").read_text(encoding="utf-8")

    for column_name in ASSET_STORAGE_COLUMNS:
        assert f"'{column_name}'" in sql
    assert "ix_generated_assets_storage_status" in sql
    assert "ix_generated_assets_local_expires_at" in sql
    assert "ix_generated_assets_storage_updated_at" in sql


def test_init_db_patches_asset_storage_columns_on_legacy_table(tmp_path, monkeypatch) -> None:
    from app import database

    test_engine = create_engine(f"sqlite:///{tmp_path / 'legacy-assets.sqlite3'}")
    with test_engine.begin() as connection:
        connection.execute(text("CREATE TABLE generated_assets (id VARCHAR(64) PRIMARY KEY)"))

    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(
        database,
        "SessionLocal",
        sessionmaker(bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False),
    )

    database.init_db()

    inspector = inspect(test_engine)
    columns = {column["name"] for column in inspector.get_columns("generated_assets")}
    indexes = {index["name"] for index in inspector.get_indexes("generated_assets")}
    assert ASSET_STORAGE_COLUMNS <= columns
    assert {
        "ix_generated_assets_storage_status",
        "ix_generated_assets_local_expires_at",
        "ix_generated_assets_storage_updated_at",
    } <= indexes
