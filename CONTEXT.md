# CONTEXT.md — carousel-autoposter

Documento de contexto do projeto: o que foi definido, o que existe no repositório e onde aprofundar. Complementa o [PRD.md](PRD.md) (produto) e o [SDD.md](SDD.md) (arquitetura). Para agentes e desenvolvimento, ver também [CLAUDE.md](CLAUDE.md).

---

## 1. Visão geral

**carousel-autoposter** é um bot no **Telegram** que automatiza pesquisa de tendências, engenharia de prompts, geração de imagens e publicação de **carrosséis no Instagram** para várias marcas. O operador aprova cada etapa por botões inline; o backend orquestra o fluxo com **máquina de estados**, **Redis** (estado efêmero) e **Celery** (trabalho longo).

**Marcas suportadas** (preset): `dockplus`, `roberts`, `flamma`, `capecodder`, `granite`, `cheesebread`, `thiagaoai`.

**Problema que resolve:** reduzir tempo humano de ~30–45 min por carrossel para poucos minutos de atenção, com qualidade editorial e custo controlado, num fluxo **mobile-first** (só Telegram, sem web UI no MVP).

---

## 2. Decisões já tomadas (produto + engenharia)

- **Orquestração:** FastAPI + FSM em Redis (não n8n como núcleo) — retomada, callbacks, regeneração parcial e testes exigem código.
- **LLM principal de prompts:** DeepSeek V3 (JSON estruturado).
- **Pesquisa de tópicos:** Perplexity (`sonar-pro`, recência curta).
- **Fallback de qualidade:** Claude Sonnet 4.5 **apenas** quando o validador local reprova (média < 7/10), para economizar chamadas caras.
- **Validação local:** `sentence-transformers` + heurísticas em `app/validators/prompt_validator.py` (custo zero na maior parte dos fluxos).
- **Imagens:** fal.ai — FLUX Pro Ultra, proporção **4:5** (Instagram).
- **Publicação:** API **postforme.dev**.
- **Persistência:** Supabase Postgres (`carousel_autoposter`: fluxos, custos, presets de marca).
- **Infra alvo:** VPS **hermes** (Docker Compose + Caddy), healthcheck e logs estruturados.

Detalhes e diagramas: [SDD.md](SDD.md).

---

## 3. O que existe neste repositório (implementação)

### 3.1 Backend (FastAPI)


| Área        | Caminho                                                                           | Função                                                                                                        |
| ----------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Entrada     | `app/main.py`                                                                     | App FastAPI, `lifespan` (bot + webhook opcional), `/health`, POST webhook Telegram com dependência de segredo |
| Config      | `app/config.py`                                                                   | `pydantic-settings`, marcas válidas, rate limits, TTLs Redis, `REGISTER_WEBHOOK`                              |
| Telegram    | `app/telegram/bot.py`, `keyboards.py`, `handlers/*.py`                            | Bot, teclados inline, comandos e callbacks                                                                    |
| Estado      | `app/state/transitions.py`, `redis_store.py`, `machine.py`                        | Estados FSM, Redis, integração com `transitions`                                                              |
| Integrações | `app/integrations/*.py`                                                           | Perplexity, DeepSeek, Claude, fal, postforme, Supabase                                                        |
| Validação   | `app/validators/prompt_validator.py`                                              | Pontuação 1–10 por dimensões; gatilho para Claude                                                             |
| Marcas      | `app/brands/registry.py`, `app/brands/prompts/`                                   | Presets (Supabase + cache); prompts `.md` por marca quando existirem                                          |
| Jobs        | `app/tasks/celery_app.py`, `research.py`, `prompts.py`, `images.py`, `publish.py` | Workers assíncronos                                                                                           |
| Utilidades  | `app/utils/logging.py`, `costs.py`, `security.py`                                 | structlog JSON, custos, allowlist + header do webhook                                                         |


### 3.2 Infraestrutura

- `infra/Dockerfile` — imagem Python multi-stage.
- `infra/docker-compose.yml` — app, worker, Redis, Caddy.
- `infra/caddy/Caddyfile` — proxy reverso para a API.
- `infra/migrations/0001_init.sql` — schema inicial no Postgres.

### 3.3 Testes e tooling

- `tests/unit/test_state_machine.py` — testes unitários da FSM.
- `Makefile` — `install`, `lint` (ruff + mypy), `test`, `run-dev`, `worker-dev`, `up`/`down`/`logs`, `deploy`, `migrate`.

### 3.4 Documentação formal

- [PRD.md](PRD.md) — requisitos, user stories, métricas de sucesso, não-objetivos.
- [SDD.md](SDD.md) — stack, estados, Redis keys, contratos, segurança, custos.
- [CLAUDE.md](CLAUDE.md) — mapa de diretório, variáveis de ambiente, restrições para agentes.

---

## 4. Fluxo e estados (resumo)

Estados principais (ordem lógica): **INIT → RESEARCHING → TOPIC_SELECTED → COUNT_SELECTED → STYLE_SELECTED → PROMPTS_READY → PROMPTS_APPROVED → GENERATING_IMAGES → IMAGES_APPROVED → PUBLISHING → COMPLETED**, com ramificações **REGENERATING**, **FAILED**, **CANCELLED** e terminais **COMPLETED / FAILED / CANCELLED**.

Comando típico de início: `**/novo <marca>`** (detalhes de comandos adicionais: `commands.py` e PRD).

Redis guarda `flow:{id}`, mapeamento usuário→fluxo ativo, locks e idempotência (TTLs configuráveis em `Settings`).

---

## 5. Segredos e ambiente

- **Nunca** versionar chaves reais; usar apenas `.env` local (não commitado) e variáveis no servidor.
- Variáveis esperadas estão descritas em [CLAUDE.md](CLAUDE.md) e no template `.env.example` do projeto (ajustar placeholders se necessário).
- Webhook: header `**X-Telegram-Bot-Api-Secret-Token`** validado antes de processar o corpo.
- Allowlist: `**ALLOWED_TELEGRAM_USER_IDS**` (CSV de inteiros).

---

## 6. Comandos úteis (desenvolvimento)

```bash
make install      # uv sync --extra dev
make lint         # ruff + mypy
make test         # pytest
make run-dev      # FastAPI com reload
make worker-dev   # Celery worker debug
make up           # docker compose (infra)
```

Deploy documentado no Makefile: SSH em `hermes`, `git pull`, `docker compose up`.

---

## 7. Fora do escopo do MVP (lembrar)

Agendamento futuro, analytics pós-publicação, multi-tenant, Reels, legendas longas com CTA complexo, web UI — ver secção de não-objetivos no [PRD.md](PRD.md).

---

## 8. Onde ir depois

1. Garantir migração aplicada no Supabase (`make migrate` com `SUPABASE_DB_URL` configurado).
2. Preencher tabela `brand_presets` e arquivos em `app/brands/prompts/` por marca.
3. Subir **app + worker + redis** e validar webhook com `PUBLIC_WEBHOOK_URL` e `REGISTER_WEBHOOK`.
4. Expandir testes de integração (fixtures com APIs mockadas), conforme SDD.

---

*Última consolidação: alinhada ao código e documentos v1.0 (abril 2026). Para decisões normativas, prevalecem PRD + SDD; para mapa rápido do código, CLAUDE.md.*