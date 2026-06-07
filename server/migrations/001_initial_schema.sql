-- GenStudio initial MySQL schema.
-- Apply before production start when GENSTUDIO_AUTO_CREATE_TABLES=false.

CREATE TABLE users (
  id VARCHAR(64) NOT NULL,
  external_user_id VARCHAR(128) NOT NULL,
  email VARCHAR(255) NOT NULL,
  phone VARCHAR(64) NOT NULL,
  nickname VARCHAR(128) NOT NULL,
  avatar_url VARCHAR(512) NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE UNIQUE INDEX ix_users_external_user_id ON users (external_user_id);

CREATE TABLE api_keys (
  id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  base_url VARCHAR(512) NOT NULL,
  api_key_ciphertext TEXT NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_api_keys_user_id ON api_keys (user_id);

CREATE TABLE sessions (
  id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  token_hash VARCHAR(128) NOT NULL,
  expires_at DATETIME NOT NULL,
  created_at DATETIME NOT NULL,
  last_seen_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_sessions_expires_at ON sessions (expires_at);
CREATE UNIQUE INDEX ix_sessions_token_hash ON sessions (token_hash);
CREATE INDEX ix_sessions_user_id ON sessions (user_id);

CREATE TABLE user_credentials (
  id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  provider VARCHAR(32) NOT NULL,
  identifier VARCHAR(255) NOT NULL,
  email VARCHAR(255) NOT NULL,
  phone VARCHAR(64) NOT NULL,
  password_hash VARCHAR(512) NOT NULL,
  failed_attempts INTEGER NOT NULL,
  last_failed_at DATETIME,
  locked_until DATETIME,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT uq_user_credential_provider_identifier UNIQUE (provider, identifier),
  FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_user_credentials_user_id ON user_credentials (user_id);
CREATE INDEX ix_user_credentials_identifier ON user_credentials (identifier);

CREATE TABLE models (
  id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  api_key_id VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  vendor VARCHAR(128) NOT NULL,
  capability VARCHAR(32) NOT NULL,
  adapter VARCHAR(64) NOT NULL,
  description TEXT NOT NULL,
  primary_sub_model_id VARCHAR(64) NOT NULL,
  is_public BOOL NOT NULL DEFAULT FALSE,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
  FOREIGN KEY(api_key_id) REFERENCES api_keys (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_models_api_key_id ON models (api_key_id);
CREATE INDEX ix_models_is_public ON models (is_public);
CREATE INDEX ix_models_user_id ON models (user_id);

CREATE TABLE session_csrf_tokens (
  id VARCHAR(64) NOT NULL,
  session_id VARCHAR(64) NOT NULL,
  token_hash VARCHAR(128) NOT NULL,
  expires_at DATETIME NOT NULL,
  created_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY(session_id) REFERENCES sessions (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_session_csrf_tokens_expires_at ON session_csrf_tokens (expires_at);
CREATE UNIQUE INDEX ix_session_csrf_tokens_token_hash ON session_csrf_tokens (token_hash);
CREATE INDEX ix_session_csrf_tokens_session_id ON session_csrf_tokens (session_id);

CREATE TABLE sub_models (
  id VARCHAR(64) NOT NULL,
  model_group_id VARCHAR(64) NOT NULL,
  api_key_id VARCHAR(64) NOT NULL,
  model_name VARCHAR(255) NOT NULL,
  display_name VARCHAR(255) NOT NULL,
  capability VARCHAR(32) NOT NULL,
  adapter VARCHAR(64) NOT NULL,
  is_primary BOOL NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT uq_sub_model_group_name UNIQUE (model_group_id, model_name),
  FOREIGN KEY(model_group_id) REFERENCES models (id) ON DELETE CASCADE,
  FOREIGN KEY(api_key_id) REFERENCES api_keys (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_sub_models_api_key_id ON sub_models (api_key_id);
CREATE INDEX ix_sub_models_model_group_id ON sub_models (model_group_id);

CREATE TABLE call_logs (
  id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  model_group_id VARCHAR(64),
  sub_model_id VARCHAR(64),
  capability VARCHAR(32) NOT NULL,
  endpoint VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  duration_ms INTEGER NOT NULL,
  prompt_summary VARCHAR(512) NOT NULL,
  error_message VARCHAR(512) NOT NULL,
  raw_usage_json TEXT NOT NULL,
  created_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
  FOREIGN KEY(model_group_id) REFERENCES models (id) ON DELETE SET NULL,
  FOREIGN KEY(sub_model_id) REFERENCES sub_models (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_call_logs_created_at ON call_logs (created_at);
CREATE INDEX ix_call_logs_user_id ON call_logs (user_id);

CREATE TABLE conversations (
  id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  title VARCHAR(160) NOT NULL,
  capability VARCHAR(32) NOT NULL,
  model_group_id VARCHAR(64),
  sub_model_id VARCHAR(64),
  status VARCHAR(32) NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
  FOREIGN KEY(model_group_id) REFERENCES models (id) ON DELETE SET NULL,
  FOREIGN KEY(sub_model_id) REFERENCES sub_models (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_conversations_created_at ON conversations (created_at);
CREATE INDEX ix_conversations_updated_at ON conversations (updated_at);
CREATE INDEX ix_conversations_user_id ON conversations (user_id);

CREATE TABLE conversation_messages (
  id VARCHAR(64) NOT NULL,
  conversation_id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  model_group_id VARCHAR(64),
  sub_model_id VARCHAR(64),
  `role` VARCHAR(32) NOT NULL,
  capability VARCHAR(32) NOT NULL,
  content TEXT NOT NULL,
  status VARCHAR(32) NOT NULL,
  error_message VARCHAR(512) NOT NULL,
  can_retry BOOL NOT NULL,
  request_json TEXT NOT NULL,
  response_json TEXT NOT NULL,
  created_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE,
  FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
  FOREIGN KEY(model_group_id) REFERENCES models (id) ON DELETE SET NULL,
  FOREIGN KEY(sub_model_id) REFERENCES sub_models (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_conversation_messages_user_id ON conversation_messages (user_id);
CREATE INDEX ix_conversation_messages_created_at ON conversation_messages (created_at);
CREATE INDEX ix_conversation_messages_conversation_id ON conversation_messages (conversation_id);

CREATE TABLE generated_assets (
  id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  conversation_id VARCHAR(64) NOT NULL,
  message_id VARCHAR(64) NOT NULL,
  capability VARCHAR(32) NOT NULL,
  asset_type VARCHAR(32) NOT NULL,
  url TEXT NOT NULL,
  thumbnail_url TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
  FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE,
  FOREIGN KEY(message_id) REFERENCES conversation_messages (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_generated_assets_created_at ON generated_assets (created_at);
CREATE INDEX ix_generated_assets_message_id ON generated_assets (message_id);
CREATE INDEX ix_generated_assets_conversation_id ON generated_assets (conversation_id);
CREATE INDEX ix_generated_assets_user_id ON generated_assets (user_id);
