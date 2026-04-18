.DEFAULT_GOAL := help
COMPOSE := docker compose -f infra/docker-compose.yml
HERMES_HOST ?= root@hermes.dockplusai.com
HERMES_DIR  ?= /opt/carousel-autoposter

.PHONY: help install lint test run-dev worker-dev up down logs deploy migrate

help:
	@echo "carousel-autoposter — available targets:"
	@echo ""
	@echo "  install     Install all dependencies with uv"
	@echo "  lint        Run ruff (style) + mypy (types)"
	@echo "  test        Run pytest"
	@echo "  run-dev     Start FastAPI with hot-reload"
	@echo "  worker-dev  Start Celery worker (debug loglevel)"
	@echo "  up          docker compose up -d --build"
	@echo "  down        docker compose down"
	@echo "  logs        Follow docker compose logs"
	@echo "  deploy      SSH to hermes, pull, rebuild, restart"
	@echo "  migrate     Apply Supabase SQL migrations via psql"

install:
	uv sync --extra dev

lint:
	.venv/bin/ruff check app tests
	.venv/bin/mypy app

test:
	.venv/bin/pytest tests/ -v

run-dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker-dev:
	uv run celery -A app.tasks.celery_app worker --loglevel=debug -c 2

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

deploy:
	ssh $(HERMES_HOST) "cd $(HERMES_DIR) && git pull && $(COMPOSE) up -d --build && curl -fsS http://127.0.0.1:8000/ready"

migrate:
	@echo "Applying migrations to Supabase..."
	@psql "$(SUPABASE_DB_URL)" -f infra/migrations/0001_init.sql
