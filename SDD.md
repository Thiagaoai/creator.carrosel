**SDD**

**Instagram Carousel Autoposter**

*System Design Document*

DockPlus Enterprise — Thiago do Carmo

Versão 1.0 — Abril 2026

*Documento complementar ao PRD v1.0*

# **1. Stack Técnico**

## **1.1 Decisões Arquiteturais**

Três decisões centrais governam toda a arquitetura:

- FastAPI + Redis para state machine — n8n não dá conta de 5+ pontos de aprovação sequencial com retomada
- DeepSeek V3 como motor primário de prompt engineering — Claude Sonnet 4.5 só entra se validação automática falha
- Supabase como source of truth persistente — Redis é volátil, só guarda estado do fluxo ativo

## **1.2 Componentes**


| **Componente**    | **Tecnologia**                            | **Responsabilidade**                                             |
| ----------------- | ----------------------------------------- | ---------------------------------------------------------------- |
| Bot Telegram      | python-telegram-bot 21.x                  | Webhook receiver, roteamento de callbacks, envio de mensagens    |
| API Backend       | FastAPI 0.115 + uvicorn                   | Endpoints internos, orchestração, healthcheck                    |
| State Machine     | Redis 7 + transitions lib                 | Persistência de estado do fluxo, TTL, locks                      |
| Job Queue         | Celery + Redis broker                     | Tasks longas ([fal.ai](http://fal.ai), Perplexity) em background |
| Persistência      | Supabase Postgres                         | Histórico, custos, carrosséis publicados                         |
| LLM primário      | DeepSeek V3 API                           | Geração de prompts coesos em JSON estruturado                    |
| LLM validador     | Claude Sonnet 4.5 API                     | Reescrita de prompts quando score < 7/10                         |
| Pesquisa          | Perplexity sonar-pro                      | Busca de tópicos atuais com citações                             |
| Geração de imagem | [fal.ai](http://fal.ai) FLUX Pro Ultra    | Imagens 4:5 (1080x1350) Instagram-ready                          |
| Publicação        | [postforme.dev](http://postforme.dev) API | Upload + post no Instagram                                       |
| Infra             | VPS hermes (Hostinger)                    | Debian + Docker Compose, já em produção                          |
| Monitoramento     | Uptime Kuma + Loki                        | Healthcheck + logs estruturados                                  |


## **1.3 Por que não só n8n**

n8n é excelente para fluxos lineares com retries simples. Esse projeto tem características que n8n lida mal:

- Estado complexo por conversa (8+ variáveis persistentes por flow_id)
- 5 pontos de aprovação sequencial com callbacks Telegram assíncronos
- Regeneração parcial (só slide 3 de 5) que exige grafo não-linear
- Lógica de validação com score numérico e branching condicional
- Testes unitários e CI/CD

n8n pode continuar sendo usado para integrações simples (ex: notificar Discord quando um carrossel é publicado), mas não é o orquestrador principal.

# **2. Arquitetura**

## **2.1 Diagrama de Alto Nível**

                                 ┌──────────────────┐

                                 │   Telegram Bot   │

                                 │   (python-tg)    │

                                 └────────┬─────────┘

                                          │ webhook

                                          ▼

                                 ┌──────────────────┐

                                 │   FastAPI App    │

                                 │   (orchestrator) │

                                 └────────┬─────────┘

                                          │

        ┌─────────────────┬────────────────┼────────────────┬─────────────────┐

        ▼                 ▼                ▼                ▼                 ▼

  ┌──────────┐      ┌──────────┐    ┌───────────┐    ┌──────────┐      ┌───────────┐

  │  Redis   │      │  Celery  │    │ Supabase  │    │ Perplex. │      │  [fal.ai](http://fal.ai)   │

  │  State   │◄─────┤ Workers  ├───►│  Postgres │    │   API    │      │  FLUX     │

  └──────────┘      └────┬─────┘    └───────────┘    └──────────┘      └─────┬─────┘

                         │                                                   │

                         ▼                                                   ▼

                   ┌───────────┐                                      ┌───────────┐

                   │ DeepSeek  │                                      │ postforme │

                   │    V3     │                                      │   .dev    │

                   └─────┬─────┘                                      └───────────┘

                         │ (se score < 7)

                         ▼

                   ┌───────────┐

                   │  Claude   │

                   │ Sonnet 4.5│

                   └───────────┘

## **2.2 Fluxo de Dados**

Sequência canônica de um carrossel de 5 slides:

1. Telegram /novo roberts
  └─► FastAPI /webhook/telegram
       └─► StateMachine.start(user_id, brand='roberts')
           └─► Redis SET flow:{flow_id} = {stage: 'RESEARCH', brand, ...} TTL 1h
2. Celery task research_topics.delay(flow_id)
  └─► Perplexity API call
       └─► 5 tópicos salvos em Redis + Supabase
           └─► Bot envia 5 botões inline
3. User clica topic_3
  └─► callback_query → StateMachine.transition('TOPIC_SELECTED')
       └─► Bot envia botões [1|3|5|7|10]
4. User clica 5
  └─► StateMachine.transition('SLIDE_COUNT_SELECTED', count=5)
       └─► Bot envia 8 botões de estilo
5. User clica 'cinematografico'
  └─► StateMachine.transition('STYLE_SELECTED')
       └─► Celery task generate_prompts.delay(flow_id)
           └─► DeepSeek V3 call com system prompt + contexto
               └─► JSON com 5 prompts
                   └─► Validator (similarity, coesão, viabilidade)
                       ├─► Score >= 7: segue
                       └─► Score < 7: Claude Sonnet 4.5 reescreve prompts problemáticos
                   └─► Bot envia prompts + botões
6. User clica 'aprovar tudo'
  └─► Celery task generate_images.delay(flow_id)
       └─► 5 calls [fal.ai](http://fal.ai) em paralelo (asyncio.gather)
           └─► URLs salvas no Supabase
               └─► Bot envia media_group + botões
7. User clica 'publicar'
  └─► Celery task publish.delay(flow_id)
       └─► [postforme.dev](http://postforme.dev) API
           └─► Post_id salvo
               └─► StateMachine.transition('COMPLETED')
                   └─► Redis DEL flow:{flow_id}
                       └─► Bot envia link final

## **2.3 Máquina de Estados**

INIT ─► RESEARCHING ─► TOPIC_SELECTED ─► COUNT_SELECTED ─► STYLE_SELECTED

                                                                │

                                                                ▼

COMPLETED ◄── PUBLISHING ◄── IMAGES_APPROVED ◄── GENERATING_IMAGES

     ▲              │                │                    ▲

     │              │                │                    │

     │              ▼                ▼                    │

     │          FAILED           REGENERATING ────────────┘

     │                                                    ▲

     └──────── CANCELLED ◄── * (qualquer estado)           │

                                                           │

                        PROMPTS_READY ─► PROMPTS_APPROVED ─┘

                             ▲

                             │

                        STYLE_SELECTED

Transições permitidas definidas em [transitions.py](http://transitions.py). Estados terminais: COMPLETED, FAILED, CANCELLED (TTL 24h no Redis antes de limpar para permitir /historico).

# **3. Modelo de Dados**

## **3.1 Schema Supabase**

Database: qmlmbjaolmmwujfrxcpa. Schema: carousel_autoposter.

### **Tabela: flows**

CREATE TABLE carousel_autoposter.flows (

  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  telegram_user_id BIGINT NOT NULL,

  brand TEXT NOT NULL CHECK (brand IN (

    'dockplus','roberts','flamma','capecodder','granite','cheesebread','thiagaoai')),

  stage TEXT NOT NULL,

  topic_chosen JSONB,

  slide_count INT CHECK (slide_count IN (1,3,5,7,10)),

  visual_style TEXT,

  prompts JSONB,

  image_urls TEXT[],

  caption TEXT,

  postforme_post_id TEXT,

  instagram_permalink TEXT,

  cost_breakdown JSONB,

  total_cost_usd NUMERIC(10,4),

  created_at TIMESTAMPTZ DEFAULT now(),

  completed_at TIMESTAMPTZ,

  status TEXT DEFAULT 'active'

);

 

CREATE INDEX idx_flows_user ON carousel_autoposter.flows(telegram_user_id);

CREATE INDEX idx_flows_status ON carousel_autoposter.flows(status);

CREATE INDEX idx_flows_brand ON carousel_autoposter.flows(brand);

### **Tabela: api_costs**

CREATE TABLE carousel_autoposter.api_costs (

  id BIGSERIAL PRIMARY KEY,

  flow_id UUID REFERENCES carousel_autoposter.flows(id),

  service TEXT NOT NULL,

  model TEXT,

  tokens_input INT,

  tokens_output INT,

  images_generated INT,

  cost_usd NUMERIC(10,6),

  latency_ms INT,

  created_at TIMESTAMPTZ DEFAULT now()

);

### **Tabela: brand_presets**

CREATE TABLE carousel_autoposter.brand_presets (

  brand TEXT PRIMARY KEY,

  palette JSONB,       -- cores primárias, secundárias

  voice JSONB,         -- tom, frases proibidas, hashtags base

  default_style TEXT,  -- estilo visual default

  system_prompt TEXT,  -- system prompt customizado para DeepSeek

  instagram_handle TEXT,

  caption_template TEXT

);

## **3.2 Schema Redis**

flow:{flow_id}                    → Hash com estado completo (TTL 1h)

flow:user:{telegram_user_id}      → flow_id ativo do usuário (TTL 1h)

lock:flow:{flow_id}               → Lock distribuído (TTL 30s)

rate:user:{telegram_user_id}      → Counter rate limit (TTL 1h)

idempotency:{message_id}          → Marker de mensagem já processada (TTL 5min)

# **4. Integrações Externas**

## **4.1 Telegram Bot API**

Biblioteca: python-telegram-bot 21.x. Modo: webhook (não polling) via FastAPI endpoint.

### **Setup do webhook**

# Set webhook uma vez:

curl -X POST [https://api.telegram.org/bot{TOKEN}/setWebhook](https://api.telegram.org/bot{TOKEN}/setWebhook) \

  -d url=[https://hermes.dockplusai.com/webhook/telegram](https://hermes.dockplusai.com/webhook/telegram) \

  -d secret_token={WEBHOOK_SECRET}

### **Exemplo de handler**

# app/telegram/[handlers.py](http://handlers.py)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import ContextTypes

 

async def cmd_novo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_[user.id](http://user.id)

    if user_id not in settings.ALLOWED_USERS:

        await update.message.reply_text('Não autorizado.')

        return

    brand = ctx.args[0] if ctx.args else 'thiagaoai'

    flow_id = await state_machine.start(user_id, brand)

    await update.message.reply_text(f'🔍 Buscando novidades em {brand}...')

    celery_app.send_task('tasks.research_topics', args=[flow_id])

## **4.2 Perplexity API**

### **Request**

POST [https://api.perplexity.ai/chat/completions](https://api.perplexity.ai/chat/completions)

Authorization: Bearer {PERPLEXITY_API_KEY}

Content-Type: application/json

 

{

  "model": "sonar-pro",

  "messages": [

    {"role": "system", "content": "Você é um curador de notícias. Responda APENAS JSON."},

    {"role": "user", "content": "Liste 5 tópicos atuais (últimos 7 dias) sobre landscaping em Cape Cod MA. Formato: {topics: [{title, summary, source, date}]}"}

  ],

  "max_tokens": 1000,

  "temperature": 0.3,

  "search_recency_filter": "week"

}

## **4.3 DeepSeek V3**

### **System prompt para prompt engineering**

Você é um prompt engineer especializado em carrosséis Instagram virais.

 

ENTRADA: tópico, quantidade de slides (N), estilo visual, marca.

SAÍDA: JSON válido com story_arc (1 frase) e array slides com N objetos.

 

Cada slide deve ter: slide (int), role (hook|dev1|dev2|...|cta),

prompt (string em inglês, 80-150 palavras, com estilo visual obrigatório

e elementos recorrentes da marca), caption (pt-br, 40-80 palavras).

 

REGRAS DURAS:

- Slide 1 = hook visual impactante
- Slide N = CTA ou conclusão
- Elementos visuais recorrentes em >= 60% dos slides
- Nunca prompts idênticos ou quase-idênticos
- Sempre inclua aspect ratio 4:5 no prompt
- Incorpore paleta da marca (passada no context)

 

RESPONDA APENAS JSON. SEM MARKDOWN. SEM EXPLICAÇÕES.

### **Request**

POST [https://api.deepseek.com/chat/completions](https://api.deepseek.com/chat/completions)

Authorization: Bearer {DEEPSEEK_API_KEY}

 

{

  "model": "deepseek-chat",

  "messages": [

    {"role": "system", "content": ""},

    {"role": "user", "content": "<contexto estruturado com tópico/marca/estilo>"}

  ],

  "response_format": {"type": "json_object"},

  "temperature": 0.7,

  "max_tokens": 3000

}

## **4.4 Validador Local + Claude Fallback**

# app/validators/prompt_[validator.py](http://validator.py)

from sentence_transformers import SentenceTransformer

import numpy as np

 

model = SentenceTransformer('all-MiniLM-L6-v2')  # 80MB, roda local

 

def score_prompts(prompts: list[dict], brand_rules: dict) -> dict:

    texts = [p['prompt'] for p in prompts]

    embeddings = model.encode(texts)

    

    # 1. Similarity check (não pode ter prompts quase-idênticos)

    sim_matrix = np.inner(embeddings, embeddings)

    np.fill_diagonal(sim_matrix, 0)

    max_sim = sim_matrix.max()

    similarity_score = 10 if max_sim < 0.7 else (5 if max_sim < 0.85 else 1)

    

    # 2. Length check

    lengths = [len(t.split()) for t in texts]

    length_score = 10 if all(80 <= l <= 200 for l in lengths) else 6

    

    # 3. Brand keyword presence

    required = brand_rules.get('required_keywords', [])

    brand_score = 10 if all(

        any(kw.lower() in t.lower() for kw in required) for t in texts

    ) else 5

    

    # 4. Role diversity (hook/dev/cta devem estar preenchidos)

    roles = [p['role'] for p in prompts]

    role_score = 10 if len(set(roles)) >= min(3, len(prompts)) else 5

    

    avg = (similarity_score + length_score + brand_score + role_score) / 4

    return {

        'average': avg,

        'needs_claude_fix': avg < 7,

        'problematic_slides': [

            i for i, l in enumerate(lengths) if l < 80 or l > 200

        ]

    }

Se needs_claude_fix = True, só os problematic_slides vão pro Claude Sonnet 4.5 com prompt específico de reescrita. Economia típica de 60-70% das chamadas Claude.

## **4.5 [fal.ai](http://fal.ai)**

# app/integrations/fal_[client.py](http://client.py)

import fal_client

import asyncio

 

async def generate_one(prompt: str, style_params: dict) -> str:

    handler = await fal_client.submit_async(

        "fal-ai/flux-pro/v1.1-ultra",

        arguments={

            "prompt": prompt,

            "aspect_ratio": "4:5",

            "num_images": 1,

            "enable_safety_checker": True,

            **style_params  # seed, guidance_scale específicos do estilo

        }

    )

    result = await handler.get()

    return result['images'][0]['url']

 

async def generate_carousel(prompts: list[dict], style: str) -> list[str]:

    style_params = STYLE_PRESETS[style]

    tasks = [generate_one(p['prompt'], style_params) for p in prompts]

    return await asyncio.gather(*tasks)

## **4.6 [postforme.dev*](http://postforme.dev)*

Consultar documentação oficial em [https://postforme.dev/docs](https://postforme.dev/docs) para endpoint exato. Estrutura esperada:

POST [https://api.postforme.dev/v1/posts](https://api.postforme.dev/v1/posts)

Authorization: Bearer {POSTFORME_API_KEY}

 

{

  "platform": "instagram",

  "account_id": "{ig_account_id}",

  "type": "carousel",

  "media": [

    {"url": "[https://fal.ai/cdn/....jpg](https://fal.ai/cdn/....jpg)"},

    {"url": "[https://fal.ai/cdn/....jpg](https://fal.ai/cdn/....jpg)"}

  ],

  "caption": "",

  "schedule": "now"

}

# **5. Estrutura do Projeto**

carousel-autoposter/

├── app/

│   ├── [main.py](http://main.py)                    # FastAPI entrypoint

│   ├── [config.py](http://config.py)                  # Pydantic Settings

│   ├── telegram/

│   │   ├── [bot.py](http://bot.py)                 # Application setup

│   │   ├── handlers/

│   │   │   ├── [commands.py](http://commands.py)        # /novo /status /cancelar etc

│   │   │   ├── [callbacks.py](http://callbacks.py)       # callback_query handlers

│   │   │   └── [messages.py](http://messages.py)        # text messages

│   │   └── [keyboards.py](http://keyboards.py)           # InlineKeyboardMarkup builders

│   ├── state/

│   │   ├── [machine.py](http://machine.py)             # transitions-based FSM

│   │   ├── redis_[store.py](http://store.py)         # wrapper Redis

│   │   └── [transitions.py](http://transitions.py)         # definição de estados/transições

│   ├── integrations/

│   │   ├── [perplexity.py](http://perplexity.py)

│   │   ├── [deepseek.py](http://deepseek.py)

│   │   ├── [claude.py](http://claude.py)              # só para fallback

│   │   ├── fal_[client.py](http://client.py)

│   │   ├── [postforme.py](http://postforme.py)

│   │   └── supabase_[client.py](http://client.py)

│   ├── validators/

│   │   └── prompt_[validator.py](http://validator.py)

│   ├── tasks/

│   │   ├── celery_[app.py](http://app.py)

│   │   ├── [research.py](http://research.py)

│   │   ├── [prompts.py](http://prompts.py)

│   │   ├── [images.py](http://images.py)

│   │   └── [publish.py](http://publish.py)

│   ├── brands/

│   │   ├── [registry.py](http://registry.py)            # loader de brand_presets

│   │   └── prompts/               # system prompts por marca

│   │       ├── [roberts.md](http://roberts.md)

│   │       ├── [flamma.md](http://flamma.md)

│   │       └── ...

│   └── utils/

│       ├── [logging.py](http://logging.py)             # structlog config

│       ├── [costs.py](http://costs.py)               # tracker de custos

│       └── [security.py](http://security.py)            # auth allowlist

├── tests/

│   ├── unit/

│   ├── integration/

│   └── fixtures/

├── infra/

│   ├── docker-compose.yml

│   ├── Dockerfile

│   ├── caddy/Caddyfile            # reverse proxy

│   └── migrations/                # SQL Supabase

├── .env.example

├── pyproject.toml                 # Poetry ou uv

├── ruff.toml

├── [README.md](http://README.md)

└── Makefile

# **6. Algoritmo de Coesão de Prompts**

## **6.1 Story Arc Templates**

Para cada quantidade de slides, um story arc template guia o DeepSeek:


| **Slides** | **Arco narrativo**                                                  |
| ---------- | ------------------------------------------------------------------- |
| 1          | Single-punch: hook visual + caption carrega a história inteira      |
| 3          | Hook → Desenvolvimento → CTA. Clássico para tópicos diretos.        |
| 5          | Hook → Problema → Virada → Solução → CTA. Mais comum e recomendado. |
| 7          | Hook → Contexto → Problema → Insight → Solução → Prova → CTA        |
| 10         | Hook → 8 steps/pontos numerados → CTA. Para guias completos.        |


## **6.2 Elementos Recorrentes**

Para evitar carrosséis visualmente desconexos, o DeepSeek recebe uma instrução obrigatória de manter 3 elementos recorrentes:

- Paleta de cores (máximo 3 cores principais da marca)
- Elemento visual âncora (ex: mesmo personagem, mesmo objeto, mesmo cenário base)
- Tratamento de luz/atmosfera (ex: golden hour, estúdio branco, neon noturno)

Os 3 elementos são injetados no system prompt a partir da tabela brand_presets.

## **6.3 Detecção de Duplicatas**

Sentence-transformers (MiniLM-L6) roda local no VPS. Custo zero após download (80MB). Similaridade cosseno > 0.85 entre qualquer par de prompts = regeneração obrigatória do slide com maior similaridade média.

# **7. Segurança e Hardening**

## **7.1 Secrets**

Armazenamento em .env no VPS hermes, montado como read-only no container. Nunca commitado. Arquivo .env.example com placeholders fica no repo.

# .env.example

TELEGRAM_BOT_TOKEN=

TELEGRAM_WEBHOOK_SECRET=

ALLOWED_TELEGRAM_USER_IDS=123456789  # CSV

 

PERPLEXITY_API_KEY=

DEEPSEEK_API_KEY=

ANTHROPIC_API_KEY=

FAL_KEY=

POSTFORME_API_KEY=

 

SUPABASE_URL=[https://qmlmbjaolmmwujfrxcpa.supabase.co](https://qmlmbjaolmmwujfrxcpa.supabase.co)

SUPABASE_SERVICE_KEY=

 

REDIS_URL=redis://redis:6379/0

LOG_LEVEL=INFO

## **7.2 Allowlist**

Middleware FastAPI valida secret token Telegram no header X-Telegram-Bot-Api-Secret-Token. Handler de comando valida user_id contra ALLOWED_TELEGRAM_USER_IDS antes de qualquer ação.

## **7.3 Rate Limiting**

Redis-based sliding window. 10 carrosséis completos por usuário por hora. 60 callbacks inline por minuto.

## **7.4 Redação de Logs**

structlog com processor que detecta e redage qualquer string matching regex de API keys conhecidas (sk-, fal_, etc.). Logs nunca contêm tokens mesmo em DEBUG.

# **8. Deployment**

## **8.1 docker-compose.yml**

services:

  app:

    build: .

    restart: unless-stopped

    env_file: .env

    depends_on: [redis]

    labels:

      - caddy=[hermes.dockplusai.com](http://hermes.dockplusai.com)

      - caddy.reverse_proxy={{upstreams 8000}}

 

  worker:

    build: .

    command: celery -A app.tasks.celery_app worker --loglevel=info -c 4

    restart: unless-stopped

    env_file: .env

    depends_on: [redis]

 

  redis:

    image: redis:7-alpine

    restart: unless-stopped

    volumes:

      - redis_data:/data

    command: redis-server --appendonly yes --maxmemory 512mb

 

  caddy:

    image: lucaslorentz/caddy-docker-proxy:latest

    ports: ["80:80", "443:443"]

    restart: unless-stopped

    volumes:

      - /var/run/docker.sock:/var/run/docker.sock

      - caddy_data:/data

 

volumes:

  redis_data:

  caddy_data:

## **8.2 Deploy no hermes**

# No VPS hermes (Debian):

cd /opt

git clone  carousel-autoposter

cd carousel-autoposter

cp .env.example .env

# editar .env com secrets reais

docker compose up -d --build

 

# Set webhook Telegram uma vez:

curl -X POST [https://api.telegram.org/bot{TOKEN}/setWebhook](https://api.telegram.org/bot{TOKEN}/setWebhook) \

  -d url=[https://hermes.dockplusai.com/webhook/telegram](https://hermes.dockplusai.com/webhook/telegram) \

  -d secret_token=$(grep WEBHOOK_SECRET .env | cut -d= -f2)

 

# Verificar:

curl [https://hermes.dockplusai.com/health](https://hermes.dockplusai.com/health)

# → {"status":"ok"}

## **8.3 CI/CD**

GitHub Actions com 3 jobs: lint (ruff + mypy), test (pytest com fixtures Redis), deploy (SSH para hermes + docker compose pull && up).

# **9. Estratégia de Testes**

## **9.1 Unit**

- StateMachine: todas transições válidas e inválidas
- prompt_validator: matriz de similaridade, edge cases
- keyboards: cada InlineKeyboardMarkup com shape esperado
- redis_store: get/set/lock com testcontainers

## **9.2 Integration**

- Mock de cada API externa com responses fixtures
- Fluxo end-to-end /novo → publicação usando mocks
- Teste de retomada: kill FastAPI no meio do fluxo, restart, verificar estado

## **9.3 Manual Smoke**

- Canal Telegram de staging apenas com /novo → tópico mockado → imagem mockada
- Canal real Telegram primeiro post com marca thiagaoai (baixo risco)

# **10. Prompt de Boot para Cursor**

Copie e cole isto como primeira mensagem ao Cursor Agent (Composer) na raiz de um repo vazio chamado carousel-autoposter:

Vou construir o projeto carousel-autoposter descrito no SDD e PRD

anexados. Sua missão hoje:

 

1. Criar estrutura de diretórios conforme seção 5 do SDD.
2. Inicializar projeto Python com uv (pyproject.toml).
3. Dependências: fastapi, uvicorn, python-telegram-bot, celery,
  redis, transitions, httpx, anthropic, fal-client, supabase,
   structlog, pydantic-settings, sentence-transformers, pytest,
   pytest-asyncio, testcontainers, ruff, mypy.
4. Criar .env.example conforme seção 7.1.
5. Criar docker-compose.yml conforme seção 8.1.
6. Criar Dockerfile multi-stage (builder + runtime) com Python 3.12-slim.
7. Criar Caddyfile com reverse proxy para app:8000.
8. Implementar app/[config.py](http://config.py) com Pydantic Settings lendo .env.
9. Implementar app/state/[machine.py](http://machine.py) com transitions usando estados
  da seção 2.3 do SDD.
10. Implementar app/telegram/[bot.py](http://bot.py) com webhook handler em FastAPI.
11. Implementar app/telegram/handlers/[commands.py](http://commands.py) com /novo, /status,
  /cancelar, /historico, /custo, /marca.
12. Implementar app/telegram/[keyboards.py](http://keyboards.py) com builders para os 3 menus
  inline (tópicos, quantidade, estilo).
13. Implementar app/integrations/ com um client por serviço externo,
  todos com retry exponencial via tenacity.
14. Implementar app/validators/prompt_[validator.py](http://validator.py) conforme seção 4.4.
15. Criar tests/unit/test_state_[machine.py](http://machine.py) cobrindo todas as transições.
16. Criar Makefile com targets: install, lint, test, run-dev, deploy.
17. Criar [README.md](http://README.md) com setup local e guia de primeiro deploy.

Restrições duras:

- Todo código em inglês, toda docstring em inglês.
- Commits atômicos conforme cada item acima.
- Nenhuma API key no código — tudo via env.
- Type hints em 100% das funções públicas.
- Logs estruturados JSON com correlation_id por flow.

 

Comece criando a estrutura de diretórios e o pyproject.toml.

Pare e peça confirmação antes de passar para o próximo bloco de 5 itens.

# **11. Recomendação de IDE — Sem Drama**

## **11.1 Análise Objetiva**

Essa seção responde diretamente a pergunta "qual IDE devo escolher". Resposta sem favoritismo abaixo.


| **Critério**                      | **Cursor**    | **Claude Code**            | **Codex CLI**           |
| --------------------------------- | ------------- | -------------------------- | ----------------------- |
| Iteração rápida arquivo-a-arquivo | Excelente     | Bom                        | Médio                   |
| Refactor multi-arquivo            | Bom           | Excelente                  | Ruim                    |
| Tab completion em Python          | Excelente     | Não aplicável (CLI)        | Não aplicável (CLI)     |
| Raciocínio arquitetural profundo  | Bom           | Excelente                  | Médio                   |
| Setup inicial e boilerplate       | Bom           | Bom                        | Excelente               |
| Debug interativo com breakpoints  | Excelente     | Requer terminal            | Requer terminal         |
| Custo/mês                         | $20           | Incluído em Claude Pro/Max | Incluído em OpenAI Plus |
| **Ajuste fino para esse projeto** | **Muito bom** | **Bom**                    | **Auxiliar**            |


## **11.2 Recomendação Final**

Para este projeto específico — backend Python de automação, 1 pessoa, sem UI complexa, peso grande em integrações externas e testes — a ordem é:

- Cursor como principal. Iteração rápida, Tab em Python é superior, Composer Agent itera bem em múltiplos arquivos quando necessário.
- Claude Code para 2 momentos específicos: (a) no início, para gerar a estrutura inteira do projeto a partir deste SDD em um prompt, aproveitando raciocínio profundo; (b) quando aparecer um refactor grande (ex: trocar Celery por Dramatiq se performance exigir).
- Codex CLI fica como coadjuvante. Útil para gerar um arquivo boilerplate rápido sem abrir a IDE, mas não seria a ferramenta principal.

Observações sem puxar sardinha:

- Se você já paga Claude Max, Claude Code é gratuito — então usar ele como principal também é válido, especialmente se você prefere trabalhar em terminal.
- Cursor é escolha padrão da indústria para backend Python em 2026, o suporte a LSP e refatoração semântica é maduro.
- Não compra todos os três. Trio só faz sentido em monorepos complexos com frontend+backend+mobile simultâneos — não é o caso aqui.

## **11.3 Conclusão Direta**

**Vá com Cursor. Gaste os $20 do mês. Abra o Claude Code apenas se aparecer uma decisão arquitetural em que Cursor esteja girando em círculos — nesses casos específicos, o raciocínio mais profundo do Claude Code economiza tempo. Não trate IDEs como religião; trate como ferramentas.**

# **12. Próximos Passos Imediatos**

- Criar repo privado no GitHub: carousel-autoposter
- No hermes: criar subdomínio [hermes.dockplusai.com](http://hermes.dockplusai.com) com Caddy
- Gerar BotFather novo token para @carouselautoposter_bot
- Obter API keys: Perplexity, DeepSeek, [fal.ai](http://fal.ai), [postforme.dev](http://postforme.dev)
- Criar schema carousel_autoposter no Supabase existente
- Copiar o Prompt de Boot da seção 10 para Cursor Agent
- Primeiro deploy em staging (marca thiagaoai, canal Telegram privado)
- Iterar até 5 carrosséis seguidos sem intervenção manual além dos pontos de aprovação
- Ir para produção com marcas reais (Roberts, Flamma)

*Fim do SDD v1.0*

*Documento mantido pelo Thiago do Carmo — DockPlus Enterprise*