# Spec — Fase 1: Quick Wins In-Play

**Status:** Accepted (implementada 2026-06-10)
**Duração estimada:** 1 semana
**Owner:** amaro
**Depende de:** Fase 0 (pipeline reproduzível)
**Habilita:** Fase 2

---

## 1. Goal

Corrigir 3 problemas estruturais do modelo in-play com **mudanças cirúrgicas, sem retreinar nada**:

1. **Ordem errada Bayesian × Momentum** (dupla contagem do placar)
2. **Poisson homogêneo no tempo** (subestima gols no final, superestima no início)
3. **Odds Superbet não shrinkam o modelo** (mercado é ignorado)

## 2. Non-goals

- ❌ Não treina coeficientes do momentum (isso é Fase 2).
- ❌ Não muda Dixon-Coles pré-jogo.
- ❌ Não adiciona GBM / Hawkes.

## 3. Motivação

### Problema 1 — Ordem Bayesian × Momentum
Em `models/wc_inplay.py:412-440`:
```python
# HOJE:
if bayesian_update and minute > 0:
    lambda_full_home = bayesian_lambda_update(λ, home_score, ...)   # Sobe λ se marcou
    lambda_full_away = bayesian_lambda_update(λ, away_score, ...)
...
if minute > 0:
    lambda_full_home, lambda_full_away, _ = adjust_lambdas(...)     # Cai λ se está ganhando
```
Bayesian aumenta λ do time que marcou. Momentum reduz λ desse mesmo time porque está ganhando. **Sinal "placar" contado duas vezes em direções opostas**, e o resultado depende dos coeficientes arbitrários.

### Problema 2 — Intensidade homogênea
`_half_lambdas` (linha 161): `lam_2h_h = λ_full × half/match_minutes`. Distribui λ uniformemente. Distribuição empírica de gols em jogos de Copa (e ligas em geral):

| Bucket | % gols esperada vs uniforme |
|---|---|
| 0-15' | -20% |
| 15-30' | -5% |
| 30-HT | +5% |
| 46-60' | -10% |
| 60-75' | +10% |
| 75-90+' | +30% |

### Problema 3 — Mercado ignorado
`ingest/superbet/parser.py` captura odds 1X2, Over/Under, BTTS ao vivo. `models/wc_inplay.py` nunca lê isso. Empiricamente, **odds de mercado ao vivo têm MAE menor que modelos estatísticos a partir do minuto ~45**.

## 4. Success Metrics

Baseline: rodar walk-forward in-play (será criado na Fase 2 com rigor, mas para esta fase usaremos **subset de jogos de Copa 2022 com timeline disponível**).

| Métrica | Baseline | Alvo |
|---|---|---|
| Brier `prob_final_*` (snapshots cada 15min) | medir | -0.005 a -0.010 |
| Brier `prob_next_goal_*` | medir | -0.010 a -0.020 |
| Latência `simulate_inplay()` p95 | medir | manter < +20% |
| MAE λ_remaining vs mercado (min 70') | medir | -30% |

## 5. Design Técnico

### 5.1 Sub-fase 1a — Inverter ordem Bayesian × Momentum

**Decisão:** Momentum age sobre **fatores táticos** (placar, vermelhos, subs); Bayesian age sobre **densidade de evidência** (gols observados ajustam λ). A ordem correta é:

```
λ_full_pré → momentum (placar/contexto) → λ_full_pós_momentum
                                       ↓
                       Bayesian update (gols observados) → λ_full_final
```

**Mas há um conflito conceitual:** Bayesian já assume que gols observados são amostras de λ_full. Se momentum **reduz** λ porque o time está ganhando, o Bayesian em cima vai ver "marcou mais do que esperado" e **reinflar**. Continua circular.

**Solução:** separar os papéis explicitamente.

- **Bayesian** atualiza λ_base a partir de **gols + tempo decorrido**, sem saber quem ganhou.
- **Momentum** ajusta λ_remaining (não λ_full) — afeta só o futuro, não o que já aconteceu.

```python
# DEPOIS:
lambda_full_h_post = bayesian_update(λ_full_h, home_score, minute, ...)
lambda_full_a_post = bayesian_update(λ_full_a, away_score, minute, ...)

lam_rem_h, lam_rem_a = _split_remaining(lambda_full_h_post, lambda_full_a_post, minute)

# Momentum só afeta λ_remaining:
lam_rem_h_adj, lam_rem_a_adj = apply_momentum(lam_rem_h, lam_rem_a, ctx)
```

### 5.2 Sub-fase 1b — Intensidade não-homogênea (NHPP)

Adicionar `pipelines/wc_intensity_profile.py`:

```python
# Pesos relativos por minuto (soma = match_minutes para preservar λ_full)
_GOAL_INTENSITY_BUCKETS = [
    (0, 15,  0.80),
    (15, 30, 0.95),
    (30, 45, 1.05),
    (45, 60, 0.90),
    (60, 75, 1.10),
    (75, 90, 1.20),
    (90, 95, 1.30),   # acréscimos
]

def integrated_intensity(start_min: int, end_min: int, match_minutes: int = 90) -> float:
    """Retorna a fração de λ_full integrada no intervalo [start, end]."""
```

Substituir em `wc_inplay.py:_half_lambdas`:
```python
# ANTES:
lam_2h_h = λ_full × half / match_minutes

# DEPOIS:
lam_2h_h = λ_full × integrated_intensity(minute, match_minutes) / total_weight
```

**Calibração inicial:** usar pesos da literatura (acima). Fase 2 estima por MLE.

### 5.3 Sub-fase 1c — Shrinkage com odds Superbet

Novo módulo `models/wc_market_shrinkage.py`:

```python
@dataclass
class MarketOdds:
    p_under_1_5: float | None = None
    p_under_2_5: float | None = None
    p_btts_no: float | None = None
    timestamp_minute: int = 0

def implied_lambdas_from_market(odds: MarketOdds, current_total: int) -> tuple[float, float] | None:
    """Resolve λ_h_rem, λ_a_rem que reproduzem as odds observadas via mínimos quadrados."""

def shrink_to_market(
    lam_h_rem: float, lam_a_rem: float,
    odds: MarketOdds | None,
    minute: int,
) -> tuple[float, float]:
    if odds is None:
        return lam_h_rem, lam_a_rem
    market = implied_lambdas_from_market(odds, ...)
    if market is None:
        return lam_h_rem, lam_a_rem
    alpha = _alpha_schedule(minute)  # 0.7 em min 0, 0.3 em min 80
    lam_h_final = alpha * lam_h_rem + (1 - alpha) * market[0]
    lam_a_final = alpha * lam_a_rem + (1 - alpha) * market[1]
    return lam_h_final, lam_a_final

def _alpha_schedule(minute: int, match_minutes: int = 90) -> float:
    """α decresce linearmente de 0.7 (min 0) até 0.3 (min 80)."""
    if minute <= 0: return 0.7
    if minute >= 80: return 0.3
    return 0.7 - 0.4 * (minute / 80)
```

### 5.4 Mudanças em arquivos existentes

| Arquivo | Mudança |
|---|---|
| `models/wc_inplay.py` | Reordenar `simulate_inplay`; injetar `market_odds` parâmetro; chamar `shrink_to_market` |
| `pipelines/wc_intensity_profile.py` | **Novo** — perfil temporal de intensidade |
| `models/wc_market_shrinkage.py` | **Novo** — shrinkage com mercado |
| `api/main.py` | Endpoint in-play passa odds correntes do `superbet_odds.json` |
| `pipelines/wc_hyperparams.py` | Adicionar `intensity_buckets`, `market_alpha_start`, `market_alpha_end` |

### 5.5 Feature flag

```python
# config/settings.py
inplay_use_nhpp: bool = True
inplay_use_market_shrinkage: bool = True
inplay_momentum_after_bayesian: bool = True  # nova ordem
```

Permite A/B em produção: rodar simulações com e sem cada feature, comparar Brier.

## 6. Plano de Implementação

### Dia 1–2 — Sub-fase 1a (ordem)
- [x] Refatorar `simulate_inplay` para aplicar momentum só em λ_remaining.
- [x] Momentum via `compute_momentum_calibrated` em λ_remaining (não λ_full).
- [x] Testes: `tests/test_inplay_phase1.py`.

### Dia 3 — Sub-fase 1b (NHPP)
- [x] `pipelines/wc_intensity_profile.py` com pesos iniciais.
- [x] `compute_half_lambdas_nhpp` integrado em `simulate_inplay`.
- [x] Teste: `tests/test_intensity_profile.py`.

### Dia 4–5 — Sub-fase 1c (shrinkage)
- [x] `models/wc_market_shrinkage.py`.
- [x] Heurística odds → λ + `shrink_lambda` com α(minute).
- [x] Integrado em `inplay_from_predictor`, `advice.py`, `api/main.py`.
- [x] Testes: `tests/test_market_shrinkage.py`.

### Dia 6 — Integração API + validação
- [x] `/worldcup/inplay` e `/worldcup/superbet/live/{id}/advice` passam odds Superbet.
- [x] Walk-forward A/B: `validate-inplay-phase1`.
- [ ] MLflow: logar Brier por variante (opcional).

### Dia 7 — Documentação + rollout
- [x] Feature flags em `config.py` (ligadas por padrão).
- [x] CLI `validate-inplay-phase1` para medir ganho vs baseline.

## 7. Test Plan

### Unit tests
- `tests/test_intensity_profile.py`: integração no intervalo total = match_minutes.
- `tests/test_market_shrinkage.py`: inversão de odds idempotente em casos sintéticos.
- `tests/test_inplay_order.py`: marcando gol no min 30 não duplica efeito.

### Property tests
- Para todo `minute ∈ [0, 90]`, `prob_final_home + prob_final_draw + prob_final_away ≈ 1.0`.
- Para placar muito desigual, `prob_no_more_goals` deve ser maior se `α(minute)` privilegia mercado.

### Integration test (golden)
- Jogo Brasil 4-1 Coreia 2022: snapshots a cada 15min, comparar com odds históricas Superbet (se disponíveis).

## 8. Rollback Plan

- Todas as 3 mudanças são **feature-flagged**. Reversão: setar flags `False` no `config/settings.py`.
- Modelo pré-jogo intocado — risco zero para `/predict`.
- Endpoint in-play continua aceitando chamadas sem `market_odds` (fallback transparente).

## 9. Riscos

| Risco | Mitigação |
|---|---|
| Odds Superbet com latência alta | Adicionar `max_odds_age_seconds`; se odds > 60s, ignorar shrinkage |
| Mercado ineficiente em ligas pequenas | Reduzir α para casos non-WC (fora do escopo) |
| Pesos NHPP da literatura não baterem com Copa | Aceitar como aproximação na Fase 1; calibrar em Fase 2 |
| Refatoração de ordem quebra testes existentes | Manter `bayesian_update=False` como flag de compat. |

## 10. Definition of Done

- [x] As 3 sub-fases mergeadas atrás de feature flag (`config.py`).
- [x] Walk-forward in-play reporta Brier para cada combinação de flags (`validate-inplay-phase1`).
- [ ] Latência p95 do endpoint documentada antes/depois (medir em produção).
- [x] Sub-fases 1a, 1b e 1c ligadas por padrão em dev.
- [x] Shrinkage ativo quando odds Superbet disponíveis no advice/inplay.
