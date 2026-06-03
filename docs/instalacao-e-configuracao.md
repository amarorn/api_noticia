# Instalação e configuração

## Requisitos

- Python **3.11+**
- Node.js **18+** (frontend)
- Git

## Setup backend

```bash
cd api_noticia
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
```

### Dependências opcionais

```bash
pip install -e ".[ml]"    # transformers, sklearn, mlflow
pip install -e ".[gcp]"   # BigQuery, GCS
```

## Variáveis de ambiente (`.env`)

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `LAKE_ROOT` | Raiz do datalake | `./data/lake` |
| `COLLECT_LOOKBACK_DAYS` | Dias retroativos RSS | `7` |
| `ODDS_API_KEY` | Chave The Odds API | — |
| `ODDS_DEFAULT_SPORT` | Sport key | `soccer_fifa_world_cup` |
| `ODDS_DEFAULT_REGIONS` | Regiões bookmakers | `eu` |
| `API_HOST` | Host uvicorn | `0.0.0.0` |
| `API_PORT` | Porta API | `8000` |

> **Nunca commite** `.env` — já está no `.gitignore`.

## Dados iniciais obrigatórios (Copa)

```bash
import-world-cup --list
import-world-cup --missing-only    # 1930–2022
```

Sem fixtures WC, `/worldcup/*` retorna erro pedindo import.

## Baselines KXL (opcional, Copa 2026)

```bash
python3 scripts/import_wc_baselines.py "/caminho/arquivo-baselines.txt"
```

Gera/atualiza `data/wc/team_baselines.json`.

## Desenvolvimento — dois terminais

**Terminal 1 — API:**

```bash
source .venv/bin/activate
./scripts/dev-api.sh
# alternativa estável (sem reload): ./scripts/dev-api-stable.sh
```

**Terminal 2 — Frontend:**

```bash
cd frontend
npm install
npm run dev
```

| URL | Serviço |
|-----|---------|
| http://localhost:8000 | API |
| http://localhost:8000/docs | Swagger OpenAPI |
| http://localhost:5173 | UI React |

## Proxy Vite

O frontend chama `/api/*`; o Vite remove o prefixo e encaminha para `localhost:8000`.

```env
# frontend/.env (opcional)
VITE_API_URL=/api
```

## Troubleshooting

| Sintoma | Solução |
|---------|---------|
| `ECONNREFUSED` no Vite | Subir API na porta 8000 |
| `ECONNRESET` em `/news/sync` | Usar `dev-api.sh` (não reinicia ao escrever em `data/`) |
| Primeira previsão WC lenta (~1–2 min) | Normal — modelos treinam no startup; aguarde `Application startup complete` |
| Value bets vazio | Configure `ODDS_API_KEY`; `matched_games` pode ser 0 se schedule ≠ mercado ao vivo |
| `/worldcup/editions/.../matches` 500 | Reinicie API após updates; jogos mata-mata têm `group_name: null` |

## Testes

```bash
pytest tests/ -q
cd frontend && npm run build
```

## Comandos CLI (entry points)

Ver lista completa em [datalake-e-pipelines.md](datalake-e-pipelines.md).

```bash
collect-news          # Coleta RSS → bronze
daily-sync            # Coleta + silver
predict-wc            # Palpites WC CLI
predict-round         # Rodada Brasileirão
fetch-wc-odds         # Odds ao vivo
benchmark-wc-models   # Compara modelos
```
