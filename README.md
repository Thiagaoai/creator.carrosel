# carousel-autoposter

Telegram bot that researches trending topics, generates cohesive Instagram carousel prompts, creates images with FLUX Pro Ultra, and publishes — with human approval at each step.

Brands: `dockplus`, `roberts`, `flamma`, `capecodder`, `granite`, `cheesebread`, `thiagaoai`.

> Full architecture and design decisions: [SDD.md](SDD.md)  
> Agent context and conventions: [CLAUDE.md](CLAUDE.md)

---

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Docker + Docker Compose (for local containers / production deploy)
- Redis 7 (included in docker-compose.yml)

---

## Local setup

```bash
# 1. Clone and enter
git clone <repo-url> carousel-autoposter
cd carousel-autoposter

# 2. Install dependencies
make install

# 3. Configure secrets
cp .env.example .env
# Edit .env — fill in all API keys and your Telegram user ID(s)

# 4. Run lint + tests (no API keys needed for unit tests)
make lint
make test
```

---

## Secrets Hygiene

- `.env.example` contains placeholders only. Never place real tokens in it.
- Keep real credentials only in `.env` on your machine/server.
- If a token was ever committed or shared, rotate it before using this project in production.
- `SUPABASE_SERVICE_KEY` must stay server-side only. Never expose it to browsers or public clients.

---

## Running locally (development)

You need two processes: the FastAPI app and a Celery worker.

```bash
# Terminal 1 — FastAPI
make run-dev
# → http://localhost:8000/live should return {"status":"ok"}
# → http://localhost:8000/ready should validate Redis/Supabase readiness

# Terminal 2 — Celery worker
make worker-dev
```

For the Telegram webhook to work locally you need a public URL (e.g. via [ngrok](https://ngrok.com)):

```bash
ngrok http 8000
# Set PUBLIC_WEBHOOK_URL=https://<ngrok-id>.ngrok.io in .env
# The bot will call setWebhook on startup automatically
```

---

## Running with Docker Compose (full stack)

```bash
make up          # builds + starts app, worker, redis, caddy
make logs        # follow logs
make down        # stop everything
```

---

## First deploy to hermes (Hostinger VPS)

```bash
# On hermes (Debian):
cd /opt
git clone <repo-url> carousel-autoposter
cd carousel-autoposter
cp .env.example .env
# Fill in .env with real secrets
make up

# Register Telegram webhook (runs automatically on startup, but can be forced):
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=https://hermes.dockplusai.com/webhook/telegram" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}"

# Verify
curl https://hermes.dockplusai.com/live
curl https://hermes.dockplusai.com/ready
```

### Subsequent deploys

```bash
make deploy
# Runs: ssh root@hermes.dockplusai.com "cd /opt/carousel-autoposter && git pull && docker compose up -d --build"
```

---

## Database migrations

Apply the SQL schema to your Supabase project:

```bash
# Set SUPABASE_DB_URL first (from Supabase dashboard → Settings → Database → Connection string)
export SUPABASE_DB_URL="postgresql://postgres:<password>@db.qmlmbjaolmmwujfrxcpa.supabase.co:5432/postgres"
make migrate
```

Or paste `infra/migrations/0001_init.sql` directly into the Supabase SQL editor.

---

## Make targets reference

| Target | Description |
|--------|-------------|
| `make install` | `uv sync` — install/update all dependencies |
| `make lint` | `ruff check` + `mypy` |
| `make test` | `pytest tests/ -v` |
| `make run-dev` | FastAPI hot-reload on :8000 |
| `make worker-dev` | Celery worker (debug, 2 concurrency) |
| `make up` | `docker compose up -d --build` |
| `make down` | `docker compose down` |
| `make logs` | `docker compose logs -f` |
| `make deploy` | SSH → pull → rebuild on hermes |
| `make migrate` | Apply SQL migrations via psql |

---

## Project structure

```
app/
  main.py              FastAPI entrypoint
  config.py            Pydantic Settings
  telegram/            Bot, keyboards, handlers
  state/               FSM + Redis persistence
  integrations/        Perplexity, DeepSeek, Claude, fal.ai, postforme, Supabase
  validators/          Local prompt quality scorer
  brands/              Brand presets + per-brand system prompts
  tasks/               Celery tasks
  utils/               Logging, costs, security
infra/
  Dockerfile           Multi-stage python:3.12-slim
  docker-compose.yml   app + worker + redis + caddy
  caddy/               Caddyfile
  migrations/          SQL
tests/
  unit/                pytest (no external deps)
  integration/         pytest with fixtures/mocks
```

---

## Environment variables

See [.env.example](.env.example) for the full list.

Required for the bot to start:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `ALLOWED_TELEGRAM_USER_IDS` (comma-separated)
- `REDIS_URL`
- `SUPABASE_URL` + `SUPABASE_SERVICE_KEY`
- `PERPLEXITY_API_KEY`, `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY`, `FAL_KEY`, `POSTFORME_API_KEY`

Operationally relevant:
- `SUPABASE_SCHEMA` (defaults to `carousel_autoposter`)
- `PUBLIC_WEBHOOK_URL`
- `REGISTER_WEBHOOK`
- `MAX_COST_PER_CAROUSEL_USD`

---

## Architecture

See [SDD.md](SDD.md) for the full System Design Document, including:
- State machine diagram (§2.3)
- Redis key schema (§3.2)
- API integration details (§4.x)
- Prompt validator algorithm (§4.4)
- Docker + deploy guide (§8)

---

## Release Checklist

- `.env.example` still contains placeholders only
- `make lint` passes
- `make test` passes
- `/live` returns `200`
- `/ready` returns `200`
- `/novo <marca>` produces 5 topical options
- Prompt approval, image regeneration, style change, preview and publish all work end-to-end
