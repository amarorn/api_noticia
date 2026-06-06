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
- API REST em FastAPI que serve previsões, notícias, validação histórica e odds ao vivo.
- Frontend web em React + TypeScript + Tailwind CSS + Vite.
- Foco atual: **Copa do Mundo 2026** (48 seleções, 12 grupos, 72 jogos), com suporte contínuo ao Brasileirão.

---

## 2. Stack tecnológico

### Backend (Python 3.11+)
| Camada | Tecnologia |
|--------|-----------|
| API | FastAPI + Uvicorn |
| Configuração | Pydantic Settings (`.env`) |
| Datalake | Pandas + PyArrow (Parquet); GCS + BigQuery (opcional, `[gcp]`) |
| ML / Estatística | scikit-learn, Poisson customizado, Dixon-Coles |
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
│   ├── sofascore/          # Cliente curl_cffi, FEPT, stats, histórico
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
│   ├── ev_value.py         # Expected Value + Kelly
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
│   │   └── artifacts/      # predictor WC (pickle + manifest)
│   ├── sources.yaml        # Configuração declarativa de fontes RSS
│   ├── rounds/             # Rodadas planejadas (current.json, wc_2026.json)
│   └── wc/                 # Dados estáticos WC (squads, baselines, rankings, odds)
├── scripts/                # Utilitários (dev-api.sh, docker-dev.sh, cron_collect.sh)
├── docs/                   # Documentação em português
├── config.py               # Settings central (pydantic-settings)
├── pyproject.toml          # Dependências, scripts, ruff, pytest
├── .devcontainer/          # Dev Container local (recomendado para codar)
├── Dockerfile              # API produção + deps gcp/sofascore
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

### Dev Container (recomendado para dev local)
Abra o projeto com **Dev Containers** (Cursor/VS Code): `.devcontainer/devcontainer.json`.

- Lake em disco (`LAKE_PRIMARY=local`), sem custo GCP
- `post-create.sh` instala `.[dev,gcp,sofascore,analytics]` + `npm install` no frontend
- Portas encaminhadas: **8000** (API), **5173** (Vite)

```bash
# Dentro do container
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
cd frontend && npm run dev
daily-sync
pytest tests/ -q
```

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
| Docker compose | `docker-compose.yml`, `scripts/docker-dev.sh` |
