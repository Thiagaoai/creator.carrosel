**PRD**

**Instagram Carousel Autoposter com Telegram Approval**

DockPlus Enterprise — Thiago do Carmo

Versão 1.0 — Abril 2026

*Product Requirements Document*

  


# **1. Sumário Executivo**

Este documento define os requisitos de produto de um pipeline automatizado de criação e publicação de carrosséis no Instagram, orquestrado por comandos no Telegram, integrado a Perplexity (pesquisa), DeepSeek (prompt engineering), Claude Sonnet 4.5 (validação de qualidade), [fal.ai](http://fal.ai) (geração de imagem) e [postforme.dev](http://postforme.dev) (publicação).

O objetivo é reduzir o tempo de produção de um carrossel de 45 minutos para menos de 8 minutos de atenção humana, mantendo qualidade editorial, storytelling consistente e economia agressiva de tokens.

## **1.1 Problema**

- Criação manual de carrosséis consome 30-60 minutos por post
- Conteúdo de redes sociais precisa ser publicado com frequência para manter engajamento
- Ferramentas de IA isoladas (ChatGPT, Midjourney, etc.) exigem múltiplos context-switches
- Prompts de imagem inconsistentes geram carrosséis visualmente fragmentados
- Não existe fluxo mobile-first aprovado para aprovar conteúdo em qualquer lugar

## **1.2 Solução**

Bot Telegram como interface única de comando e aprovação, com pipeline assíncrono de 5 estágios (pesquisa → escolha de tópico → prompts → imagens → publicação), cada um com ponto de aprovação humana via botões inline. Backend FastAPI com máquina de estados em Redis garante retomada segura mesmo se o usuário abandonar no meio.

## **1.3 Stakeholders**


| **Stakeholder**           | **Papel**              | **Interesse principal**                               |
| ------------------------- | ---------------------- | ----------------------------------------------------- |
| Thiago (user)             | Aprovador final        | Qualidade, velocidade, custo baixo por post           |
| Ecossistema DockPlus      | Clientes do output     | Consistência visual por marca (Roberts, Flamma, etc.) |
| Audiência final Instagram | Consumidor de conteúdo | Relevância, storytelling, qualidade visual            |


# **2. Objetivos e Não-Objetivos**

## **2.1 Objetivos (MVP)**

- Produzir carrossel Instagram completo (1, 3, 5, 7 ou 10 slides) a partir de 1 comando Telegram
- Pesquisar notícias atuais via Perplexity e sugerir 5 tópicos para aprovação
- Gerar prompts de imagem coesos (storytelling) com DeepSeek, validados por Claude Sonnet 4.5
- Suportar 8 estilos visuais: informativo, anime/manga, ultra-realístico, cinematográfico, aquarela moderna, anime 3D, cartoon, editorial magazine
- Gerar imagens via [fal.ai](http://fal.ai) (FLUX Pro Ultra ou FLUX Dev conforme tier)
- Publicar em [postforme.dev](http://postforme.dev) após aprovação final
- Retomar fluxo interrompido de onde parou (idempotência)
- Custo por carrossel de 5 slides abaixo de US$ 0,80

## **2.2 Não-Objetivos (MVP)**

- Agendamento de posts futuros (v1.1)
- Análise de performance pós-publicação (v1.2)
- Multi-usuário / multi-tenant (v2.0)
- Vídeos Reels (projeto separado reels-pipeline)
- Geração automática de legendas longas com CTA complexo (v1.1)
- Web UI — tudo é Telegram-first

## **2.3 Métricas de Sucesso**


| **Métrica**                          | **Alvo MVP** | **Como medir**                                                |
| ------------------------------------ | ------------ | ------------------------------------------------------------- |
| Tempo humano por carrossel           | < 8 min      | Timestamp início → aprovação final (Supabase)                 |
| Custo por carrossel 5 slides         | < US$ 0,80   | Soma [fal.ai](http://fal.ai) + DeepSeek + Claude + Perplexity |
| Taxa de aprovação primeira tentativa | > 75%        | Aprovado sem regenerar / total gerado                         |
| Uptime do bot                        | > 99%        | Uptime Kuma no hermes                                         |
| Carrosséis publicados por semana     | ≥ 5          | Count de posts com status=published                           |


# **3. User Stories**

## **3.1 Fluxo Principal — Carrossel from Scratch**

Como Thiago, quero enviar /novo no Telegram e receber 5 tópicos atuais, para escolher o mais relevante sem pesquisar manualmente.

Como Thiago, quero escolher entre 1, 3, 5, 7 ou 10 slides com botões inline, para adaptar o tamanho ao peso do assunto.

Como Thiago, quero escolher o estilo visual entre 8 opções predefinidas, para manter consistência de marca.

Como Thiago, quero revisar os prompts antes das imagens serem geradas, para evitar queimar tokens [fal.ai](http://fal.ai) em direção errada.

Como Thiago, quero receber as imagens no Telegram com botões de aprovar/regenerar/regenerar-só-slide-N, para corrigir sem recomeçar tudo.

Como Thiago, quero um botão final de publicar que dispara o [postforme.dev](http://postforme.dev), para ter o post no Instagram sem abrir o navegador.

## **3.2 Fluxo Secundário — Retomada**

Como Thiago, quero enviar /status e ver em qual estágio meu fluxo parou, para decidir se continuo ou descarto.

Como Thiago, quero enviar /cancelar e abortar o fluxo atual, para liberar o bot para outro assunto.

## **3.3 Fluxo de Marca**

Como Thiago, quero enviar /novo Roberts para que o bot aplique automaticamente paleta e estilo Roberts Landscape, para manter consistência entre os 6 negócios do ecossistema.

# **4. Requisitos Funcionais**

## **4.1 RF-01 — Comando /novo**

O bot deve aceitar /novo [marca_opcional] e iniciar o fluxo. Marcas suportadas: dockplus, roberts, flamma, capecodder, granite, cheesebread, thiagaoai. Sem marca = thiagaoai (default).

## **4.2 RF-02 — Pesquisa via Perplexity**

O bot deve chamar Perplexity API com prompt estruturado pedindo 5 tópicos atuais relevantes à marca, retornando título + 2 linhas de contexto por tópico. Resultados devem ter menos de 7 dias de idade preferencialmente.

## **4.3 RF-03 — Seleção de Tópico**

Apresentar os 5 tópicos como botões inline verticais. Usuário clica em 1. Bot persiste escolha no Redis com TTL de 1 hora.

## **4.4 RF-04 — Escolha de Quantidade**

Após tópico aprovado, bot pergunta quantidade de slides com botões: 1 | 3 | 5 | 7 | 10. Default recomendado: 5.

## **4.5 RF-05 — Escolha de Estilo Visual**

Apresentar 8 estilos como botões 2x4:

- Informativo Cards (tipografia forte, ícones, data viz)
- Anime/Manga (linhas nítidas, screen tones, paleta alta)
- Ultra-realístico (foto-realismo, luz natural, detalhe tátil)
- Cinematográfico (proporção 21:9 feel, luz dramática, grain)
- Aquarela Moderna (washes, bleed controlado, texturas)
- Anime 3D (Pixar/Arcane style, PBR, rim light)
- Cartoon (flat shapes, outlines, paleta primária saturada)
- Editorial Magazine (Vogue-like, composição fashion, moodboard)

## **4.6 RF-06 — Geração de Prompts Coesos**

DeepSeek V3 deve receber: tópico escolhido, quantidade de slides, estilo, marca, e retornar JSON estruturado com:

{ "story_arc": "...", "slides": [{ "slide": 1, "role": "hook", "prompt": "...", "caption": "..." }, ...] }

Regras obrigatórias do prompt engineer interno:

- Primeiro slide = hook visual impactante
- Último slide = CTA ou conclusão
- Slides intermediários desenvolvem narrativa — não podem ser intercambiáveis
- Proibido prompts idênticos ou quase-idênticos (cosine similarity > 0.85 triggera regeneração)
- Elementos visuais recorrentes (personagem, paleta, cenário) devem aparecer em pelo menos 60% dos slides

## **4.7 RF-07 — Validação Claude Sonnet 4.5**

Após DeepSeek gerar prompts, um validador automático score cada prompt em 4 dimensões (especificidade, coesão narrativa, viabilidade [fal.ai](http://fal.ai), risco de falha de marca). Se score médio < 7/10, Claude Sonnet 4.5 é acionado para reescrever apenas os prompts problemáticos. Economia típica: 60-70% das chamadas Claude.

## **4.8 RF-08 — Aprovação de Prompts**

Bot envia mensagem única com os N prompts numerados + botões: Aprovar tudo | Regenerar tudo | Ajustar slide N (abre sub-menu com campo de texto para feedback livre).

## **4.9 RF-09 — Geração de Imagens [fal.ai](http://fal.ai)**

Chamar [fal.ai](http://fal.ai) em paralelo (até 5 imagens simultâneas) com prompt + parâmetros por estilo. Modelo default: FLUX 1.1 Pro Ultra para tier premium, FLUX Dev para draft. Armazenar URLs no Supabase.

## **4.10 RF-10 — Aprovação Visual**

Bot envia carrossel no Telegram (media group de N fotos) + mensagem com botões: Publicar | Regenerar slide N | Trocar estilo | Descartar tudo.

## **4.11 RF-11 — Publicação [postforme.dev](http://postforme.dev)**

Chamar [postforme.dev](http://postforme.dev) API com array de URLs de imagem + caption gerada (storytelling condensado em 2200 chars, com 8-12 hashtags relevantes à marca). Retornar link de preview antes de publicar. Após publicado, enviar link final no Telegram.

## **4.12 RF-12 — Comandos Auxiliares**

- /status — mostra estágio atual do fluxo ativo
- /cancelar — aborta fluxo e limpa Redis
- /historico — últimos 10 carrosséis publicados com links
- /custo — custo acumulado do mês (todas APIs somadas)
- /marca <nome> — altera marca default

# **5. Requisitos Não-Funcionais**

## **5.1 Performance**

- Tempo de resposta de botão inline: < 2 segundos
- Pesquisa Perplexity: < 20 segundos
- Geração de 5 prompts DeepSeek: < 15 segundos
- Geração de 5 imagens [fal.ai](http://fal.ai) em paralelo: < 90 segundos
- Tempo total de ponta a ponta (sem esperas humanas): < 3 minutos

## **5.2 Custo**

Orçamento por carrossel de 5 slides:


| **Serviço**                            | **Chamadas** | **Custo unit.** | **Total**  |
| -------------------------------------- | ------------ | --------------- | ---------- |
| Perplexity (sonar-pro)                 | 1            | ~$0.015         | $0.015     |
| DeepSeek V3 (prompts)                  | 1            | ~$0.002         | $0.002     |
| Claude Sonnet 4.5 (fix)                | 0-1          | ~$0.02          | $0.02      |
| [fal.ai](http://fal.ai) FLUX Pro Ultra | 5            | $0.06           | $0.30      |
| [postforme.dev](http://postforme.dev)  | 1            | incluso         | $0.00      |
| **TOTAL**                              |              |                 | **~$0.34** |


*Margem de segurança confortável em relação ao alvo de US$ 0,80.*

## **5.3 Segurança**

- Todas as API keys em .env no VPS hermes, nunca commitadas
- Bot Telegram com allowlist de user_id (apenas Thiago)
- Webhooks Telegram com secret token
- Rate limit por usuário: 10 carrosséis/hora
- Logs estruturados em JSON com redaction de API keys

## **5.4 Confiabilidade**

- Idempotência: mesma mensagem Telegram recebida 2x não dispara 2 fluxos
- Retry com backoff exponencial em chamadas [fal.ai](http://fal.ai) e Perplexity
- Dead letter queue no Redis para jobs que falharam 3x
- Healthcheck em /health para Uptime Kuma

## **5.5 Observabilidade**

- Logs JSON estruturados com correlation_id por fluxo
- Métricas Prometheus: latência por estágio, custo acumulado, taxa de aprovação
- Alertas Telegram para o próprio admin chat quando erro crítico

# **6. Design de Interação no Telegram**

## **6.1 Fluxo Visual**

Sequência canônica de mensagens (exemplo de 5 slides):

Thiago → /novo roberts

Bot → 🔍 Buscando novidades em landscaping Cape Cod...

Bot → [5 botões verticais com tópicos]

Thiago → clica tópico 3

Bot → Quantos slides? [1] [3] [5] [7] [10]

Thiago → clica 5

Bot → Estilo? [8 botões 2x4]

Thiago → clica Cinematográfico

Bot → 📝 Gerando prompts coesos...

Bot → [prompts numerados + botões Aprovar/Regenerar/Ajustar]

Thiago → Aprovar tudo

Bot → 🎨 Gerando 5 imagens em paralelo...

Bot → [media group com 5 fotos + botões Publicar/Regenerar/Descartar]

Thiago → Publicar

Bot → ✅ Publicado: [https://instagram.com/p/](https://instagram.com/p/)...

## **6.2 Tratamento de Erros**

- [fal.ai](http://fal.ai) timeout → bot oferece regenerar com modelo Dev (mais rápido/barato)
- Perplexity sem resultados → bot pede tópico manual via texto livre
- [postforme.dev](http://postforme.dev) falha → bot salva URLs e caption no Supabase e avisa para publicar manual
- Redis down → bot responde com erro claro e sugere /cancelar

# **7. Dependências Externas**


| **Serviço**                           | **Uso**                    | **Criticidade** | **Fallback**                  |
| ------------------------------------- | -------------------------- | --------------- | ----------------------------- |
| Telegram Bot API                      | Interface única de usuário | Crítica         | Sem fallback                  |
| Perplexity API                        | Pesquisa de tópicos atuais | Alta            | Input manual                  |
| DeepSeek V3                           | Engenharia de prompts      | Alta            | Claude Haiku 4.5              |
| Claude Sonnet 4.5                     | Validação/correção prompts | Média           | Skip se score baixo           |
| [fal.ai](http://fal.ai)               | Geração de imagens         | Crítica         | Replicate (Flux)              |
| [postforme.dev](http://postforme.dev) | Publicação Instagram       | Crítica         | Download manual + post manual |
| Supabase                              | Persistência e histórico   | Alta            | SQLite local temp             |
| Redis (hermes)                        | State machine e fila       | Crítica         | Sem fallback                  |


# **8. Roadmap**

## **8.1 MVP (Semanas 1-3)**

- Setup infra no hermes (Docker, Redis, FastAPI, n8n existente)
- Bot Telegram básico com /novo e state machine
- Integração Perplexity + escolha de tópico
- Integração DeepSeek + validador local
- Integração [fal.ai](http://fal.ai) + aprovação de imagens
- Integração [postforme.dev](http://postforme.dev)
- Deploy e primeiro post de teste

## **8.2 v1.1 (Semana 4-5)**

- Agendamento de posts (cron no bot)
- Caption engineering avançado (hashtag research por marca)
- Templates salvos por marca
- /custo detalhado com breakdown

## **8.3 v1.2 (Semana 6+)**

- Análise de performance pós-publicação via Instagram Graph API
- A/B testing de estilos por marca
- Sugestão automática de melhor horário de post

## **8.4 v2.0 (Futuro)**

- Multi-tenant (outros clientes DockPlus)
- Web UI opcional para gestão
- Integração com reels-pipeline (mesma marca, outputs diferentes)

# **9. Riscos e Mitigações**


| **Risco**                             | **Impacto** | **Prob.** | **Mitigação**                                                 |
| ------------------------------------- | ----------- | --------- | ------------------------------------------------------------- |
| [fal.ai](http://fal.ai) preço sobe    | Alto        | Média     | Abstração de provider + fallback Replicate                    |
| Instagram muda API / postforme quebra | Crítico     | Média     | Monitorar changelog postforme, caminho manual como fallback   |
| Prompts geram imagens fora da marca   | Médio       | Alta      | Brand guidelines no system prompt + validação pós-imagem v1.1 |
| Custo por post estoura budget         | Médio       | Baixa     | Circuit breaker a $1.50/carrossel, alerta Telegram            |
| Telegram bot bloqueado                | Crítico     | Baixa     | Backup de token, domínio próprio no webhook                   |
| VPS hermes cai                        | Alto        | Baixa     | Snapshot Hostinger diário, fluxo salvo em Supabase            |


# **10. Critérios de Aceite**

MVP é considerado pronto quando todos os critérios abaixo estão verdes:

- /novo roberts resulta em carrossel publicado no Instagram em menos de 10 minutos totais (incluindo aprovações)
- 5 carrosséis seguidos geram 0 prompts ou imagens duplicadas
- Custo médio de 10 carrosséis fica abaixo de US$ 0,80 cada
- Bot responde a /status em menos de 2 segundos em 95% das chamadas
- Reiniciar o bot no meio de um fluxo preserva o estado (idempotência validada)
- Todas as 8 opções de estilo visual geram imagens visivelmente distintas
- Abandonar fluxo por 1h + /novo = fluxo anterior descartado sem erros

  


*Fim do PRD v1.0*

*Próximo documento: SDD (System Design Document)*