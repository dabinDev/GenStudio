CREATE TABLE IF NOT EXISTS prompt_scene_templates (
    id VARCHAR(64) NOT NULL,
    external_id VARCHAR(128) NOT NULL,
    category_id VARCHAR(128) NOT NULL DEFAULT '',
    document_title VARCHAR(255) NOT NULL DEFAULT '',
    document_url TEXT NOT NULL,
    section VARCHAR(255) NOT NULL DEFAULT '',
    category VARCHAR(255) NOT NULL DEFAULT '',
    subcategory VARCHAR(255) NOT NULL DEFAULT '',
    title VARCHAR(255) NOT NULL DEFAULT '',
    prompt_text TEXT NOT NULL,
    prompt_summary TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    source VARCHAR(128) NOT NULL DEFAULT '',
    original_no VARCHAR(64) NOT NULL DEFAULT '',
    image_url TEXT NOT NULL,
    model VARCHAR(128) NOT NULL DEFAULT '',
    likes INTEGER NOT NULL DEFAULT 0,
    views INTEGER NOT NULL DEFAULT 0,
    weight INTEGER NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    raw_json TEXT NOT NULL,
    use_count INTEGER NOT NULL DEFAULT 0,
    click_count INTEGER NOT NULL DEFAULT 0,
    impression_count INTEGER NOT NULL DEFAULT 0,
    imported_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_prompt_scene_template_external_id UNIQUE (external_id)
);

CREATE INDEX IF NOT EXISTS ix_prompt_scene_templates_external_id ON prompt_scene_templates (external_id);
CREATE INDEX IF NOT EXISTS ix_prompt_scene_templates_category_id ON prompt_scene_templates (category_id);
CREATE INDEX IF NOT EXISTS ix_prompt_scene_templates_section ON prompt_scene_templates (section);
CREATE INDEX IF NOT EXISTS ix_prompt_scene_templates_category ON prompt_scene_templates (category);
CREATE INDEX IF NOT EXISTS ix_prompt_scene_templates_subcategory ON prompt_scene_templates (subcategory);
CREATE INDEX IF NOT EXISTS ix_prompt_scene_templates_title ON prompt_scene_templates (title);
CREATE INDEX IF NOT EXISTS ix_prompt_scene_templates_source ON prompt_scene_templates (source);
CREATE INDEX IF NOT EXISTS ix_prompt_scene_templates_original_no ON prompt_scene_templates (original_no);
CREATE INDEX IF NOT EXISTS ix_prompt_scene_templates_model ON prompt_scene_templates (model);
CREATE INDEX IF NOT EXISTS ix_prompt_scene_templates_weight ON prompt_scene_templates (weight);
CREATE INDEX IF NOT EXISTS ix_prompt_scene_templates_enabled ON prompt_scene_templates (enabled);

CREATE TABLE IF NOT EXISTS prompt_scene_template_events (
    id VARCHAR(64) NOT NULL,
    template_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64),
    event_type VARCHAR(32) NOT NULL DEFAULT 'impression',
    image_url TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(template_id) REFERENCES prompt_scene_templates (id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_prompt_scene_template_events_template_id ON prompt_scene_template_events (template_id);
CREATE INDEX IF NOT EXISTS ix_prompt_scene_template_events_user_id ON prompt_scene_template_events (user_id);
CREATE INDEX IF NOT EXISTS ix_prompt_scene_template_events_event_type ON prompt_scene_template_events (event_type);
CREATE INDEX IF NOT EXISTS ix_prompt_scene_template_events_created_at ON prompt_scene_template_events (created_at);
