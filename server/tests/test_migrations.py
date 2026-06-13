from pathlib import Path


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
