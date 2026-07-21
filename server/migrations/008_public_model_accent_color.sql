-- Administrator-selected accent color for public model cards.
-- Apply after 007_prompt_scene_templates.sql.

ALTER TABLE models ADD COLUMN public_accent_color VARCHAR(7) NOT NULL DEFAULT '';
