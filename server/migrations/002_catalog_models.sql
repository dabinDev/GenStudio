-- GenStudio KKYi catalog metadata schema.
-- Apply after 001_initial_schema.sql.

CREATE TABLE IF NOT EXISTS catalog_models (
  id VARCHAR(64) NOT NULL,
  external_id VARCHAR(64) NOT NULL,
  display_name VARCHAR(255) NOT NULL,
  model_name VARCHAR(255) NOT NULL,
  model_type INTEGER NOT NULL,
  capability VARCHAR(32) NOT NULL,
  icon TEXT NOT NULL,
  description TEXT NOT NULL,
  input_hint TEXT NOT NULL,
  success_rate VARCHAR(32) NOT NULL,
  raw_json TEXT NOT NULL,
  source VARCHAR(64) NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE UNIQUE INDEX ix_catalog_models_external_id ON catalog_models (external_id);
CREATE INDEX ix_catalog_models_model_name ON catalog_models (model_name);
CREATE INDEX ix_catalog_models_model_type ON catalog_models (model_type);
CREATE INDEX ix_catalog_models_capability ON catalog_models (capability);

CREATE TABLE IF NOT EXISTS catalog_model_parameters (
  id VARCHAR(64) NOT NULL,
  catalog_model_id VARCHAR(64) NOT NULL,
  external_id VARCHAR(64) NOT NULL,
  display_name VARCHAR(255) NOT NULL,
  param_key VARCHAR(128) NOT NULL,
  description TEXT NOT NULL,
  widget_type INTEGER NOT NULL,
  is_required BOOL NOT NULL,
  default_value TEXT NOT NULL,
  function_tag VARCHAR(128) NOT NULL,
  max_count INTEGER,
  sort_order INTEGER NOT NULL,
  raw_json TEXT NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY(catalog_model_id) REFERENCES catalog_models (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_catalog_model_parameters_catalog_model_id ON catalog_model_parameters (catalog_model_id);
CREATE INDEX ix_catalog_model_parameters_param_key ON catalog_model_parameters (param_key);

CREATE TABLE IF NOT EXISTS catalog_model_parameter_options (
  id VARCHAR(64) NOT NULL,
  parameter_id VARCHAR(64) NOT NULL,
  external_id VARCHAR(64) NOT NULL,
  option_name VARCHAR(255) NOT NULL,
  option_value VARCHAR(255) NOT NULL,
  description TEXT NOT NULL,
  max_count INTEGER,
  is_default BOOL NOT NULL,
  sort_order INTEGER NOT NULL,
  price_factor VARCHAR(64) NOT NULL,
  raw_json TEXT NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY(parameter_id) REFERENCES catalog_model_parameters (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_catalog_model_parameter_options_parameter_id ON catalog_model_parameter_options (parameter_id);

CREATE TABLE IF NOT EXISTS catalog_model_channel_groups (
  id VARCHAR(64) NOT NULL,
  catalog_model_id VARCHAR(64) NOT NULL,
  external_id VARCHAR(64) NOT NULL,
  channel_id VARCHAR(64) NOT NULL,
  group_name VARCHAR(255) NOT NULL,
  billing_type INTEGER NOT NULL,
  input_token_price VARCHAR(64) NOT NULL,
  output_token_price VARCHAR(64) NOT NULL,
  base_price VARCHAR(64) NOT NULL,
  success_rate_24h VARCHAR(64) NOT NULL,
  avg_response_seconds_24h VARCHAR(64) NOT NULL,
  total_success_count VARCHAR(64) NOT NULL,
  total_fail_count VARCHAR(64) NOT NULL,
  sort_order INTEGER NOT NULL,
  option_prices_json TEXT NOT NULL,
  raw_json TEXT NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY(catalog_model_id) REFERENCES catalog_models (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_catalog_model_channel_groups_catalog_model_id ON catalog_model_channel_groups (catalog_model_id);
CREATE INDEX ix_catalog_model_channel_groups_channel_id ON catalog_model_channel_groups (channel_id);

ALTER TABLE models ADD COLUMN catalog_model_id VARCHAR(64) NULL;
CREATE INDEX ix_models_catalog_model_id ON models (catalog_model_id);
ALTER TABLE models ADD CONSTRAINT fk_models_catalog_model_id FOREIGN KEY (catalog_model_id) REFERENCES catalog_models (id) ON DELETE SET NULL;

ALTER TABLE sub_models ADD COLUMN catalog_model_id VARCHAR(64) NULL;
CREATE INDEX ix_sub_models_catalog_model_id ON sub_models (catalog_model_id);
ALTER TABLE sub_models ADD CONSTRAINT fk_sub_models_catalog_model_id FOREIGN KEY (catalog_model_id) REFERENCES catalog_models (id) ON DELETE SET NULL;
