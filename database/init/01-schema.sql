-- Database schema bootstrap executed by the Postgres container
-- Mirrors backend/app/schemas.py to make the DB usable before backend starts

-- Extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- ENUM types
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type WHERE typname = 'item_client_status'
    ) THEN
        CREATE TYPE item_client_status AS ENUM (
            'adding', 'queued', 'paused', 'completed', 'bookmark', 'error'
        );
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type WHERE typname = 'item_server_status'
    ) THEN
        CREATE TYPE item_server_status AS ENUM (
            'saved', 'extracted', 'summarised', 'embedded', 'classified'
        );
    END IF;
END$$;

-- Tables
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    url TEXT NOT NULL,
    canonical_url TEXT,
    title TEXT,
    source_site TEXT,
    publication_date TIMESTAMPTZ,
    favicon_url TEXT,
    content_markdown TEXT,
    content_text TEXT,
    content_token_count INTEGER,
    client_status item_client_status,
    server_status item_server_status NOT NULL DEFAULT 'saved',
    summary TEXT,
    expiry_score DOUBLE PRECISION,
    ts_embedding TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(content_text, ''))
    ) STORED,
    mistral_embedding VECTOR(1024),
    client_status_at TIMESTAMPTZ,
    server_status_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS item_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    content_text TEXT,
    content_token_count INTEGER,
    ts_embedding TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(content_text, ''))
    ) STORED,
    mistral_embedding VECTOR(1024),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (item_id, position)
);

CREATE TABLE IF NOT EXISTS llm_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    item_id UUID REFERENCES items(id) ON DELETE SET NULL,
    operation TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    prompt_cost NUMERIC,
    completion_cost NUMERIC,
    total_cost NUMERIC,
    currency TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    setting_type TEXT NOT NULL,
    setting_key TEXT NOT NULL,
    setting_value JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, setting_type, setting_key)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_items_user_client_status ON items(user_id, client_status);
CREATE INDEX IF NOT EXISTS idx_items_user_server_status ON items(user_id, server_status);
CREATE INDEX IF NOT EXISTS idx_items_ts_embedding ON items USING GIN (ts_embedding);
CREATE INDEX IF NOT EXISTS idx_items_mistral_embedding_ivfflat ON items USING ivfflat (mistral_embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_item_chunks_ts_embedding ON item_chunks USING GIN (ts_embedding);
CREATE INDEX IF NOT EXISTS idx_item_chunks_mistral_embedding_ivfflat ON item_chunks USING ivfflat (mistral_embedding vector_l2_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_llm_usage_logs_user_created_at ON llm_usage_logs(user_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_items_user_url_unique ON items(user_id, url);
CREATE UNIQUE INDEX IF NOT EXISTS idx_items_user_canonical_url ON items(user_id, canonical_url) WHERE canonical_url IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_user_settings_lookup ON user_settings(user_id, setting_type, setting_key);
CREATE INDEX IF NOT EXISTS idx_user_settings_type ON user_settings(user_id, setting_type);

