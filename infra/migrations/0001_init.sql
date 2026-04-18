-- Migration 0001: Initial schema for carousel_autoposter
-- Run against the Supabase project: vkcsqnxzndhwjyoecwaa (carousel-bot)
-- Schema: carousel_autoposter

CREATE SCHEMA IF NOT EXISTS carousel_autoposter;

-- ── Table: flows ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS carousel_autoposter.flows (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_user_id    BIGINT NOT NULL,
    brand               TEXT NOT NULL CHECK (brand IN (
                            'dockplus','roberts','flamma','capecodder',
                            'granite','cheesebread','thiagaoai'
                        )),
    stage               TEXT NOT NULL,
    topic_chosen        JSONB,
    slide_count         INT CHECK (slide_count IN (1, 3, 5, 7, 10)),
    visual_style        TEXT,
    prompts             JSONB,
    image_urls          TEXT[],
    caption             TEXT,
    postforme_post_id   TEXT,
    instagram_permalink TEXT,
    cost_breakdown      JSONB,
    total_cost_usd      NUMERIC(10, 4),
    created_at          TIMESTAMPTZ DEFAULT now(),
    completed_at        TIMESTAMPTZ,
    status              TEXT DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS idx_flows_user   ON carousel_autoposter.flows (telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_flows_status ON carousel_autoposter.flows (status);
CREATE INDEX IF NOT EXISTS idx_flows_brand  ON carousel_autoposter.flows (brand);

-- ── Table: api_costs ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS carousel_autoposter.api_costs (
    id                BIGSERIAL PRIMARY KEY,
    flow_id           UUID REFERENCES carousel_autoposter.flows (id),
    service           TEXT NOT NULL,
    model             TEXT,
    tokens_input      INT,
    tokens_output     INT,
    images_generated  INT,
    cost_usd          NUMERIC(10, 6),
    latency_ms        INT,
    created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_api_costs_flow ON carousel_autoposter.api_costs (flow_id);

-- ── Table: brand_presets ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS carousel_autoposter.brand_presets (
    brand               TEXT PRIMARY KEY,
    palette             JSONB,          -- primary, secondary, accent colours
    voice               JSONB,          -- tone, forbidden_phrases, hashtags
    default_style       TEXT,           -- default visual style key
    system_prompt       TEXT,           -- custom system prompt for DeepSeek
    instagram_handle    TEXT,
    instagram_account_id TEXT,          -- postforme.dev account ID
    caption_template    TEXT,
    required_keywords   TEXT[]          -- for validator brand-keyword check
);

-- Seed minimal brand rows (update with real values before production)
INSERT INTO carousel_autoposter.brand_presets (brand, palette, voice, default_style, instagram_handle, caption_template, required_keywords)
VALUES
    ('thiagaoai',    '{"primary":"#1a1a2e","secondary":"#16213e","accent":"#0f3460"}', '{"tone":"tech-forward"}',    'cinematic',          '@thiagaoai',    '{caption} #AI #automation', '{}'),
    ('dockplus',     '{"primary":"#003366","secondary":"#ffffff","accent":"#0099cc"}', '{"tone":"professional"}',    'editorial_magazine', '@dockplusai',   '{caption} #DockPlus',       '{}'),
    ('roberts',      '{"primary":"#2d6a2d","secondary":"#f5f5dc","accent":"#8b4513"}', '{"tone":"earthy"}',         'ultra_realistic',   '@roberts_land', '{caption} #landscaping',    '{"landscaping","garden"}'),
    ('flamma',       '{"primary":"#ff4500","secondary":"#1a1a1a","accent":"#ffd700"}', '{"tone":"bold"}',           'cartoon',           '@flamma_brand', '{caption} #Flamma',         '{}'),
    ('capecodder',   '{"primary":"#4a90d9","secondary":"#ffffff","accent":"#c0a060"}', '{"tone":"coastal"}',        'informative_cards', '@capecodder',   '{caption} #CapeCod',        '{}'),
    ('granite',      '{"primary":"#808080","secondary":"#ffffff","accent":"#333333"}', '{"tone":"sturdy"}',         'ultra_realistic',   '@granite_co',   '{caption} #Granite',        '{}'),
    ('cheesebread',  '{"primary":"#f4a460","secondary":"#fff8dc","accent":"#8b0000"}', '{"tone":"warm,food"}',      'cartoon',           '@cheesebread',  '{caption} #food #bakery',   '{}')
ON CONFLICT (brand) DO NOTHING;
