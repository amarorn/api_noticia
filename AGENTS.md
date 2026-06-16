# AGENTS.md — api-noticia

> Arquivo de referência para agentes de codificação (AI coding agents).  
> Leia isto antes de editar qualquer arquivo do projeto.  
> Idioma principal do projeto: **português** (código, docstrings, commits, documentação).

---

## 1. Visão geral do projeto

**api-noticia** (também referido como *Bolão AI*) é um datalake de notícias esportivas com pipeline de coleta, transformação e previsão de resultados de bolão (formato **1 / X / 2**) para futebol. O sistema combina:

- Coleta de RSS de portais esportivos (Globo Esporte, ESPN BR, UOL, Lance!, Fogaonet, Gazeta Esportiva).
- Arquitetura medalhão (Bronze → Silver → Gold) em Parquet; **dev padrão: lake local** (`LAKE_PRIMARY=local`); publicação opcional em **GCS + BigQuery** (`sync-gcp`).
- Modelos estatísticos e de ML: Dixon-Coles, regressão logística, gradient boosting, ensemble colaborativo e motor tático **KXL** (Energy × Space × Time).
- API REST em FastAPI que serve previsões, notícias, validação histórica, odds ao vivo e **painel in-play Superbet** com recomendações de aporte/cash-out.
- Frontend web em React + TypeScript + Tailwind CSS + Vite, com tela **Ao Vivo** (`/ao-vivo/:eventId`) para orientação de apostas em tempo real.
- Foco atual: **Copa do Mundo 2026** (48 seleções, 12 grupos, 72 jogos), com suporte contínuo ao Brasileirão.
- **Integração ao vivo:** Superbet API (curl_cffi) → snapshot → modelo Poisson in-play → EV/Kelly → cash-out / aporte → frontend em cards interativos.

---

## 2. Stack tecnológico

### Backend (Python 3.11+)
| Camada | Tecnologia |
|--------|-----------|
| API | FastAPI + Uvicorn |
| Configuração | Pydantic Settings (`.env`) |
| Datalake | Pandas + PyArrow (Parquet); GCS + BigQuery (opcional, `[gcp]`) |
| ML / Estatística | scikit-learn, Poisson customizado, Dixon-Coles, Monte Carlo in-play, EV/Kelly/Cash-out |
| LLM (opcional) | transformers + Unsloth (Qwen2.5-0.5B-Instruct com PEFT/LoRA) |
| MLflow (opcional) | Tracking local SQLite (`mlflow.db`) |
| ETL / Pipelines | Prefect (opcional), ou funções Python puras |
| Scraping / HTTP | httpx, feedparser, BeautifulSoup4, curl_cffi (Sofascore) |
| Logging | structlog |
| Formatação / Lint | ruff |
| Testes | pytest + pytest-asyncio |

### Frontend
| Camada | Tecnologia |
|--------|-----------|
| Framework | React 18 + TypeScript 5.6 |
| Bundler | Vite 6 |
| Estilo | Tailwind CSS 3 + CSS custom properties (tema dark) |
| Animações | Framer Motion |
| Gráficos | ApexCharts (react-apexcharts) |
| Dados | TanStack Query (React Query) v5 |
| Roteamento | react-router-dom v7 |

### Infraestrutura
| Camada | Tecnologia |
|--------|-----------|
| Container | Docker (`python:3.11-slim`) + `docker-compose.yml` (perfis `local` / `cloud`) |
| Cloud (opcional) | GCS (`lake/…`) + BigQuery (`sports_news_lake`) — projeto `beanalytic-dev` |
| Deploy (API) | Fly.io (região `gru`, volume em `/data`) |
| CI/CD | GitHub Actions (`ci.yml`, `daily-collect.yml`) |
| Pre-commit | ruff + hooks padrão |

---

## 3. Estrutura de diretórios

```
api_noticia/
├── api/                    # FastAPI — rotas, auth, middleware, caches
│   ├── main.py             # App, lifespan, endpoints
│   ├── auth.py             # API key / Bearer token (middleware)
│   ├── data_pulse.py       # Headers de metadados do lake em cada resposta
│   ├── lake_cache.py       # Cache TTL de contagens do lake
│   └── wc_round_cache.py   # Cache persistente (memória + JSON) de previsões WC
├── ingest/                 # Coleta e persistência bronze
│   ├── cli.py              # collect-news (RSS → bronze)
│   ├── daily.py            # daily-sync (RSS → bronze → silver)
│   ├── sources.py          # Lógica de fetch RSS
│   ├── storage.py          # Escrita Parquet particionada (bronze)
│   ├── fixtures/           # Import de fixtures (Brasileirão, Copa do Mundo)
│   ├── sofascore/          # Cliente curl_cffi, FEPT, stats, histórico, amistosos
│   │   └── friendlies.py   # list_team_friendlies, merge FIFA+Sofascore, snapshot JSON
│   ├── superbet/           # Cliente ao vivo, parser, advice, benchmark, store, live_ticks
│   │   ├── client.py       # HTTP Superbet (curl_cffi) — fetch_event
│   │   ├── parser.py       # SuperbetEventSnapshot — h2h, totals, btts, combos
│   │   ├── advice.py       # run_live_advice → in-play + EV + cash-out + strategy
│   │   ├── benchmark.py    # h2h_overround, market_benchmark
│   │   ├── live_ticks.py   # append_live_tick → Parquet (bronze superbet/live_poll)
│   │   └── store.py        # save_event_snapshot
│   ├── fifa/               # APIs inside.fifa.com / api.fifa.com
│   │   ├── client.py       # HTTP FIFA
│   │   ├── match_ingest.py # detalhes de jogo, load_fifa_window_matches (cache)
│   │   ├── rankings_live.py# rankings ao vivo (cache rankings_live.json)
│   │   ├── teams.py        # nome canônico → código FIFA (BRA, EGY, …)
│   │   └── friendlies.py   # amistosos na janela FIFA (SeasonName Friendly)
│   ├── gcp/                # Medalhão GCP: sync, lake_store, lake_frames, medallion
│   │   ├── sync.py         # sync-gcp (local ou GCS → BQ)
│   │   ├── lake_store.py   # read/write snapshots GCS (cloud_lake_enabled)
│   │   ├── lake_frames.py  # normalização bronze/silver/gold para BQ
│   │   └── medallion.py    # mapa camada → tabela BQ / prefixo GCS
│   └── odds/               # The Odds API
├── pipelines/              # Transformações silver/gold + pipelines WC
│   ├── silver.py           # Bronze → Silver
│   ├── gold.py             # Silver + fixtures → Gold
│   ├── enrich_gold.py      # Enriquecimento assíncrono via API-Football
│   ├── cli.py              # run-pipeline (silver / gold / export / all)
│   ├── flows/daily.py      # Flow diário (Prefect opcional)
│   ├── wc_*.py             # ~30 módulos WC (stats, benchmark, value, KXL, etc.)
│   └── bolao_*.py          # Pipelines do Brasileirão
├── models/                 # Modelos preditivos e treinamento
│   ├── baseline.py         # Heurística baseline (posição, forma, sentimento)
│   ├── bolao_predictor.py  # LM local + blend com baseline
│   ├── poisson_wc.py       # Poisson ataque/defesa com meia-vida
│   ├── dixon_coles_wc.py   # Ajuste rho para jogos de baixo placar
│   ├── logistic_wc.py      # Regressão logística calibrada
│   ├── wc_collaborative.py # Blend Dixon-Coles + logística (otimizado por Brier)
│   ├── wc_draw_model.py    # Modelo dedicado para empate
│   ├── wc_predictor.py     # Pipeline completo WC (treino + inferência)
│   ├── wc_artifact.py      # Persistência pickle + manifest JSON do predictor
│   ├── wc_match_simulator.py # simulate_match: FIFA + Sofascore + ensemble WC
│   ├── ev_value.py         # Expected Value + Kelly
│   ├── wc_inplay.py        # Mercados in-play condicionados ao placar/minuto (Poisson + MC)
│   ├── wc_bet_advice.py    # Recomendações cash-out e aporte in-play vs mercado
│   ├── wc_bet_strategy.py  # Plano de apostas: posture, shields, watch list, rules
│   ├── wc_monte_carlo.py   # _sample_poisson_bivariada com correlação rho (Dixon-Coles)
│   ├── economics.py        # CES blend (Dixit-Stiglitz)
│   ├── corners_predictor.py# Previsão de escanteios
│   ├── dataset.py          # Export JSONL para treino
│   └── train_cli.py        # CLI de treinamento do LM
├── schemas/                # Contratos Pydantic
│   ├── models.py           # BronzeArticle, SilverArticle, BolaoFeature, GoldBolaoContext
│   ├── teams.py            # Normalização de times brasileiros
│   ├── national_teams.py   # Normalização de seleções
│   └── wc_kxl_dynamic.py   # Schema de entrada dinâmica KXL
├── frontend/               # Aplicação React
│   ├── src/
│   │   ├── domain/         # Entidades e interfaces de repositório
│   │   ├── application/    # Use cases, container de DI
│   │   ├── infrastructure/ # apiFetch, mappers, repositórios concretos
│   │   └── presentation/   # Páginas, componentes, hooks, tema
│   ├── package.json
│   └── vite.config.ts
├── tests/                  # Suite pytest (40+ arquivos)
├── data/
│   ├── lake/               # Datalake local (gitignored)
│   │   ├── bronze/
│   │   ├── silver/
│   │   ├── gold/
│   │   ├── fixtures/
│   │   ├── sofascore/      # match_stats.parquet (stats xG)
│   │   ├── fept/           # JSON por evento (não vai ao GCS por padrão)
│   │   ├── fifa/           # cache local FIFA (gitignored em dev)
│   │   │   ├── rankings_live.json
│   │   │   └── window_matches.json
│   │   ├── friendlies/     # snapshot por seleção/ano ({year}.json)
│   │   └── artifacts/      # predictor WC (pickle + manifest)
│   ├── sources.yaml        # Configuração declarativa de fontes RSS
│   ├── rounds/             # Rodadas planejadas (current.json, wc_2026.json)
│   └── wc/                 # Dados estáticos WC (squads, baselines, rankings, odds)
├── scripts/                # Utilitários (dev-api.sh, docker-dev.sh, cron_collect.sh)
├── docs/                   # Documentação em português
├── config.py               # Settings central (pydantic-settings)
├── pyproject.toml          # Dependências, scripts, ruff, pytest
├── .devcontainer/          # Dev Container (Cursor/VS Code — ambiente isolado local)
├── .vscode/extensions.json # recomenda extensão Dev Containers
├── Dockerfile              # API + deps gcp/sofascore
├── docker-compose.yml      # perfis local (lake disco) e cloud (GCS/BQ)
├── docker-compose.env.example
├── fly.toml                # Configuração Fly.io
├── credentials/            # Service account GCP (gitignored)
└── .env / .env.example     # Variáveis de ambiente
```

---

## 4. Comandos essenciais

### Setup inicial
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install -e ".[gcp]"       # opcional: sync-gcp, lake cloud
pip install -e ".[sofascore]" # opcional: ingest-sofascore
cp .env.example .env
# Dev recomendado: LAKE_PRIMARY=local, LAKE_SYNC_BQ_ON_WRITE=false
```

### Executar testes
```bash
pytest tests/ -q --tb=short
```
- Configuração em `pyproject.toml`: `asyncio_mode = "auto"`, `testpaths = ["tests"]`.
- Testes de API usam `TestClient` do FastAPI.
- Testes de modelos WC requerem fixtures importadas; o CI faz isso automaticamente.

### Lint e formatação
```bash
ruff check .          # lint
ruff check . --fix    # lint com auto-fix
ruff format .         # formatação
```
- Configuração em `pyproject.toml`: `line-length = 100`, `target-version = "py311"`.
- Pre-commit roda `ruff --fix`, `ruff-format`, `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-json`, `check-added-large-files`.

### Rodar API localmente
```bash
./scripts/dev-api.sh          # reload apenas em api/ (evita reinício ao gravar parquet)
./scripts/dev-api-stable.sh   # reload em api/, models/, ingest/, pipelines/ (amistosos/simulate)
# ou manualmente:
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Rodar frontend localmente
```bash
cd frontend && npm install && npm run dev
```
- O Vite proxy redireciona `/api` para `http://127.0.0.1:8000` (ver `vite.config.ts`).
- URL: http://localhost:5173

### Coleta de dados
```bash
daily-sync              # RSS → bronze → silver (2–3x/dia: 8h, 14h, 20h ou 11h, 17h, 23h UTC no CI)
collect-news            # só bronze
ingest-sofascore --history --all-teams   # stats xG (últimos jogos por seleção)
ingest-sofascore --all                   # fixtures WC (since-year 2018) + seleções
ingest-sofascore --backfill-dates        # preenche match_date via Sofascore API
```

### Importar fixtures
```bash
import-brasileirao --seasons 2024
import-world-cup --missing-only    # 1930–2022
```

### Pipelines
```bash
run-pipeline silver
run-pipeline gold --season 2024
run-pipeline export                # JSONL para treino
```

### Datalake local vs GCP

**Dev padrão (sem custo GCP):**
```env
LAKE_PRIMARY=local
LAKE_SYNC_BQ_ON_WRITE=false
```

**Publicar na nuvem (manual):**
```bash
sync-gcp --list-layers
sync-gcp --layer all --truncate
sync-gcp --layer silver_sofascore
```

**Produção / cloud-first:**
```env
LAKE_PRIMARY=cloud
LAKE_SYNC_BQ_ON_WRITE=true
GCS_BUCKET=beanalytic-dev-sports-news-lake
GCP_PROJECT=beanalytic-dev
GOOGLE_APPLICATION_CREDENTIALS=./credentials/beanalytic-dev.json
```

| Camada | Tabela BQ | Snapshot GCS |
|--------|-----------|--------------|
| bronze | `bronze_articles` | `lake/bronze/articles/articles.parquet` |
| silver | `silver_articles` | `lake/silver/articles/articles.parquet` |
| gold | `gold_bolao_context` | `lake/gold/bolao/articles.parquet` |
| silver_sofascore | `silver_sofascore_match_stats` | `lake/silver/sofascore/match_stats.parquet` |
| silver_fixtures | `silver_fixtures_results` | `lake/silver/fixtures/world_cup_fixtures.parquet` |
| gold_wc | `gold_wc_match_features` | `lake/gold/wc/match_features.parquet` |

Aliases CLI: `sofascore` → `silver_sofascore`, `fixtures` → `silver_fixtures`.

Leitores/escritores (`save_bronze`, `load_silver`, `upsert_match_stats`, `load_wc_fixtures`, etc.) respeitam `cloud_lake_enabled()` em `ingest/gcp/lake_store.py`. Com `LAKE_PRIMARY=local`, usam `data/lake/`; com `cloud`, leem/escrevem snapshots no GCS.

### Dev Container (ambiente isolado ao abrir o projeto)
A pasta fica na **raiz do repositório**: `.devcontainer/devcontainer.json` (não dentro de `.cursor/`).

Requisito: extensão **Dev Containers** (`anysphere.remote-containers` no Cursor).

1. Command Palette → `Dev Containers: Reopen in Container`
2. Na primeira vez: build da imagem + `post-create.sh` (pip, npm, pastas do lake)
3. Terminal e extensões rodam **dentro do container**; lake em `/workspace/data/lake` (`LAKE_PRIMARY=local`)

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
cd frontend && npm run dev
daily-sync
```

Para **Cursor Cloud Agents** (máquina remota), use `.cursor/environment.json` — feature separada.

### Docker Compose (API em container, sem IDE)
```bash
./scripts/docker-dev.sh up                    # API local (perfil local, padrão)
./scripts/docker-dev.sh run daily-sync
./scripts/docker-dev.sh cloud up              # API apontando para GCS/BQ
./scripts/docker-dev.sh cloud run sync-gcp --layer all
```

### Previsões
```bash
predict-round                      # Brasileirão (data/rounds/current.json)
predict-wc --round-file data/rounds/wc_2026.json
```

### Treinamento WC
```bash
train-wc                           # treina e gera artifact pickle
train-wc --force --mlflow          # força retrain e loga no MLflow
```

### MLflow
```bash
mlflow-ui                          # porta 5001 (evita conflito com AirPlay no macOS)
```

### Deploy Fly.io
```bash
./scripts/fly-deploy.sh
```

### Coleta de dados
```bash
daily-sync              # RSS → bronze → silver (2–3x/dia)
collect-news            # só bronze
ingest-sofascore --history --all-teams   # stats xG (últimos jogos por seleção)
ingest-sofascore --all                   # fixtures WC (since-year 2018) + seleções
ingest-sofascore --backfill-dates        # preenche match_date via Sofascore API
poll-superbet-live --event-ids 13127506  # captura ao vivo → bronze/superbet/live_poll/
```

---

## 5. Convenções de código

### Idioma
- **Português** é o idioma oficial para: docstrings, comentários, mensagens de erro, logs, nomes de scripts/CLIs, documentação e commits.
- **Inglês** é usado para: nomes de variáveis, funções, classes, arquivos Python e endpoints REST (exceções: termos de domínio como `bolao`, `rodada`, `mandante`, `visitante` podem aparecer em nomes quando o contexto é puramente brasileiro).

### Estilo Python
- Ruff com `line-length = 100` e `target-version = "py311"`.
- Type hints obrigatórios em APIs públicas (schemas Pydantic, funções de pipeline, modelos).
- `pathlib.Path` preferido a strings para caminhos de arquivo.
- `structlog` para logging estruturado (ISO timestamps, console renderer).
- Async/await usado em I/O da API (`asyncio.to_thread` para operações pesadas: carregar Parquet, treinar modelos).

### Organização de imports
- Imports agrupados: stdlib → terceiros → internos do projeto.
- Imports relativos evitados em módulos de topo; preferir absolutos (`from pipelines.silver import ...`).

### Nomenclatura de arquivos
- Módulos Python: `snake_case.py`.
- CLIs: nomes descritivos em português (`predict-round`, `train-wc`, `value-wc-odds`).
- Testes: `test_<modulo>.py`.

### Datalake
- **Local** (`LAKE_PRIMARY=local`): Parquet em `data/lake/` (gitignored).
- **Cloud** (`LAKE_PRIMARY=cloud`): snapshots consolidados no GCS; BQ opcional via `LAKE_SYNC_BQ_ON_WRITE`.
- Bronze local: `data/lake/bronze/source=<fonte>/year=…/month=…/day=…/articles_*.parquet`
- Silver local: `data/lake/silver/year=…/month=…/day=…/articles_*.parquet`
- Gold local: `data/lake/gold/year=…/month=…/context_*.parquet`
- Fixtures WC: `data/lake/fixtures/world_cup_<season>.parquet` (local) ou `silver_fixtures` no GCS
- Sofascore stats: `data/lake/sofascore/match_stats.parquet` (local) ou `silver_sofascore` no GCS
- Ingest em massa Sofascore usa `match_stats_batch_write()` para um único upload GCS por execução.

### Configuração
- Toda configuração sensível ou variável por ambiente vai para `config.py` (Pydantic Settings) e é sobrescrita via `.env`.
- Chaves relevantes do lake: `LAKE_ROOT`, `LAKE_PRIMARY` (`local` | `cloud`), `LAKE_SYNC_BQ_ON_WRITE`, `GCS_BUCKET`, `GCP_PROJECT`, `BQ_DATASET`, `GOOGLE_APPLICATION_CREDENTIALS`.
- Cache FIFA (dev offline): `fifa_rankings_cache_path` (`data/lake/fifa/rankings_live.json`), `fifa_window_cache_path` (`data/lake/fifa/window_matches.json`). Falha de rede não deve derrubar endpoints — usar cache antigo ou retornar só Sofascore.
- Nunca hardcode chaves de API ou caminhos absolutos em código de produção.
- Nunca commitar `.env` nem `credentials/`.

---

## 6. Estratégia de testes

- **Framework:** pytest + pytest-asyncio (`asyncio_mode = auto`).
- **Cobertura:** 40+ arquivos de teste cobrando API, autenticação, modelos (baseline, Poisson, Dixon-Coles, KXL, EV), pipelines (silver, gold, stats, fixtures), ingest (RSS, Sofascore, odds, parsers WC) e schemas.
- **Padrões:**
  - Testes unitários isolam lógica pura (ex: `test_dixon_coles.py` testa apenas o ajuste de rho).
  - Testes de integração usam `TestClient` do FastAPI e arquivos de fixture temporários.
  - Testes temporais verificam que não há *data leakage* (ex: `test_gold_temporal.py`).
- **CI (GitHub Actions):**
  - `lint` → `test-and-benchmark` (timeout 20 min) → `wc-model` (timeout 25 min).
  - Benchmarks rodam em CI após os testes: `benchmark-bolao-models --eval-season 2024` e `walkforward-wc-models --max-editions 6 --min-season 1990`.
  - Artefatos de benchmark são preservados por 14 dias.
- **Coleta diária:** Workflow `daily-collect.yml` roda `daily-sync` em cron (`11h, 17h, 23h UTC`) e faz upload do lake local como artefato (30 dias). Em dev local, `daily-sync` não toca GCP; use `sync-gcp` para publicar.

---

## 7. Segurança

### Autenticação da API
- Ativada quando `API_KEY` está definida no `.env`.
- Suporta múltiplas chaves separadas por vírgula.
- Extrai de: header `X-API-Key` ou `Authorization: Bearer <token>`.
- Comparação em tempo constante via `secrets.compare_digest`.
- Middleware (`ApiKeyMiddleware`) ignora paths públicos: `/health/live`, `/docs`, `/redoc`, `/openapi.json`.
- A OpenAPI schema é customizada para incluir os esquemas de segurança quando a chave está ativa.

### Considerações de desenvolvimento
- Nunca exponha `.env` ou `data/lake/` (ambos estão no `.gitignore`).
- A API em produção (Fly.io) usa `auto_stop_machines = off` e volume persistente em `/data`.
- O frontend lê `VITE_API_KEY` apenas em build; em dev, o proxy do Vite não expõe a chave para o browser.
- Respeite `robots.txt` das fontes RSS. Scraping de HTML completo é opcional (`--fetch-body`) e deve ser usado com moderação.

---

## 8. Arquitetura de modelos (resumo operacional)

### Brasileirão (bolão)
1. **Baseline** (`models/baseline.py`): heurística de posição, pontos, forma (V/E/D), H2H, sentimento e lesões.
2. **LM** (`models/bolao_predictor.py`): fine-tuned causal LM (Unsloth/Qwen2.5-0.5B-Instruct) com fallback automático para baseline se o checkpoint não existir.
3. **Blend**: `lm_weight=0.55` mistura probabilidades baseline com o palpite do LM.

### Copa do Mundo (WC)
1. **Feature engineering** (`pipelines/wc_stats.py`, `pipelines/wc_sofascore_features.py`): Elo iterativo, H2H, forma, squad features, notícias, rolling xG Sofascore (6 features), FIFA rankings, market features (odds). Dataset gold WC: `gold_wc_match_features`.
2. **Poisson / Dixon-Coles** (`models/poisson_wc.py`, `models/dixon_coles_wc.py`): força de ataque/defesa com decaimento temporal e correlação rho.
3. **Logistic Regression** (`models/logistic_wc.py`): calibrada com `CalibratedClassifierCV`.
4. **Collaborative Ensemble** (`models/wc_collaborative.py`): blend otimizado por Brier entre Dixon-Coles e logística.
5. **Draw Model** (`models/wc_draw_model.py`): classificador dedicado para empate; descontado em mata-mata.
6. **KXL Collision** (`pipelines/wc_kxl_collision.py`): motor tático que computa `Vcar` (vetor ataque) × `Vesc` (vetor defesa) com colisões setoriais, matriz letalidade×goleiro e moduladores dinâmicos (clima, árbitro, escalações, emoção).
7. **Blend final**: ensemble + KXL (`wc_kxl_blend_weight` padrão 0.20) + draw floor (`wc_draw_prob_floor` padrão 0.18).

### Persistência de artefatos
- `models/wc_artifact.py` serializa o `WcPredictor` treinado em pickle e um manifest JSON com fingerprints dos dados de entrada.  
- A API recarrega o artifact no startup (em background thread para não bloquear health checks).  
- Se o artifact estiver desatualizado ou ausente, retrain automático é disparado.

### In-Play / Ao Vivo (Superbet)
Fluxo para orientação de apostas em eventos Superbet ao vivo (`phase=friendly`, `source=friendly` no frontend).

| Camada | Responsabilidade |
|--------|------------------|
| `ingest/superbet/client.py` | HTTP Superbet via curl_cffi — `fetch_event(event_id)` |
| `ingest/superbet/parser.py` | `SuperbetEventSnapshot` — h2h, totals, BTTS, combos, next_goal, generosity, overround |
| `ingest/superbet/advice.py` | `run_live_advice()` — orquestra snapshot → modelo in-play → JSON de resposta |
| `ingest/superbet/benchmark.py` | `market_benchmark()`, `h2h_overround()` — comparação modelo vs casa |
| `ingest/superbet/live_ticks.py` | `append_live_tick()` — persiste snapshot + modelo + aporte em Parquet (`bronze/superbet/live_poll`) |
| `models/wc_inplay.py` | `simulate_inplay()` — Monte Carlo Poisson bivariada com rho (Dixon-Coles), condicionado ao placar e minuto |
| `models/wc_bet_advice.py` | `advise_aportes()` / `advise_cashout()` / `scan_all_market_edges()` — EV, Kelly, stake |
| `models/wc_bet_strategy.py` | `build_bet_strategy_report()` — posture, shields, watch_list, rules, correlation warnings |
| `models/ev_value.py` | `evaluate_outcome()` — EV = P × O - 1, Kelly fraction, fair odd |

**Fluxo de dados ao vivo:**
```
Superbet API → client.fetch_event() → parser.SuperbetEventSnapshot
                                              ↓
                                    models.wc_inplay.simulate_inplay()
                                              ↓
                                    models.wc_bet_advice.advise_aportes()
                                              ↓
                                    models.wc_bet_strategy.build_bet_strategy_report()
                                              ↓
                                    JSON → GET /worldcup/superbet/live/{id}/advice
                                              ↓
                                    frontend → LiveInPlayPage (/ao-vivo/:eventId)
```

**Endpoints API:**
- `GET /worldcup/superbet/live` — lista eventos Superbet ao vivo com IDs
- `GET /worldcup/superbet/live/{event_id}/advice` — resposta completa: inplay_summary, market_scan, strategy, cashout, aportes
- `GET /worldcup/superbet/events/{event_id}` — dados brutos do evento

**Frontend (`/ao-vivo`, `/ao-vivo/:eventId`):**
- `LiveInPlayPage.tsx` — Hero CTA, cards de mercado, barras de probabilidade, guia colapsável, monitor de cash-out
- Componentes: `LiveActionNowPanel`, `LiveMarketCards`, `LiveModelPanel`, `LivePlainGuide`, `LiveOpenBetMonitor`, `BetStrategyPanel`
- Layout: 2 colunas (mercados | modelo) em desktop, Hero CTA em destaque, seções colapsáveis

**Limitações conhecidas:**
- O modelo in-play usa λ (força de ataque) **fixo do pré-jogo** — não se adapta a eventos reais (gol, cartão, substituição, posse de bola). Melhorias planejadas: Bayesian update de λ, momentum por placar/minuto, integração de eventos Sofascore ao vivo. Ver `docs/analise-inplay-backend.md`.

### Amistosos internacionais (Sofascore + FIFA)
Fluxo fora da tabela oficial da Copa (`phase=round_16`, `source=friendly` no frontend).

| Camada | Responsabilidade |
|--------|------------------|
| `ingest/sofascore/friendlies.py` | Agenda via `team/{id}/events/next` + `events/last`; filtro ano UTC; `merge_friendlies()` |
| `ingest/fifa/friendlies.py` | Amistosos na janela FIFA (`SeasonName` com "Friendly"); filtro por `fifa_country_code` |
| `ingest/fifa/teams.py` | Mapa nome PT → código FIFA (ex.: Egito → `EGY`) |
| `models/wc_match_simulator.py` | `simulate_match()`: ensemble WC + rankings FIFA + enrich/stats/FEPT Sofascore |

**Fontes de dados (prioridade operacional):**
- **Agenda**: Sofascore é principal (inclui jogos futuros, ex. Brasil x Egito). FIFA complementa quando o jogo está na janela (~1055 jogos).
- **Escalações**: FIFA (`ingest_match_details`) se `fifa_match_id` ou jogo na janela; senão **FEPT Sofascore** (`build_fept_payload`) com `lineup_source: "sofascore"`.
- **Pré-jogo**: stats Sofascore retornam 404 antes do apito — não exibir como erro ao usuário.

**Endpoints API:**
- `GET /worldcup/friendlies?team=Brasil&year=2026` — merge Sofascore+FIFA; snapshot em `data/lake/friendlies/{year}.json`; falha FIFA → só Sofascore (sem 500).
- `POST /worldcup/simulate` — body `WcPredictRequest` aceita `match_date`, `fifa_match_id`, `sofascore_event_id`; resposta inclui `lineup_source`, escalações, rankings, `warnings`.
- `POST /worldcup/predict` — palpite ensemble/KXL; amistosos usam `phase=round_16` (evita gate `official_match_exists`).

**Frontend** (`/amistosos`, `/predict`):
- `FriendliesPage.tsx` — badges por fonte (`sources: ["sofascore"]`, `["fifa"]` ou ambos); link palpite com `simulate=1&eventId=&date=`.
- `PredictPage.tsx` — modo `source=friendly` + `simulate=1` chama `SimulateWcMatchUseCase` → painel com escalações (FIFA ou Sofascore) e probabilidades.
- Use cases: `GetWcFriendliesUseCase`, `SimulateWcMatchUseCase` em `application/container.ts`.

**Testes:** `tests/test_sofascore_friendlies.py`, `tests/test_fifa_friendlies.py`, `tests/test_fifa_window_cache.py`, `tests/test_wc_match_simulator.py`.

**Limitação conhecida:** nem todo amistoso Sofascore consta na janela FIFA (ex. Brasil x Egito 2026-06-06). Badge FIFA só aparece após cruzamento real na janela.

---

## 9. Convenções para agentes

- **Não assuma** que o leitor conhece o projeto. Documente o propósito de novas funções/classes em português.
- **Mantenha a arquitetura em camadas**: ingest → pipelines → models → api. Não crie dependências circulares (ex: `api/` não deve importar `ingest/` diretamente; use `pipelines/` ou `models/`).
- **Adicione testes** para qualquer lógica nova em `models/`, `pipelines/` ou `api/`.
- **Respeite o `.env`**: novas configurações devem ser adicionadas a `config.py` (com defaults sensatos) e documentadas em `.env.example`.
- **Pydantic para schemas**: qualquer contrato de dados público (request/response da API, linhas do lake) deve ter um schema Pydantic em `schemas/`.
- **Parquet para lake**: dados tabulares vão para Parquet (particionado localmente; snapshot consolidado no GCS). JSON/JSONL apenas para configs, FEPT, exemplos ou export de treino.
- **Lake local em dev**: prefira `LAKE_PRIMARY=local` para evitar custo BQ durante desenvolvimento. Integrações GCP devem funcionar com `sync-gcp` sem exigir `LAKE_PRIMARY=cloud` no dia a dia.
- **Normalização GCS/BQ**: ao escrever snapshots, use `normalize_*_df` / `normalize_match_stats_snapshot_df` em `lake_frames.py` e `stats_dataset.py` (timestamps em microssegundos, `match_date` sempre datetime).
- **CLI para automação**: operações recorrentes (coleta, transformação, treino) devem expor um entrypoint via `pyproject.toml` `[project.scripts]`.
- **Métricas de qualidade**: quando adicionar modelos, inclua métricas de Brier, log-loss e accuracy. Use MLflow opcionalmente (`pip install -e ".[ml]"`).
- **Frontend**: mantenha a arquitetura limada (domain → application → infrastructure → presentation). Novas páginas adicionam rota em `App.tsx`, use case em `application/`, repositório em `infrastructure/`, e componentes em `presentation/`.
- **Amistosos**: não bloquear UX quando FIFA estiver offline — `load_fifa_window_matches()` com cache + fallback; merge FIFA em `list_team_friendlies` dentro de `try/except`. Resolver `event_id`/`match_date` da URL no frontend (`resolvedSofascoreEventId`, `resolvedMatchDate`).
- **Simulate**: ao estender `simulate_match`, manter ordem FIFA → rankings → resolve contexto Sofascore → enrich → stats → FEPT fallback para escalações.
- **Dev Container**: `.devcontainer/Dockerfile` remove repo Yarn inválido antes do `apt-get` (evita `NO_PUBKEY` no build).

---

## 10. Links rápidos

| Recurso | Local |
|---------|-------|
| Docs completos | `docs/README.md` |
| Datalake e pipelines | `docs/datalake-e-pipelines.md` |
| Referência API | `docs/api-referencia.md` |
| Arquitetura | `docs/arquitetura.md` |
| Modelos preditivos | `docs/modelos-preditivos.md` |
| KXL Colisão | `docs/kxl-colisao.md` |
| Frontend | `docs/frontend.md` |
| Deploy Fly.io | `docs/deploy-fly.md` |
| Dev Container | `.devcontainer/devcontainer.json` |
| In-Play / Superbet | `docs/analise-inplay-backend.md`, `ingest/superbet/advice.py`, `models/wc_inplay.py` |
| Amistosos (ingest) | `ingest/sofascore/friendlies.py`, `ingest/fifa/friendlies.py` |
| Simulate WC | `models/wc_match_simulator.py`, `POST /worldcup/simulate` |
| Docker compose | `docker-compose.yml`, `scripts/docker-dev.sh` |
