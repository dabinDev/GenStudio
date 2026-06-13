-- Credit account, transaction, pricing, and settings tables.
-- Apply after 004_admin_console_fields.sql. Safe to run more than once on MySQL.

DROP PROCEDURE IF EXISTS genstudio_add_index_if_missing;
DROP PROCEDURE IF EXISTS genstudio_add_unique_index_if_missing;

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

CREATE PROCEDURE genstudio_add_unique_index_if_missing(
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
    SET @genstudio_sql = CONCAT('CREATE UNIQUE INDEX `', p_index_name, '` ON `', p_table_name, '` ', p_index_definition);
    PREPARE genstudio_stmt FROM @genstudio_sql;
    EXECUTE genstudio_stmt;
    DEALLOCATE PREPARE genstudio_stmt;
  END IF;
END//
DELIMITER ;

CREATE TABLE IF NOT EXISTS system_settings (
  `key` VARCHAR(128) NOT NULL,
  `value` TEXT NOT NULL,
  updated_by VARCHAR(64) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CALL genstudio_add_index_if_missing('system_settings', 'ix_system_settings_updated_by', '(updated_by)');

CREATE TABLE IF NOT EXISTS user_credit_accounts (
  id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  balance INTEGER NOT NULL DEFAULT 0,
  reserved_balance INTEGER NOT NULL DEFAULT 0,
  total_recharged INTEGER NOT NULL DEFAULT 0,
  total_spent INTEGER NOT NULL DEFAULT 0,
  total_refunded INTEGER NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT uq_user_credit_accounts_user_id UNIQUE (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CALL genstudio_add_unique_index_if_missing('user_credit_accounts', 'ix_user_credit_accounts_user_id', '(user_id)');

CREATE TABLE IF NOT EXISTS credit_transactions (
  id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  `type` VARCHAR(64) NOT NULL,
  amount INTEGER NOT NULL DEFAULT 0,
  balance_after INTEGER NOT NULL DEFAULT 0,
  reserved_after INTEGER NOT NULL DEFAULT 0,
  capability VARCHAR(32) NOT NULL DEFAULT '',
  model_group_id VARCHAR(64) NOT NULL DEFAULT '',
  sub_model_id VARCHAR(64) NOT NULL DEFAULT '',
  conversation_id VARCHAR(64) NOT NULL DEFAULT '',
  message_id VARCHAR(64) NOT NULL DEFAULT '',
  task_id VARCHAR(128) NOT NULL DEFAULT '',
  related_transaction_id VARCHAR(64) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL DEFAULT 'succeeded',
  reason TEXT NOT NULL,
  operator_user_id VARCHAR(64) NOT NULL DEFAULT '',
  metadata_json TEXT NOT NULL,
  created_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CALL genstudio_add_index_if_missing('credit_transactions', 'ix_credit_transactions_user_id', '(user_id)');
CALL genstudio_add_index_if_missing('credit_transactions', 'ix_credit_transactions_type', '(`type`)');
CALL genstudio_add_index_if_missing('credit_transactions', 'ix_credit_transactions_capability', '(capability)');
CALL genstudio_add_index_if_missing('credit_transactions', 'ix_credit_transactions_model_group_id', '(model_group_id)');
CALL genstudio_add_index_if_missing('credit_transactions', 'ix_credit_transactions_sub_model_id', '(sub_model_id)');
CALL genstudio_add_index_if_missing('credit_transactions', 'ix_credit_transactions_conversation_id', '(conversation_id)');
CALL genstudio_add_index_if_missing('credit_transactions', 'ix_credit_transactions_message_id', '(message_id)');
CALL genstudio_add_index_if_missing('credit_transactions', 'ix_credit_transactions_task_id', '(task_id)');
CALL genstudio_add_index_if_missing('credit_transactions', 'ix_credit_transactions_related_transaction_id', '(related_transaction_id)');
CALL genstudio_add_index_if_missing('credit_transactions', 'ix_credit_transactions_status', '(status)');
CALL genstudio_add_index_if_missing('credit_transactions', 'ix_credit_transactions_operator_user_id', '(operator_user_id)');
CALL genstudio_add_index_if_missing('credit_transactions', 'ix_credit_transactions_created_at', '(created_at)');

CREATE TABLE IF NOT EXISTS credit_pricing_rules (
  id VARCHAR(64) NOT NULL,
  scope VARCHAR(64) NOT NULL,
  capability VARCHAR(32) NOT NULL DEFAULT '',
  model_group_id VARCHAR(64) NOT NULL DEFAULT '',
  sub_model_id VARCHAR(64) NOT NULL DEFAULT '',
  price INTEGER NOT NULL DEFAULT 0,
  enabled BOOL NOT NULL DEFAULT TRUE,
  created_by VARCHAR(64) NOT NULL DEFAULT '',
  updated_by VARCHAR(64) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT uq_credit_pricing_scope UNIQUE (scope, capability, model_group_id, sub_model_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CALL genstudio_add_index_if_missing('credit_pricing_rules', 'ix_credit_pricing_rules_scope', '(scope)');
CALL genstudio_add_index_if_missing('credit_pricing_rules', 'ix_credit_pricing_rules_capability', '(capability)');
CALL genstudio_add_index_if_missing('credit_pricing_rules', 'ix_credit_pricing_rules_model_group_id', '(model_group_id)');
CALL genstudio_add_index_if_missing('credit_pricing_rules', 'ix_credit_pricing_rules_sub_model_id', '(sub_model_id)');
CALL genstudio_add_index_if_missing('credit_pricing_rules', 'ix_credit_pricing_rules_created_by', '(created_by)');
CALL genstudio_add_index_if_missing('credit_pricing_rules', 'ix_credit_pricing_rules_updated_by', '(updated_by)');

INSERT INTO credit_pricing_rules (
  id, scope, capability, model_group_id, sub_model_id, price, enabled, created_by, updated_by, created_at, updated_at
)
SELECT CONCAT('cprice_', REPLACE(UUID(), '-', '')), 'capability_default', 'text', '', '', 0, TRUE, '', '', NOW(), NOW()
WHERE NOT EXISTS (
  SELECT 1 FROM credit_pricing_rules
  WHERE scope = 'capability_default' AND capability = 'text' AND model_group_id = '' AND sub_model_id = ''
);

INSERT INTO credit_pricing_rules (
  id, scope, capability, model_group_id, sub_model_id, price, enabled, created_by, updated_by, created_at, updated_at
)
SELECT CONCAT('cprice_', REPLACE(UUID(), '-', '')), 'capability_default', 'image', '', '', 1, TRUE, '', '', NOW(), NOW()
WHERE NOT EXISTS (
  SELECT 1 FROM credit_pricing_rules
  WHERE scope = 'capability_default' AND capability = 'image' AND model_group_id = '' AND sub_model_id = ''
);

INSERT INTO credit_pricing_rules (
  id, scope, capability, model_group_id, sub_model_id, price, enabled, created_by, updated_by, created_at, updated_at
)
SELECT CONCAT('cprice_', REPLACE(UUID(), '-', '')), 'capability_default', 'video', '', '', 0, TRUE, '', '', NOW(), NOW()
WHERE NOT EXISTS (
  SELECT 1 FROM credit_pricing_rules
  WHERE scope = 'capability_default' AND capability = 'video' AND model_group_id = '' AND sub_model_id = ''
);

DROP PROCEDURE IF EXISTS genstudio_add_index_if_missing;
DROP PROCEDURE IF EXISTS genstudio_add_unique_index_if_missing;
