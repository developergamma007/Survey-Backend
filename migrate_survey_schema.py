"""One-time migration: create survey schema and move survey tables."""
from sqlalchemy import create_engine, text

from config import DATABASE_URL

MIGRATION_SQL = """
CREATE SCHEMA IF NOT EXISTS survey;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'survey_responses'
    ) THEN
        ALTER TABLE public.survey_responses SET SCHEMA survey;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'questions'
    ) THEN
        ALTER TABLE public.questions SET SCHEMA survey;
        ALTER TABLE survey.questions RENAME TO survey_questions;
    END IF;
END $$;

ALTER SEQUENCE IF EXISTS survey.questions_id_seq RENAME TO survey_questions_id_seq;
ALTER INDEX IF EXISTS survey.questions_pkey RENAME TO survey_questions_pkey;
ALTER INDEX IF EXISTS survey.ix_questions_id RENAME TO ix_survey_questions_id;

CREATE TABLE IF NOT EXISTS survey.survey_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    display_name VARCHAR(255),
    mobile VARCHAR(32),
    disabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

ALTER TABLE survey.survey_users ADD COLUMN IF NOT EXISTS display_name VARCHAR(255);
ALTER TABLE survey.survey_users ADD COLUMN IF NOT EXISTS mobile VARCHAR(32);

CREATE INDEX IF NOT EXISTS ix_survey_users_username ON survey.survey_users (username);

INSERT INTO survey.survey_users (username, hashed_password, disabled)
VALUES
    ('admin', '$2b$12$y5THdVd56K2gvIRMlwC5sOK.Am.HGbthUp0L1aPWnzcIP7c6HLT6u', FALSE),
    ('admin@iswot.io', '$2b$12$MX9SY/SK5YbA70fZXEy40O0HZaq6iYroJ7jakYWKlmSOi8dnifYPu', FALSE)
ON CONFLICT (username) DO NOTHING;

ALTER TABLE survey.survey_responses ADD COLUMN IF NOT EXISTS audio_url TEXT;
"""


def migrate() -> None:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text(MIGRATION_SQL))
    print("Survey schema migration complete.")


if __name__ == "__main__":
    migrate()
