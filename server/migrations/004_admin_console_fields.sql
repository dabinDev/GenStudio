-- Admin console governance fields and audit tables.
-- Apply after 003_public_models.sql. Safe to run more than once on MySQL.

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
    SELECT 1
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = p_table_name
  ) AND NOT EXISTS (
    SELECT 1
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = p_table_name
      AND COLUMN_NAME = p_column_name
  ) THEN
    SET @genstudio_sql = CONCAT('ALTER TABLE `', p_table_name, '` ADD COLUMN `', p_column_name, '` ', p_column_definition);
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
    SELECT 1
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = p_table_name
  ) AND NOT EXISTS (
    SELECT 1
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = p_table_name
      AND INDEX_NAME = p_index_name
  ) THEN
    SET @genstudio_sql = CONCAT('CREATE INDEX `', p_index_name, '` ON `', p_table_name, '` ', p_index_definition);
    PREPARE genstudio_stmt FROM @genstudio_sql;
    EXECUTE genstudio_stmt;
    DEALLOCATE PREPARE genstudio_stmt;
  END IF;
END//
DELIMITER ;

CALL genstudio_add_column_if_missing('models', 'is_public', 'BOOL NOT NULL DEFAULT FALSE');
CALL genstudio_add_column_if_missing('models', 'public_display_name', 'VARCHAR(255) NOT NULL DEFAULT ''''');
CALL genstudio_add_column_if_missing('models', 'public_description', 'TEXT');
CALL genstudio_add_column_if_missing('models', 'input_hint', 'TEXT');
CALL genstudio_add_column_if_missing('models', 'icon_url', 'TEXT');
CALL genstudio_add_column_if_missing('models', 'public_tags_json', 'TEXT');
CALL genstudio_add_column_if_missing('models', 'prompt_optimize_enabled', 'BOOL NOT NULL DEFAULT TRUE');
CALL genstudio_add_column_if_missing('models', 'default_parameters_json', 'TEXT');
CALL genstudio_add_index_if_missing('models', 'ix_models_is_public', '(is_public)');

UPDATE models
SET
  public_description = COALESCE(public_description, ''),
  input_hint = COALESCE(input_hint, ''),
  icon_url = COALESCE(icon_url, ''),
  public_tags_json = COALESCE(public_tags_json, '[]'),
  default_parameters_json = COALESCE(default_parameters_json, '{}');

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
  );

CALL genstudio_add_column_if_missing('call_logs', 'request_params_json', 'TEXT');
CALL genstudio_add_column_if_missing('call_logs', 'response_summary_json', 'TEXT');
CALL genstudio_add_column_if_missing('call_logs', 'conversation_id', 'VARCHAR(64) NOT NULL DEFAULT ''''');
CALL genstudio_add_column_if_missing('call_logs', 'message_id', 'VARCHAR(64) NOT NULL DEFAULT ''''');
CALL genstudio_add_column_if_missing('call_logs', 'is_public_model', 'BOOL NOT NULL DEFAULT FALSE');
CALL genstudio_add_index_if_missing('call_logs', 'ix_call_logs_conversation_id', '(conversation_id)');
CALL genstudio_add_index_if_missing('call_logs', 'ix_call_logs_message_id', '(message_id)');
CALL genstudio_add_index_if_missing('call_logs', 'ix_call_logs_is_public_model', '(is_public_model)');

UPDATE call_logs
SET
  request_params_json = COALESCE(request_params_json, '{}'),
  response_summary_json = COALESCE(response_summary_json, '{}');

CREATE TABLE IF NOT EXISTS prompt_templates (
  id VARCHAR(64) NOT NULL,
  capability VARCHAR(32) NOT NULL,
  model_group_id VARCHAR(64) NOT NULL DEFAULT '',
  template_type VARCHAR(64) NOT NULL DEFAULT 'prompt_optimize',
  name VARCHAR(128) NOT NULL DEFAULT '',
  content TEXT NOT NULL,
  enabled BOOL NOT NULL DEFAULT TRUE,
  updated_by VARCHAR(64) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT uq_prompt_template_scope UNIQUE (capability, model_group_id, template_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CALL genstudio_add_index_if_missing('prompt_templates', 'ix_prompt_templates_capability', '(capability)');
CALL genstudio_add_index_if_missing('prompt_templates', 'ix_prompt_templates_model_group_id', '(model_group_id)');
CALL genstudio_add_index_if_missing('prompt_templates', 'ix_prompt_templates_template_type', '(template_type)');
CALL genstudio_add_index_if_missing('prompt_templates', 'ix_prompt_templates_updated_by', '(updated_by)');

CREATE TABLE IF NOT EXISTS admin_operation_logs (
  id VARCHAR(64) NOT NULL,
  admin_user_id VARCHAR(64),
  action VARCHAR(64) NOT NULL,
  target_type VARCHAR(64) NOT NULL,
  target_id VARCHAR(128) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL DEFAULT 'success',
  summary_json TEXT NOT NULL,
  ip_hash VARCHAR(128) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY(admin_user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CALL genstudio_add_index_if_missing('admin_operation_logs', 'ix_admin_operation_logs_admin_user_id', '(admin_user_id)');
CALL genstudio_add_index_if_missing('admin_operation_logs', 'ix_admin_operation_logs_action', '(action)');
CALL genstudio_add_index_if_missing('admin_operation_logs', 'ix_admin_operation_logs_target_type', '(target_type)');
CALL genstudio_add_index_if_missing('admin_operation_logs', 'ix_admin_operation_logs_target_id', '(target_id)');
CALL genstudio_add_index_if_missing('admin_operation_logs', 'ix_admin_operation_logs_status', '(status)');
CALL genstudio_add_index_if_missing('admin_operation_logs', 'ix_admin_operation_logs_created_at', '(created_at)');

DROP PROCEDURE IF EXISTS genstudio_add_column_if_missing;
DROP PROCEDURE IF EXISTS genstudio_add_index_if_missing;
