-- Migration 0002: Set Post for Me social account IDs on brand_presets
-- Run against the Supabase project: lfxmyfiyibxqsvswnsoq
-- Schema: carousel_autoposter
--
-- instagram_account_id column stores the Post for Me social account ID (spc_…),
-- NOT the Meta/Instagram numeric user ID.

-- thiagaoai: @thiagaoai (Instagram user_id 17841400194457065)
--            Post for Me id: spc_yHK48v31utAg7B7hphu4
UPDATE carousel_autoposter.brand_presets
SET
    instagram_account_id = 'spc_yHK48v31utAg7B7hphu4',
    -- Improve caption template: use story hook + hashtags
    caption_template     = '{caption}

#AI #InteligenciaArtificial #MachineLearning #LLM #OpenAI #Anthropic #Tech #ThiagaoAI'
WHERE brand = 'thiagaoai';
