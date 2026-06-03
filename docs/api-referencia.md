# Referência da API

Base URL: `http://localhost:8000`  
Documentação interativa: `/docs`  
Versão: **0.2.0**

Todas as respostas são JSON. CORS habilitado (`*`).

---

## Saúde e meta

### `GET /health`

Status do datalake e contadores.

```bash
curl -s http://localhost:8000/health
```

### `GET /`

Lista de endpoints disponíveis.

---

## Notícias

### `POST /news/sync`

Dispara coleta RSS → bronze → silver.

### `GET /news/feed`

Feed agregado de artigos silver (filtros via query params — ver Swagger).

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
