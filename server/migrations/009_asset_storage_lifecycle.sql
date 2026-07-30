-- Generated asset local-cache and Cloudflare R2 lifecycle fields.
-- Apply after 008_public_model_accent_color.sql. Safe to run more than once on MySQL.

DROP PROCEDURE IF EXISTS genstudio_add_column_if_missing;
DROP PROCEDURE IF EXISTS genstudio_add_index_if_missing;

DELIMITER //
CREATE PROCEDURE genstudio_add_column_if_missing(
  IN p_table_name VARCHAR(64),
  IN p_column_name VARCHAR(64),
  IN p_column_definition TEXT
)
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_table_name
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_table_name AND COLUMN_NAME = p_column_name
  ) THEN
    SET @genstudio_sql = CONCAT(
      'ALTER TABLE `', p_table_name, '` ADD COLUMN `', p_column_name, '` ', p_column_definition
    );
    PREPARE genstudio_stmt FROM @genstudio_sql;
    EXECUTE genstudio_stmt;
    DEALLOCATE PREPARE genstudio_stmt;
  END IF;
END//

CREATE PROCEDURE genstudio_add_index_if_missing(
  IN p_table_name VARCHAR(64),
  IN p_index_name VARCHAR(64),
  IN p_index_definition TEXT
)
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_table_name
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_table_name AND INDEX_NAME = p_index_name
  ) THEN
    SET @genstudio_sql = CONCAT(
      'CREATE INDEX `', p_index_name, '` ON `', p_table_name, '` ', p_index_definition
    );
    PREPARE genstudio_stmt FROM @genstudio_sql;
    EXECUTE genstudio_stmt;
    DEALLOCATE PREPARE genstudio_stmt;
  END IF;
END//
DELIMITER ;

CALL genstudio_add_column_if_missing('generated_assets', 'storage_status', 'VARCHAR(32) NOT NULL DEFAULT ''local_pending''');
CALL genstudio_add_column_if_missing('generated_assets', 'local_path', 'TEXT');
CALL genstudio_add_column_if_missing('generated_assets', 'local_thumbnail_path', 'TEXT');
CALL genstudio_add_column_if_missing('generated_assets', 'r2_object_key', 'TEXT');
CALL genstudio_add_column_if_missing('generated_assets', 'r2_thumbnail_key', 'TEXT');
CALL genstudio_add_column_if_missing('generated_assets', 'r2_url', 'TEXT');
CALL genstudio_add_column_if_missing('generated_assets', 'r2_thumbnail_url', 'TEXT');
CALL genstudio_add_column_if_missing('generated_assets', 'content_type', 'VARCHAR(128) NOT NULL DEFAULT ''''');
CALL genstudio_add_column_if_missing('generated_assets', 'size_bytes', 'BIGINT NOT NULL DEFAULT 0');
CALL genstudio_add_column_if_missing('generated_assets', 'sha256', 'VARCHAR(64) NOT NULL DEFAULT ''''');
CALL genstudio_add_column_if_missing('generated_assets', 'local_expires_at', 'DATETIME NULL');
CALL genstudio_add_column_if_missing('generated_assets', 'sync_attempts', 'INTEGER NOT NULL DEFAULT 0');
CALL genstudio_add_column_if_missing('generated_assets', 'last_sync_error', 'TEXT');
CALL genstudio_add_column_if_missing('generated_assets', 'synced_at', 'DATETIME NULL');
CALL genstudio_add_column_if_missing('generated_assets', 'storage_updated_at', 'DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP');

UPDATE generated_assets
SET storage_status = COALESCE(NULLIF(storage_status, ''), 'local_pending'),
    local_path = COALESCE(local_path, ''),
    local_thumbnail_path = COALESCE(local_thumbnail_path, ''),
    r2_object_key = COALESCE(r2_object_key, ''),
    r2_thumbnail_key = COALESCE(r2_thumbnail_key, ''),
    r2_url = COALESCE(r2_url, ''),
    r2_thumbnail_url = COALESCE(r2_thumbnail_url, ''),
    content_type = COALESCE(content_type, ''),
    size_bytes = COALESCE(size_bytes, 0),
    sha256 = COALESCE(sha256, ''),
    sync_attempts = COALESCE(sync_attempts, 0),
    last_sync_error = COALESCE(last_sync_error, ''),
    storage_updated_at = COALESCE(storage_updated_at, created_at, CURRENT_TIMESTAMP);

CALL genstudio_add_index_if_missing('generated_assets', 'ix_generated_assets_storage_status', '(storage_status)');
CALL genstudio_add_index_if_missing('generated_assets', 'ix_generated_assets_local_expires_at', '(local_expires_at)');
CALL genstudio_add_index_if_missing('generated_assets', 'ix_generated_assets_storage_updated_at', '(storage_updated_at)');

DROP PROCEDURE IF EXISTS genstudio_add_column_if_missing;
DROP PROCEDURE IF EXISTS genstudio_add_index_if_missing;
