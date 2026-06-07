-- Public model visibility and admin-managed shared models.
-- Apply after 002_catalog_models.sql.

ALTER TABLE models ADD COLUMN is_public BOOL NOT NULL DEFAULT FALSE;
CREATE INDEX ix_models_is_public ON models (is_public);

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
