# Spec — Fase 2: Calibração MLE do Momentum e In-Play

**Status:** Accepted (implementada 2026-06-10)
**Duração estimada:** 2 semanas
**Owner:** amaro
**Depende de:** Fases 0, 1
**Habilita:** Fase 3

---

## 1. Goal

Substituir **todas as constantes chutadas** do modelo in-play por **coeficientes estimados via MLE** sobre dataset histórico minuto-a-minuto. Estabelecer **walk-forward in-play** como métrica oficial.

## 2. Non-goals

- ❌ Não substitui Poisson por GBM (Fase 3).
- ❌ Não introduz Hawkes process (Fase 3).
- ❌ Não muda modelo pré-jogo.

## 3. Motivação

`models/wc_live_momentum.py` tem 7 constantes mágicas que nunca foram validadas:

```python
_GOAL_DIFF_ATTACK_FACTOR = 0.06         # ← chute
_GOAL_DIFF_DEFEND_PRESSURE = 0.08       # ← chute
_LATE_GAME_COMPRESS_START = 75          # ← chute
_LATE_GAME_COMPRESS_FACTOR = 0.85       # ← chute
_RED_CARD_OWN_PENALTY = 0.15            # ← chute
_RED_CARD_OPP_BOOST = 0.10              # ← chute
_OFFENSIVE_SUB_BOOST = 0.05             # ← chute
```

Mais os pesos NHPP da Fase 1 (que foram da literatura). Sem calibração, **não dá pra dizer se o momentum ajuda ou atrapalha** — pode estar reduzindo Brier ou aumentando.

## 4. Success Metrics

| Métrica | Baseline (Fase 1) | Alvo |
|---|---|---|
| Brier in-play walk-forward (snapshot 15min) | medir | -0.005 adicional |
| Brier in-play walk-forward (snapshot 75min) | medir | -0.010 adicional |
| Cada constante do momentum tem **intervalo de confiança 95%** | ❌ | ✅ |
| Pesos NHPP estimados por bucket de 5min | inicial: 7 buckets manuais | 18 buckets MLE |
| Walk-forward in-play roda em < 1h | ❌ não existe | ✅ |

## 5. Design Técnico

### 5.1 Dataset minuto-a-minuto

**Schema** (parquet em `data/lake/silver/wc_timeline/`):

```python
timeline_event:
    match_id: str
    season: int
    minute: int                   # 0..120
    home_score: int               # antes do evento
    away_score: int
    home_red_cards: int           # acumulado
    away_red_cards: int
    home_corners: int
    away_corners: int
    home_xg: float                # acumulado
    away_xg: float
    home_offensive_subs: int      # acumulado
    away_offensive_subs: int
    event_type: str | None        # "goal_home", "goal_away", "red_home", ...
    minute_lambda_home_pre: float # do modelo Fase 1
    minute_lambda_away_pre: float
```

**Fonte:** Sofascore (já no `ingest/`). Precisa pipeline `pipelines/wc_build_timeline.py` que percorre fixtures históricas e materializa.

### 5.2 Walk-forward in-play (`pipelines/wc_inplay_walkforward.py`)

```python
def evaluate_inplay(
    timeline_df: pd.DataFrame,
    *,
    snapshot_minutes: list[int] = [15, 30, 45, 60, 75, 85],
    eval_season: int,
    use_calibrated_momentum: bool = False,
) -> dict:
    """Para cada (jogo, minuto_snapshot) prevê e mede Brier vs resultado real."""
```

Saídas: Brier por bucket de minuto, por mercado (1X2, OU2.5, BTTS), por placar atual.

### 5.3 MLE do momentum

Modelo log-linear sobre o multiplicador de λ_remaining:

```
log(factor_home) = β_0
                 + β_1 × goal_diff
                 + β_2 × max(0, minute - 75)
                 + β_3 × home_red_cards
                 + β_4 × away_red_cards
                 + β_5 × home_offensive_subs
                 + β_6 × corner_share_home
                 + β_7 × goal_diff × (minute > 75)   # interação

log(factor_away) = simétrico
```

**Likelihood:** Poisson com λ = λ_full_NHPP × factor.

```python
def fit_momentum_mle(timeline_df: pd.DataFrame, train_seasons: list[int]) -> MomentumCoefficients:
    """L-BFGS-B sobre log-likelihood Poisson. Retorna β's + erros padrão (Hessiana inversa)."""
```

### 5.4 MLE do perfil NHPP

Mesmo framework. Para cada bucket de 5 min `[t_i, t_{i+1}]`, estima peso `w_i`:

```
λ_bucket_i = λ_full × w_i,  com Σ w_i × duration_i = match_minutes
```

Restrições: `w_i ≥ 0.3`, `w_i ≤ 2.0`, `Σ w_i × dur_i = 90`.

Otimizar via SLSQP com restrição de igualdade.

### 5.5 Persistência dos coeficientes

Novo módulo `models/wc_inplay_coefficients.py`:

```python
@dataclass
class InPlayCoefficients:
    momentum_betas: dict[str, float]
    momentum_se: dict[str, float]
    nhpp_weights: list[tuple[int, int, float]]  # (start, end, weight)
    trained_at: datetime
    train_seasons: list[int]
    n_observations: int
    in_sample_loglik: float
    holdout_brier: float
```

Carregado por `wc_live_momentum` e `wc_intensity_profile`. Fallback: constantes da Fase 1.

### 5.6 Mudanças em arquivos existentes

| Arquivo | Mudança |
|---|---|
| `pipelines/wc_build_timeline.py` | **Novo** — materializa timeline silver |
| `pipelines/wc_inplay_walkforward.py` | **Novo** — Brier in-play oficial |
| `pipelines/wc_inplay_tune.py` | **Novo** — MLE momentum + NHPP |
| `models/wc_inplay_coefficients.py` | **Novo** — persistência |
| `models/wc_live_momentum.py` | Ler coeficientes; fallback p/ constantes |
| `pipelines/wc_intensity_profile.py` | Idem |
| `models/train.py` | Adicionar etapa opcional `--with-inplay` |
| `pipelines/wc_calibration.py` | Adicionar seção in-play no relatório |

## 6. Plano de Implementação

### Semana 1 — Dataset e walk-forward

**Dia 1–3 — Pipeline timeline**
- [x] `pipelines/wc_build_timeline.py` + CLI `build-wc-timeline`.
- [x] Persistência em `data/lake/silver/wc_timeline/timeline.parquet`.
- [x] Testes: `tests/test_inplay_phase2.py`.

**Dia 4–5 — Walk-forward in-play**
- [x] `pipelines/wc_inplay_walkforward.py` com Brier por minuto.
- [x] Flag `use_calibrated_coefficients` para A/B.
- [ ] MLflow (opcional).

### Semana 2 — MLE e integração

**Dia 6–8 — MLE momentum**
- [x] `pipelines/wc_inplay_tune.py` com `fit_momentum_mle` + IC 95%.
- [x] CLI `tune-inplay` com holdout Brier.

**Dia 9 — MLE NHPP**
- [x] `fit_nhpp_weights` integrado no tune.

**Dia 10 — Persistência e integração**
- [x] `models/wc_inplay_coefficients.py`.
- [x] `wc_live_momentum` + `wc_intensity_profile.get_intensity_profile()`.
- [x] `validate-inplay-phase2`.

**Dia 11–12 — Relatório e rollout**
- [ ] `wc_calibration.py` seção in-play (opcional).
- [ ] Doc `docs/modelos-preditivos.md` (opcional).
- [x] Momentum MLE: `inplay_use_calibrated_coefficients=True`.
- [x] NHPP MLE treinado mas **desligado** por padrão (`inplay_use_calibrated_nhpp=false`) até timeline real Sofascore.

## 7. Test Plan

### Unit tests
- `tests/test_inplay_coefficients.py`: serialização round-trip.
- `tests/test_inplay_walkforward.py`: para jogo conhecido, snapshot min 90 = resultado real.

### Statistical tests
- Cada β do momentum tem `|β/SE| > 2` (significância) ou é descartado.
- Pesos NHPP somam exato `match_minutes` (restrição).
- LR test: modelo com momentum vs sem momentum.

### Regression tests
- Brier in-play (calibrado) ≤ Brier in-play (Fase 1).
- Brier pré-jogo (calibrado) ≈ Brier pré-jogo (Fase 0) — momentum não deve afetar.

## 8. Rollback Plan

- `wc_inplay_coefficients.py` é **opcional**. Se arquivo de coeficientes ausente, fallback para constantes Fase 1.
- Feature flag desliga uso dos coeficientes calibrados.
- Coeficientes versionados por hash do dataset — facilita comparar versões.

## 9. Riscos

| Risco | Mitigação |
|---|---|
| Dataset timeline incompleto (Sofascore não cobre WC antigas) | Limitar treino a WC 2010+ (4 edições + amistosos) |
| Não-convergência do MLE | L-BFGS-B com restart aleatório; validar com gradient check |
| Overfitting (poucos jogos, muitos β's) | Regularização L2; CV por edição |
| Coeficientes "anti-intuitivos" (ex: vermelho aumenta λ próprio) | Investigar antes de aceitar; pode revelar bug no pipeline |
| Walk-forward in-play roda > 1h | Cache de λ_full; paralelizar por jogo |

## 10. Definition of Done

- [x] `data/lake/silver/wc_timeline/` via `build-wc-timeline` (≥ 200 jogos).
- [x] Walk-forward com Brier por bucket (`validate-inplay-phase2`).
- [x] Coeficientes em `data/lake/artifacts/inplay_coefficients.json` com IC 95%.
- [ ] Brier calibrado reduz ≥ 0.005 vs Fase 1 (medir com `validate-inplay-phase2`).
- [x] Produção com `inplay_use_calibrated_coefficients=True`.
- [ ] Doc β's (opcional).
