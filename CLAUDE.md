# CLAUDE.md — carousel-autoposter

> Agent context file. Read this before making any change to the codebase.

## What this project does

**carousel-autoposter** is a Telegram bot that automates the creation and publishing of Instagram carousels for multiple brands. A user sends `/novo <brand>` in Telegram; the system researches trending topics, generates cohesive image prompts, creates images, and publishes — with human approval at each step.

Brands: `dockplus`, `roberts`, `flamma`, `capecodder`, `granite`, `cheesebread`, `thiagaoai`.

## Architecture in one paragraph

Telegram webhooks land on **FastAPI**. FastAPI drives a **state machine** (Redis-backed, `transitions` lib) that tracks each active flow. Long-running work is offloaded to **Celery workers** (Redis broker). External APIs used in order: Perplexity (topic research) → DeepSeek V3 (prompt draft) → local validator (sentence-transformers, signal only) → Claude Sonnet 4.5 as **mandatory** design judge over every slide → fal.ai FLUX Pro Ultra (image generation) → Claude Sonnet 4.5 vision as **mandatory** typography auditor over every generated image → postforme.dev (Instagram publish). Supabase Postgres is the permanent store; Redis is ephemeral state only.

## Source of truth

[SDD.md](SDD.md) — System Design Document v1.0. All architectural decisions are there. When in doubt, check the SDD.

## Directory map

```
app/
  main.py              FastAPI entrypoint, /health, lifespan
  config.py            Pydantic Settings (reads .env)
  telegram/
    bot.py             Application setup, webhook handler
    keyboards.py       InlineKeyboardMarkup builders
    handlers/
      commands.py      /novo /status /cancelar /historico /custo /marca
      callbacks.py     callback_query routing by prefix
      messages.py      text message fallback
  state/
    transitions.py     FSM states and allowed transitions
    redis_store.py     async Redis wrapper (hashes, locks, rate limits)
    machine.py         StateMachine class (transitions lib + redis_store)
  integrations/
    perplexity.py      search_topics()
    deepseek.py        generate_prompts()
    claude.py          judge_and_polish_prompts() — mandatory design judge
    claude_vision.py   audit_typography() — vision QA on rendered images
    fal_client.py      generate_one(), generate_carousel()
    postforme.py       publish()
    supabase_client.py singleton + helpers
  validators/
    prompt_validator.py score_prompts() — local, zero-cost
  brands/
    registry.py        get_preset(brand) -> BrandPreset
    prompts/           per-brand system prompt markdown files
  tasks/
    celery_app.py      Celery application
    research.py        research_topics task
    prompts.py         generate_prompts task
    images.py          generate_images task
    publish.py         publish task
  utils/
    logging.py         structlog JSON + secret redaction
    costs.py           record_cost() helper
    security.py        allowlist check + FastAPI dependency
infra/
  Dockerfile           multi-stage python:3.12-slim
  docker-compose.yml   app + worker + redis + caddy
  caddy/Caddyfile      reverse proxy app:8000
  migrations/
    0001_init.sql      carousel_autoposter schema
tests/
  unit/
    test_state_machine.py
  integration/         (fixtures-based, external APIs mocked)
  fixtures/
```

## State machine states (SDD §2.3)

```
INIT → RESEARCHING → TOPIC_SELECTED → COUNT_SELECTED → STYLE_SELECTED
     → PROMPTS_READY → PROMPTS_APPROVED → GENERATING_IMAGES
     → IMAGES_APPROVED → PUBLISHING → COMPLETED

Side states: REGENERATING (from IMAGES_APPROVED), FAILED, CANCELLED (from any)
Terminal states: COMPLETED, FAILED, CANCELLED
```

## Redis key schema


| Key                            | TTL  | Purpose                  |
| ------------------------------ | ---- | ------------------------ |
| `flow:{flow_id}`               | 1h   | Full flow state hash     |
| `flow:user:{telegram_user_id}` | 1h   | Active flow_id for user  |
| `lock:flow:{flow_id}`          | 30s  | Distributed lock         |
| `rate:user:{telegram_user_id}` | 1h   | Rate limit counter       |
| `idempotency:{message_id}`     | 5min | Already-processed marker |


## Supabase

- Project URL: `https://qmlmbjaolmmwujfrxcpa.supabase.co`
- Schema: `carousel_autoposter`
- Tables: `flows`, `api_costs`, `brand_presets`
- Migrations live in `infra/migrations/`

## Environment variables (see .env.example)

Required: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `ALLOWED_TELEGRAM_USER_IDS` (CSV of int), `PERPLEXITY_API_KEY`, `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY`, `FAL_KEY`, `POSTFORME_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `REDIS_URL`, `LOG_LEVEL`.

## Hard constraints (never violate)

- **No API keys in code** — all via env vars / `Settings`.
- **English only** for code, docstrings, comments, log messages.
- **Type hints on 100% of public functions**.
- **Structured JSON logs** with `correlation_id` bound per flow via `structlog`.
- **Secret redaction** in logs (regex strips `sk-`*, `fal_`*, `Bearer *`, etc.).
- **No commits auto-generated** — user commits manually.
- Telegram webhook secret validated via `X-Telegram-Bot-Api-Secret-Token` header on every inbound request.
- Rate limit: 10 carousels/user/hour, 60 inline callbacks/user/minute.

## Common commands

```bash
make install      # uv sync
make lint         # ruff check + mypy
make test         # pytest tests/
make run-dev      # uvicorn app.main:app --reload
make worker-dev   # celery -A app.tasks.celery_app worker --loglevel=debug
make up           # docker compose -f infra/docker-compose.yml up -d --build
make down         # docker compose -f infra/docker-compose.yml down
make deploy       # SSH to hermes + pull + up
```

## External API notes

- **Perplexity**: model `sonar-pro`, `search_recency_filter: "week"`, respond JSON only.
- **DeepSeek V3**: model `deepseek-chat`, `response_format: {type: "json_object"}`, temp 0.7.
- **Claude Sonnet 4.5 (text)**: ALWAYS runs after DeepSeek as senior art director + judge. Reviews every slide for subject fidelity, typography legibility, contrast (WCAG-AA), brand alignment, FLUX rendering pitfalls, and cross-slide cohesion. Returns a polished `{story_arc, slides[]}` plus per-slide `judge_notes`.
- **Claude Sonnet 4.5 (vision)**: ALWAYS runs after FLUX. Inspects every generated image and returns a per-slide audit: `text_match`, `rendered_text_seen`, `montserrat_match` (0-10), `contrast`, `color_match`, `legibility`, `verdict` (pass/fail), `notes`. Stored in Redis as `typography_audit` and surfaced in the Telegram approval message so the user can regenerate failing slides.
- **fal.ai FLUX Pro Ultra**: `fal-ai/flux-pro/v1.1-ultra`, `aspect_ratio: "3:4"`, parallel via `asyncio.gather`. Each slide's prompt is built by `build_flux_prompt(slide, style)` which prepends a hard top-line directive with the EXACT `story_text`, hex color, weight, and a Montserrat visual fingerprint (geometric sans, tall x-height, circular bowls, double-story 'a', etc.) so FLUX has concrete features to chase instead of just a font name.
- **Post for Me (postforme.dev)**: `POST https://api.postforme.dev/v1/social-posts` with `caption`, `social_accounts` (Post For Me ids `spc_…`/`sa_…`), `media` — see `https://api.postforme.dev/docs`.

## Validator scoring (SDD §4.4)

Scores 1-10 per dimension, averaged:

1. **Similarity** — cosine similarity matrix; max pair sim < 0.7 → 10, < 0.85 → 5, else → 1.
2. **Length** — all prompts 80-200 words → 10, else → 6.
3. **Brand keywords** — all prompts contain required keyword → 10, else → 5.
4. **Role diversity** — `len(unique roles) >= min(3, N)` → 10, else → 5.

The validator score is now an informational signal passed to Claude as `validator_signal` — it no longer gates whether Claude runs. Claude ALWAYS runs over every slide; the score helps it focus on weak areas.

## Do / Don't for agents


| Do                                                            | Don't                                           |
| ------------------------------------------------------------- | ----------------------------------------------- |
| Read SDD.md for architectural decisions                       | Invent new state names not in §2.3              |
| Use `structlog.get_logger()` everywhere                       | Use `print()` or `logging.getLogger()` directly |
| Bind `flow_id` to logger at task start                        | Log raw API keys even in debug                  |
| Use `tenacity` for all external HTTP calls                    | Use `time.sleep()` for retry                    |
| Write type hints on every public function                     | Leave `Any` without a comment explaining why    |
| Use `settings` singleton from `app.config`                    | Hardcode URLs, ports, or token values           |
| Check `is_allowed(user_id)` before any action                 | Trust Telegram user_id without allowlist check  |
| Use `redis_store.acquire_lock(flow_id)` before mutating state | Mutate flow state without a lock                |


