# Referência da API

Base URL: `http://localhost:8000`  
Documentação interativa: `/docs`  
Versão: **0.2.0**

Todas as respostas são JSON. CORS habilitado (`*`).

## Autenticação (API key)

Quando `API_KEY` está definida no ambiente do servidor, **todas as rotas** exigem chave, exceto:

- `GET /health/live` (liveness Fly)
- `/docs`, `/redoc`, `/openapi.json`

Envie a chave de uma destas formas:

| Forma | Exemplo |
|-------|---------|
| Header | `X-API-Key: sua-chave` |
| Bearer | `Authorization: Bearer sua-chave` |

Várias chaves válidas: `API_KEY=chave-antiga,chave-nova` (rotação).

Sem `API_KEY` no servidor, a API permanece aberta (desenvolvimento local).

```bash
# Fly.io
fly secrets set API_KEY="$(openssl rand -hex 32)" -a api-noticia

curl -H "X-API-Key: $API_KEY" https://api-noticia.fly.dev/news/all
```

Frontend (build/deploy):

```env
VITE_API_KEY=mesma-chave-do-servidor
```

---

## Saúde e meta

### `GET /health`

Status do datalake e contadores.

```bash
curl -s http://localhost:8000/health
```

### `GET /data/pulse`

Pulso do datalake (mesmo uso no navegador): contadores, `latest_silver_at`, última coleta em `_meta/collections.jsonl` e links das ações (`POST /news/sync`, `GET /news/all`).

**Em cada requisição** (exceto `/health/live` e docs), a API inclui headers de pulso na resposta:

| Header | Conteúdo |
|--------|----------|
| `X-Data-Pulse-At` | ISO8601 do snapshot |
| `X-Articles-Silver` | Artigos no silver |
| `X-Fixtures` | Fixtures (Brasileirão) |
| `X-WC-Models-Ready` | `true` / `false` |
| `X-Collections-Last-Run` | Última linha em `_meta/collections.jsonl` |
| `X-Latest-Silver-At` | mtime do parquet silver mais recente |

O frontend lê esses headers em todo `apiFetch` e atualiza o badge de status.

```bash
curl -sI http://localhost:8000/news/all | grep -i x-data-pulse
curl -s http://localhost:8000/data/pulse
```

### `GET /`

Lista de endpoints disponíveis.

---

## Notícias

### `POST /news/sync`

Dispara coleta RSS → bronze → silver (até ~800 artigos: `RSS_MAX_ENTRIES_PER_SOURCE=160` × 5 fontes).

Query opcional:

- `full_rebuild=true` — reprocessa todo o bronze no silver.
- `fetch_body=true` — baixa o HTML de cada matéria (corpo completo no `body_preview`; sync bem mais lento).

Por padrão, `body_preview` e `summary` usam o maior texto no silver **sem limite de caracteres**. O feed RSS costuma trazer só um trecho; para texto integral use `fetch_body=true` e depois `full_rebuild=true`.

### `GET /news/feed`

Feed agregado de artigos silver (filtros via query params — ver Swagger).

### `GET /news/all`

Retorna **todas** as notícias do silver em uma única resposta (mesmo formato do `/news/feed`).

| Query | Descrição | Padrão |
|-------|-----------|--------|
| `days` | Janela em dias | omitido = histórico completo no lake |
| `offset` | Deslocamento se passar de 5000 itens | `0` |
| `source`, `q`, `team`, `home_team`, `away_team`, `teams` | Mesmos filtros do feed/cards | — |

Teto interno: **5000** artigos por requisição (proteção de memória).

### `GET /news/cards`

Notícias formatadas para cards no frontend (`NewsArticleCard`).

| Query | Descrição | Padrão |
|-------|-----------|--------|
| `limit` | Máx. cards | `12` (máx. 48) |
| `offset` | Paginação | `0` |
| `days` | Janela em dias | `14` |
| `team` | Um time/seleção | — |
| `home_team` / `away_team` | Filtro por confronto | — |
| `teams` | Lista `Brasil,Marrocos` | — |
| `source`, `q` | Fonte e busca textual | — |

**Resposta:** `{ total, limit, offset, teams, cards[] }` — cada item tem `title`, `body_preview`, `sentiment_label`, `teams_mentioned`, etc.

---

## Brasileirão (notícias + heurística)

### `POST /context`

Contexto de notícias para um jogo.

```json
{
  "home_team": "Flamengo",
  "away_team": "Palmeiras",
  "round_number": 1,
  "competition": "Brasileirão",
  "season": 2024
}
```

**Resposta:** `context_text`, contagens de notícias, sentimento, posição, forma.

### `POST /predict`

Igual `/context` + palpite baseline (`1`/`X`/`2`), confiança e motivo.

### `GET /round/predict`

Palpites da rodada em `data/rounds/current.json`.

---

## Copa do Mundo — previsão

### `POST /worldcup/predict`

Palpite avulso com ensemble completo.

**Body mínimo:**

```json
{
  "home_team": "Brasil",
  "away_team": "Marrocos",
  "phase": "group"
}
```

**Body com FEPT automático (Sofascore):**

```json
{
  "home_team": "Brasil",
  "away_team": "Argentina",
  "phase": "group",
  "sofascore_event_id": 11774480
}
```

Quando `sofascore_event_id` é enviado e `kxl_match.fept` está ausente, a API busca escalação + notas no Sofascore (requer `curl_cffi` no servidor). Metadados em `model_breakdown.kxl_fept`.

### Estatísticas Sofascore (escanteios, chutes, posse)

`GET /worldcup/sofascore/{event_id}/statistics?refresh=false`

Retorna métricas achatadas (`home_corners`, `away_corners`, `home_possession_pct`, `home_xg`, cartões via incidentes, etc.). Com `refresh=false`, lê cache em `data/lake/sofascore/match_stats.parquet` se existir.

CLI equivalente:

```bash
ingest-sofascore --event-id 11774480 --stats-only --json
ingest-sofascore --event-id 11774480 --with-stats
```

### Previsão de escanteios (Poisson)

`POST /worldcup/corners/predict`

```json
{
  "home_team": "Brasil",
  "away_team": "Marrocos",
  "phase": "group"
}
```

Resposta inclui `expected_corners` (ex. `"5.8x4.2"`), `expected_total_corners`, probabilidades `over_9.5` / `under_9.5` e fatores do modelo (`lambda_home`, `lambda_away`). Treina com histórico em `data/lake/sofascore/match_stats.parquet`; com poucos jogos, faz blend com λ de gols (proxy).

CLI: `predict-corners --home Brasil --away Marrocos --json`

**Body com entrada dinâmica KXL** (opcional):

```json
{
  "home_team": "Brasil",
  "away_team": "Marrocos",
  "phase": "group",
  "kxl_match": {
    "fecl": { "previsao_chuva_pct": 55, "estado_gramado": "Molhado" },
    "feju": { "perfil": "punitivista", "indice_cartao_falta": 0.28 },
    "fede": {
      "desfalques_visitante": [
        { "jogador": "Ziyech", "impacto_nota_elenco": -0.8 }
      ]
    },
    "fept": {
      "esquema_mandante": "4-3-3",
      "mandante_titulares_notas": {
        "goleiro": { "nome": "Alisson", "nota_sofascore": 7.1 },
        "atacantes": [{ "nome": "Vini Jr", "nota_sofascore": 7.9 }]
      }
    },
    "feem": { "contexto_peso_caos": 1.25, "jogo_decisivo": true }
  }
}
```

**Resposta principal:**

| Campo | Descrição |
|-------|-----------|
| `prediction` | `1`, `X` ou `2` |
| `confidence` | Probabilidade do palpite (0–1) |
| `prob_home`, `prob_draw`, `prob_away` | Probabilidades finais |
| `poisson_score` | Placar mais provável (Dixon-Coles) |
| `expected_goals` | Ex.: `"1.4x1.0"` |
| `context` | Texto IA (stats + DNA KXL + colisão) |
| `model_breakdown` | Ver abaixo |

**`model_breakdown`:**

```json
{
  "dixon_coles": { "1": 0.69, "X": 0.21, "2": 0.10 },
  "logistic": { "1": 0.56, "X": 0.22, "2": 0.22 },
  "dixon_coles_rho": 0.08,
  "poisson_factors": {
    "lambda_home": 1.42,
    "lambda_away": 0.98,
    "home_attack": 1.15,
    "away_attack": 0.92,
    "rho": 0.08
  },
  "ensemble_weights": { "dixon_coles": 0.30, "logistic": 0.70 },
  "kxl_baseline": { "1": 0.45, "X": 0.28, "2": 0.27, "blend_weight": 0.25 },
  "kxl_collision": { },
  "kxl_dynamic": { "blocks_used": ["fecl", "fept"], "engine": "wc_kxl_collision" }
}
```

### `GET /worldcup/round`

Palpites para todos os jogos em `data/rounds/wc_2026.json`.

### `GET /worldcup/teams`

Lista de seleções (fixtures + rodada).

---

## Copa — validação histórica

### `GET /worldcup/editions`

Edições disponíveis (1986–2022 no lake típico).

### `GET /worldcup/editions/{season}/matches`

Jogos reais de uma edição (placar, fase, resultado). Mata-mata: `group_name: null`.

### `POST /worldcup/validate`

Backtest com **recorte temporal** (só dados anteriores ao jogo).

```json
{ "season": 2022, "home_team": "Brasil", "away_team": "Sérvia" }
```

ou `{ "season": 2022, "match_id": "..." }`.

**Resposta:** `correct: true/false`, `actual_result`, `cutoff_note`.

---

## Value bets (odds + EV)

### `POST /worldcup/value/live`

Requer `ODDS_API_KEY` no `.env`.

```json
{
  "min_edge": 0.03,
  "schedule_file": "data/rounds/wc_2026.json"
}
```

Cruza probabilidades do modelo com odds The Odds API. Retorna `edges[]` com EV, fair odd, Kelly ¼.

---

## Superbet ao vivo — Super Múltipla

Documentação completa: [super-multipla.md](super-multipla.md).

### `POST /worldcup/superbet/multiple/calculate`

Calcula odds combinadas, prêmio e elegibilidade da promo Super Múltipla (+5% quando todas as pernas ≥ 1,35).

```json
{
  "legs": [
    { "market": "h2h", "outcome": "1", "market_odd": 1.80, "superbet_event_id": 13127506, "is_live": true },
    { "market": "over_2_5", "outcome": "yes", "market_odd": 2.10, "superbet_event_id": 13127506, "is_live": true }
  ],
  "stake": 5.0,
  "bet_type": "MULTIPLE",
  "minute": 23
}
```

Resposta: `total_odds`, `potential_payout`, `bonus_eligible`, `bonus_percentage`, `final_payout`, `builder_validation`.

### `GET /worldcup/superbet/live/{event_id}/advice`

Com `fast=false`, inclui bloco `super_multipla.suggested_combos` (pares compatíveis do `market_scan`).

### `POST /user/open-bets`

Múltiplas com 2+ pernas recebem `bonus_eligible`, `bonus_percentage` e `final_payout` recalculados no cadastro.

---

## Códigos de erro comuns

| HTTP | Causa |
|------|-------|
| 400 | Body inválido, chave odds ausente |
| 404 | Rodada/arquivo/ jogo não encontrado |
| 502 | Falha na Odds API externa |

## Exemplos curl

```bash
# Palpite WC
curl -s -X POST http://localhost:8000/worldcup/predict \
  -H "Content-Type: application/json" \
  -d '{"home_team":"Brasil","away_team":"Marrocos"}'

# Validar Copa 2022
curl -s -X POST http://localhost:8000/worldcup/validate \
  -H "Content-Type: application/json" \
  -d '{"season":2022,"home_team":"Brasil","away_team":"Sérvia"}'

# Via proxy frontend
curl -s http://localhost:5173/api/health
```
