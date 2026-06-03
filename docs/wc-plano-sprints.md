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

## Próximo passo sugerido (Sprint 4)

1. Integrar notícias RSS com entidades de seleções nacionais no silver.
2. Walk-forward automático no CI após `import-world-cup`.
3. Calibrar peso KXL (25%) por edição, como o ensemble DC/logística.
4. Persistir também hash de `team_baselines.json` no manifest.
