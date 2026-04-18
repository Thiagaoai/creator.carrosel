# Brand System Prompts

Each file in this directory contains the custom DeepSeek system prompt for a specific brand.
The filename must match the brand slug exactly (e.g. `roberts.md`, `flamma.md`).

If a file is present, it overrides the `system_prompt` field stored in the Supabase
`brand_presets` table for that brand.

## Files to create

- `roberts.md` — Roberts Landscaping brand
- `flamma.md` — Flamma brand
- `capecodder.md` — Cape Codder brand
- `granite.md` — Granite brand
- `cheesebread.md` — Cheesebread brand
- `dockplus.md` — DockPlus brand
- `thiagaoai.md` — ThiagaoAI (staging brand, low-risk testing)

## Format

Plain markdown / plain text. The contents will be used verbatim as the `system` message
sent to DeepSeek V3. Include:
- Brand personality and tone
- Visual language and colour references
- Topics to avoid
- Hashtag suggestions
- Any brand-specific constraints
