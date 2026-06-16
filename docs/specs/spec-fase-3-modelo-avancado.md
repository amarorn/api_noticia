# Spec — Fase 3: Modelo Avançado (Hawkes + GBM Ensemble)

**Status:** Accepted (implementada 2026-06-10)
**Duração estimada:** 4–6 semanas
**Owner:** amaro
**Depende de:** Fases 0, 1, 2 (dataset timeline + walk-forward in-play já existem)
**Habilita:** —

---

## 1. Goal

Ir além do Poisson não-homogêneo para o **estado da arte em modelagem in-play**:

1. **Hawkes process** para timing de gols (captura clustering de gols após pressão).
2. **LightGBM** prevendo `P(próximo gol nos próximos K min | estado)` em paralelo ao Poisson.
3. **Ensemble blending** dinâmico: Poisson + GBM + Hawkes + Mercado, com pesos calibrados.

## 2. Non-goals

- ❌ Não tenta prever placar exato via deep learning (volume insuficiente).
- ❌ Não substitui modelo pré-jogo — continua Dixon-Coles + Logística.
- ❌ Não faz computer vision / event detection em vídeo.

## 3. Motivação

Mesmo após Fase 2, o Poisson tem limites estruturais:

- **Independência temporal**: assume que P(gol no min 51) é independente de P(gol no min 50). Empiricamente, há **clustering**: após um gol, há 8-12 min de "janela quente" onde a probabilidade de outro gol sobe.
- **Não-linearidade**: efeitos como `score × minute × red_card` são interações complexas que o MLE log-linear captura mal.
- **Features de alta cardinalidade**: estilo de jogo (posse, chutes, xG ao vivo) entram melhor em árvores.

Hawkes resolve (1). GBM resolve (2)+(3). Ensemble combina os pontos fortes.

## 4. Success Metrics

| Métrica | Baseline (Fase 2) | Alvo |
|---|---|---|
| Brier `prob_next_goal_*` (snapshot 60-85min) | medir | -0.010 adicional |
| Brier `prob_final_*` (todos snapshots) | medir | -0.005 adicional |
| Log-loss `next_goal_window_10min` | medir | -5% |
| Latência p95 `simulate_inplay()` | Fase 2 | manter < 2× |
| ROI simulado em apostas live com `min_edge=5%` | Fase 2 | +20% |

## 5. Design Técnico

### 5.1 Hawkes Process para timing de gols

**Modelo:** intensidade auto-excitante

```
λ(t) = μ(t) + Σ_{t_i < t} α × exp(-β × (t - t_i))
```

- `μ(t)`: baseline (vem do NHPP da Fase 2)
- `α`: salto após cada gol
- `β`: taxa de decaimento (~0.1 → meia-vida ~7min)
- Soma sobre gols passados de **ambos os times** (gols geram retaliação)

Calibrado por MLE no mesmo dataset timeline.

**Novo módulo:** `models/wc_hawkes.py`

```python
@dataclass
class HawkesParameters:
    alpha_self: float   # boost da intensidade após gol próprio
    alpha_cross: float  # boost após gol adversário
    beta: float         # decaimento

def hawkes_lambda(t: float, past_goals: list[tuple[float, str]], params: HawkesParameters, mu_base: float) -> float: ...

def simulate_hawkes_remaining(t_now: float, t_end: float, mu_func, params, past_goals, rng) -> list[tuple[float, str]]: ...
```

Substitui (opcionalmente) o sampling Poisson em `wc_inplay.py:_sample_poisson_bivariate`.

### 5.2 LightGBM para `P(próximo gol)`

**Target:** binário — houve gol em `[t, t+10min]`?

**Features (snapshot no minuto t):**
- λ_full_home, λ_full_away (do Dixon-Coles)
- goal_diff, home_score, away_score, minute
- home_red, away_red, home_corners, away_corners
- home_xg_acc, away_xg_acc, xg_diff
- home_shots_on_target, away_shots_on_target
- possession_home (se disponível)
- elo_diff, fifa_rank_diff
- minutes_since_last_goal
- is_late_game (binário)
- market_lambda_implied (Fase 1)

**Output:** `P(gol_home_10min)`, `P(gol_away_10min)`, `P(no_goal_10min)`.

**Treino:** LightGBM multiclasse, walk-forward por season. K-fold dentro de cada season para early stopping.

**Novo módulo:** `models/wc_inplay_gbm.py`

### 5.3 Ensemble dinâmico

Stacking: cada modelo gera `P(gol_home_10min)`, e um **regressor logístico** aprende a combinar.

```python
ensemble_p = sigmoid(
    w_poisson × logit(p_poisson) +
    w_hawkes × logit(p_hawkes) +
    w_gbm × logit(p_gbm) +
    w_market × logit(p_market) +
    b
)
```

Pesos `w_*` aprendidos no holdout, e podem variar com `minute_bucket`:

```python
weights[(0,30)]  = {poisson: 0.4, hawkes: 0.1, gbm: 0.3, market: 0.2}
weights[(30,60)] = {poisson: 0.3, hawkes: 0.2, gbm: 0.3, market: 0.2}
weights[(60,90)] = {poisson: 0.2, hawkes: 0.2, gbm: 0.3, market: 0.3}
```

### 5.4 Arquitetura final

```
                          ┌────────────────┐
                          │  Pré-jogo      │
                          │  λ_full        │ ← Fase 0
                          └────────┬───────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
        ┌─────▼─────┐        ┌─────▼─────┐        ┌─────▼─────┐
        │ Poisson   │        │  Hawkes   │        │  LightGBM │
        │ NHPP      │        │  process  │        │  P(goal)  │
        │ (Fase 2)  │        │  (Fase 3) │        │  (Fase 3) │
        └─────┬─────┘        └─────┬─────┘        └─────┬─────┘
              │                    │                    │
              └────────┬───────────┴──────────┬─────────┘
                       │                      │
                ┌──────▼──────┐        ┌──────▼──────┐
                │   Mercado   │        │   Stacking  │
                │  (shrinkage)│───────▶│  ensemble   │
                │  (Fase 1)   │        │  (Fase 3)   │
                └─────────────┘        └──────┬──────┘
                                              │
                                       ┌──────▼──────┐
                                       │  Calibrator │
                                       │  (Fase 0)   │
                                       └──────┬──────┘
                                              │
                                       Probabilidades finais
```

### 5.5 Mudanças em arquivos existentes

| Arquivo | Mudança |
|---|---|
| `models/wc_hawkes.py` | **Novo** |
| `models/wc_inplay_gbm.py` | **Novo** |
| `models/wc_inplay_ensemble.py` | **Novo** — stacking + weights por minuto |
| `pipelines/wc_inplay_gbm_train.py` | **Novo** — treino LightGBM walk-forward |
| `pipelines/wc_inplay_hawkes_fit.py` | **Novo** — MLE de α, β |
| `models/wc_inplay.py` | Integrar ensemble como camada extra |
| `models/train.py` | Etapa `--with-hawkes`, `--with-gbm` |
| `pyproject.toml` | Adicionar `lightgbm`, `scipy` (já tem) |

## 6. Plano de Implementação

### Semana 1–2 — Hawkes
- [x] `models/wc_hawkes.py` + MLE (`fit-inplay-hawkes`).
- [x] Artefato `hawkes_params.json`.
- [x] Validação via `validate-inplay-phase3`.

### Semana 3–4 — LightGBM
- [x] `models/wc_inplay_gbm.py` + `train-inplay-gbm`.
- [x] Artefato `inplay_gbm.pkl`.
- [ ] Features xG/posse ao vivo (quando Sofascore live disponível).

### Semana 5 — Ensemble + calibração
- [x] `models/wc_inplay_ensemble.py` com pesos por bucket.
- [x] `simulate_inplay_ensemble` integrado em `inplay_from_predictor`.
- [x] `validate-inplay-phase3`.

### Semana 6 — Rollout
- [x] Flags: `INPLAY_USE_ENSEMBLE`, `INPLAY_ENSEMBLE_HAWKES`, `INPLAY_ENSEMBLE_GBM`.
- [x] Shadow mode: `INPLAY_ENSEMBLE_SHADOW_MODE=true` (Poisson na UI até validação live).
- [ ] 2 semanas shadow com `benchmark-inplay` antes de `SHADOW_MODE=false`.

## 7. Test Plan

### Unit tests
- `tests/test_hawkes.py`: simulação reproduzível com seed; intensidade decai com β correto.
- `tests/test_inplay_gbm.py`: treino com seed; feature importance estável; serialização.
- `tests/test_inplay_ensemble.py`: pesos somam 1 por bucket; saída ∈ [0,1].

### Backtesting financeiro
- Simular apostas live (1X2, OU, BTTS, next_goal) com `min_edge=5%` em Copa 2022 holdout.
- Reportar ROI, Sharpe, drawdown, hit rate vs. baseline Fase 2.

### Latency tests
- `simulate_inplay()` com ensemble completo deve rodar < 2s.
- GBM inference < 50ms; Hawkes sampling < 500ms para 10k simulações.

## 8. Rollback Plan

- Cada modelo tem **feature flag independente**.
- Pesos do ensemble podem ser zerados via config (`w_hawkes=0, w_gbm=0` → cai para Poisson + Mercado).
- Artefatos versionados; rollback é trocar versão em `WcArtifact`.

## 9. Riscos

| Risco | Mitigação |
|---|---|
| Volume de dados insuficiente para GBM (~300-500 jogos com timeline completa) | Aumentar dataset com Champions League / Premier (ajustar features); avaliar valor da inclusão |
| Hawkes instável com `α + β` na fronteira de estabilidade | Restringir parâmetros: `α/β < 0.95` |
| Overfitting do ensemble | CV externa por season; reportar gap train-test |
| Latência do ensemble inviabiliza endpoint real-time | Cachear λ_pré-jogo; GBM batch-size=1 com `predict_proba` rápido |
| Ensemble não bate Fase 2 | Aceitar — relatar, manter Fase 2 em produção, documentar lições |

## 10. Definition of Done

- [x] 3 componentes (Hawkes, GBM, Ensemble) implementados (`tests/test_inplay_phase3.py`).
- [x] Walk-forward por componente (`validate-inplay-phase3`).
- [ ] Ganho ≥ 0.005 Brier vs Fase 2 — **holdout 2022 ainda não atingiu** (ver §11).
- [ ] Backtest financeiro ROI (opcional).
- [x] Shadow mode ativo por padrão (`INPLAY_ENSEMBLE_SHADOW_MODE=true`).
- [ ] Desligar shadow após validação live ticks.

## 11. Resultados walk-forward (holdout 2022, n_sim=1500)

| Variante | Brier | Δ vs Fase 2 |
|---|---|---|
| `fase2_poisson` (baseline) | **0.12166** | — |
| `fase3_hawkes_only` | 0.12178 | -0.00013 |
| `fase3_gbm_only` | 0.13079 | -0.00913 |
| `fase3_ensemble_full` | 0.12569 | -0.00403 |

**Decisão:** manter Poisson Fase 2 na UI. Ensemble disponível via flags para A/B e coleta live. GBM requer mais features ao vivo (xG/posse) antes de novo treino.

CLI: `validate-inplay-phase3 --eval-season 2022 --json`

---

## Apêndice — Decisão de escopo

Se ao final da semana 2 (Hawkes) não houver ganho relevante, **suspender Hawkes** e focar GBM. Hawkes tem custo de complexidade alto e ganho marginal incerto na escala de Copa do Mundo (poucos jogos por edição).

GBM é o componente com maior ROI esperado e deve ser **prioridade absoluta** nesta fase.
