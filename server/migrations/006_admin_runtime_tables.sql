-- Admin runtime tables used by role management, model health checks, and async task timelines.
-- Apply after 005_credit_system.sql. Safe to run more than once on MySQL.

DROP PROCEDURE IF EXISTS genstudio_add_index_if_missing;

DELIMITER //
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

CREATE TABLE IF NOT EXISTS admin_role_assignments (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CALL genstudio_add_index_if_missing('admin_role_assignments', 'ix_admin_role_assignments_user_id', '(user_id)');
CALL genstudio_add_index_if_missing('admin_role_assignments', 'ix_admin_role_assignments_role', '(role)');
CALL genstudio_add_index_if_missing('admin_role_assignments', 'ix_admin_role_assignments_assigned_by', '(assigned_by)');

CREATE TABLE IF NOT EXISTS model_health_checks (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CALL genstudio_add_index_if_missing('model_health_checks', 'ix_model_health_checks_model_group_id', '(model_group_id)');
CALL genstudio_add_index_if_missing('model_health_checks', 'ix_model_health_checks_created_at', '(created_at)');
CALL genstudio_add_index_if_missing('model_health_checks', 'ix_model_health_checks_sub_model_id', '(sub_model_id)');
CALL genstudio_add_index_if_missing('model_health_checks', 'ix_model_health_checks_admin_user_id', '(admin_user_id)');
CALL genstudio_add_index_if_missing('model_health_checks', 'ix_model_health_checks_status', '(status)');

CREATE TABLE IF NOT EXISTS task_events (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CALL genstudio_add_index_if_missing('task_events', 'ix_task_events_task_id', '(task_id)');
CALL genstudio_add_index_if_missing('task_events', 'ix_task_events_event_type', '(event_type)');
CALL genstudio_add_index_if_missing('task_events', 'ix_task_events_status', '(status)');
CALL genstudio_add_index_if_missing('task_events', 'ix_task_events_capability', '(capability)');
CALL genstudio_add_index_if_missing('task_events', 'ix_task_events_user_id', '(user_id)');
CALL genstudio_add_index_if_missing('task_events', 'ix_task_events_model_group_id', '(model_group_id)');
CALL genstudio_add_index_if_missing('task_events', 'ix_task_events_sub_model_id', '(sub_model_id)');
CALL genstudio_add_index_if_missing('task_events', 'ix_task_events_conversation_id', '(conversation_id)');
CALL genstudio_add_index_if_missing('task_events', 'ix_task_events_message_id', '(message_id)');
CALL genstudio_add_index_if_missing('task_events', 'ix_task_events_created_at', '(created_at)');

DROP PROCEDURE IF EXISTS genstudio_add_index_if_missing;
