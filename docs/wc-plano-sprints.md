# Plano de melhorias — modelo Copa (Sprints 2–3)

## Sprint 2 — Persistência e ensemble unificado

### Entregas

| Item | Status | Como usar |
|------|--------|-----------|
| Artefato em disco (`predictor.pkl` + `manifest.json`) | Feito | `train-wc` ou startup da API |
| Cache invalida ao mudar fixtures ou `squads_2026.json` | Feito | fingerprint no manifest |
| Logística única no ensemble | Feito | `CollaborativeWcModel` reutiliza `WcPredictor.logistic` |
| `/health` expõe `wc_artifact` | Feito | `GET /health` |
| Retreino manual | Feito | `POST /worldcup/retrain` ou `train-wc --force` |

### Comandos

Os CLIs `train-wc` e `walkforward-wc-models` existem após instalar o pacote:

```bash
pip install -e ".[dev,ml]"
```

Com o venv ativo (`source .venv/bin/activate`):

```bash
import-world-cup --missing-only
train-wc                    # treina e grava em data/lake/artifacts/wc_predictor/
train-wc --force            # ignora cache
```

Alternativa sem entry point no PATH:

```bash
.venv/bin/train-wc --force
.venv/bin/walkforward-wc-models --max-editions 10
```

Variáveis em `.env` (opcional):

- `WC_ARTIFACT_FORCE_RETRAIN=true` — sempre retreina na subida da API

### Artefato

```
data/lake/artifacts/wc_predictor/
├── manifest.json    # métricas, fingerprints, pesos do ensemble
└── predictor.pkl    # logística, Dixon-Coles, pesos colaborativos
```

Após `import-world-cup` ou editar convocações, rode `train-wc --force` (não precisa mais reiniciar só por isso se usar `POST /worldcup/retrain`).

---

## Sprint 3 — Walk-forward e features de convocação

### Entregas

| Item | Status | Como usar |
|------|--------|-----------|
| Validação walk-forward por edição | Feito | `walkforward-wc-models` |
| Relatório JSON | Feito | `data/lake/reports/wc_walkforward_report.json` |
| API leitura do relatório | Feito | `GET /worldcup/walkforward` |
| 6 features de elenco 2026 | Feito | `pipelines/wc_squad_features.py` |

### Walk-forward

Treina com todas as edições **anteriores** à avaliada (sem vazamento temporal):

```bash
walkforward-wc-models
walkforward-wc-models --max-editions 8 --min-season 1990
```

### Features de convocação

Derivadas de `data/wc/squads_2026.json`:

- `squad_depth_diff` — tamanho do elenco (26 = 1.0)
- `squad_top5_league_diff` — jogadores em ligas top (EPL, La Liga, etc.)
- `squad_def_share_diff` / `squad_atk_share_diff` / `squad_mid_share_diff`
- `squad_structural_balance_diff` — defesa + meio vs adversário

Seleções fora do JSON recebem perfil neutro (não quebra o modelo).

---

## Hiperparâmetros (calibrados)

Arquivo: `data/wc/hyperparams.json` (gerado por `tune-wc-hyperparams`).

| Parâmetro | Antes (implícito) | Depois (tuned) |
|-----------|-------------------|----------------|
| `elo_home_adv` | 65 | **25** |
| `home_adv_goals_neutral` | 0.15 | **0.05** |
| `logistic_c` | 1.0 (default sklearn) | **1.0** + `class_weight=balanced` |
| `kxl_blend_weight` | 0.25 fixo | **0.25** (calibrado) |
| `draw_prob_floor` | — | **0.16** (mais empates plausíveis) |
| Grade ensemble | 21 passos (5%) | **41 passos (2,5%)** |

```bash
pip install -e ".[dev,ml]"
tune-wc-hyperparams              # modo rápido (~6 min)
tune-wc-hyperparams --slow       # grade completa (lento)
train-wc --force                 # aplica e persiste artefato
```

Holdout 2022 após retreino: Brier ~**0,194**, acurácia modal ~**47%** (com piso de empate + classes balanceadas). Na rodada 2026: **43** mandantes, **27** visitantes, **2** empates (antes: 52/19/1).

---

## Sprint 4 — Notícias, calibração e CI

### Entregas

| Item | Status | Como usar |
|------|--------|-----------|
| Seleções no silver (`national_teams_mentioned`) | Feito | `collect-news` → silver; lexicon em `national_team_entities.py` |
| 3 features de notícias WC | Feito | `wc_news_count_diff`, `wc_news_sentiment_diff`, `wc_news_available` |
| Calibração Platt (sigmoid cv=3) na logística | Feito | artefato v5; `train-wc --force` |
| Fingerprint `team_baselines.json` + silver | Feito | invalida cache no manifest |
| Tune peso KXL | Feito | `tune-wc-kxl` → `data/lake/reports/wc_kxl_blend_report.json` |
| Walk-forward no CI | Feito | job `wc-model` em `.github/workflows/ci.yml` |
| Feed expõe seleções | Feito | `GET /news/feed` → `national_teams_mentioned` |

### Comandos

```bash
collect-news
train-wc --force
tune-wc-kxl              # grade 0–40% no holdout 2022
tune-wc-kxl --apply      # grava melhor peso em hyperparams.json
walkforward-wc-models --max-editions 6
```

Artefato **v5**: 26 features (23 anteriores + 3 notícias). Logística com `CalibratedClassifierCV(method="sigmoid")`.
