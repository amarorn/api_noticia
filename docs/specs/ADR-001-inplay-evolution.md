# ADR-001: Evolução do Modelo In-Play

**Status:** Accepted (specs derivadas)
**Date:** 2026-06-09
**Deciders:** amaro
**Specs:** Fases [0](spec-fase-0-reorganizacao.md), [1](spec-fase-1-quickwins-inplay.md), [2](spec-fase-2-momentum-calibrado.md), [3](spec-fase-3-modelo-avancado.md)

---

## Context

Modelo in-play (`models/wc_inplay.py`) combina Monte Carlo Poisson + Bayesian update + Momentum determinístico. Análise revelou:

1. **Treino in-play não existe** — coeficientes do momentum são chutados.
2. **Ordem Bayesian/Momentum causa dupla contagem** do sinal de placar.
3. **Intensidade de gols modelada como homogênea** no tempo — empiricamente falsa.
4. **Odds Superbet capturadas mas não usadas** para calibrar λ.
5. **Calibração de probabilidades é medida mas não aplicada.**

Modelo pré-jogo (Dixon-Coles + Logística + Ensemble Colaborativo) tem walk-forward correto e métricas adequadas — não é o problema.

## Decision

Evoluir o in-play em **4 fases incrementais**, cada uma com spec executável independente, métricas de aceitação claras, e rollback plan. Cada fase só inicia quando a anterior está medida e em produção.

| Fase | Foco | Esforço | Ganho esperado |
|---|---|---|---|
| 0 | Pipeline reproduzível + Platt scaling | 3 dias | Reproducibilidade + ECE -30% |
| 1 | Inverter ordem + NHPP + Shrinkage mercado | 1 semana | Brier -0.005~0.010 |
| 2 | MLE momentum e NHPP com timeline histórica | 2 semanas | Substitui chutes por dados |
| 3 | Hawkes + LightGBM + Ensemble stacking | 4-6 semanas | Brier -0.005~0.015 adicional |

## Consequences

**Fica mais fácil:**
- Reproduzir treino com 1 comando
- Medir contribuição de cada componente isoladamente
- Reverter mudanças via feature flags

**Fica mais difícil:**
- Pipeline de timeline minuto-a-minuto precisa de manutenção
- Mais artefatos versionados (calibrator + coefficients + GBM)
- Latência do endpoint cresce com ensemble

**Revisitar depois:**
- Pesos do `wc_collaborative` provavelmente mudam após Fase 0
- `wc_live_momentum.py` será reescrita na Fase 2
- Estrutura do `WcArtifact` precisa versionamento

## Princípios não-negociáveis

1. **Sem regressão silenciosa**: toda mudança passa por walk-forward antes de produção.
2. **Feature flags por componente**: rollback sempre possível.
3. **Coeficientes calibrados > chutados**: não aceitar constantes mágicas em Fase 2+.
4. **Brier como métrica oficial**: acurácia é métrica secundária.
5. **Mercado como referência, não como modelo**: shrinkage controlado, não imitação.
