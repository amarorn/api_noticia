# Spec-Driven Roadmap — Evolução do Modelo In-Play

Este diretório contém as **specs de execução** (spec-driven development) para a evolução do modelo in-play, derivadas do [ADR-001](../../ADR-001-inplay-evolution.md).

Cada fase tem uma spec independente, com:
- **Goal & Non-goals** (escopo claro)
- **Success metrics** (como saber se funcionou)
- **Design técnico** (interfaces, contratos, mudanças de arquivo)
- **Plano de implementação** (tarefas verificáveis)
- **Test plan** (como validar antes de mergear)
- **Rollback plan** (como reverter se quebrar)

## Ordem de execução

| Fase | Spec | Duração | Ganho esperado | Status |
|------|------|---------|----------------|--------|
| **0** | [spec-fase-0-reorganizacao.md](spec-fase-0-reorganizacao.md) | 3 dias | Unifica entrada de treino + Platt scaling | 📝 Proposed |
| **1** | [spec-fase-1-quickwins-inplay.md](spec-fase-1-quickwins-inplay.md) | 1 semana | Brier in-play -0.005~0.010 | 📝 Proposed |
| **2** | [spec-fase-2-momentum-calibrado.md](spec-fase-2-momentum-calibrado.md) | 2 semanas | Substitui chutes por MLE | 📝 Proposed |
| **3** | [spec-fase-3-modelo-avancado.md](spec-fase-3-modelo-avancado.md) | 1 mês+ | Hawkes + GBM ensemble | 📝 Proposed |

## Princípio guia

Cada fase **só começa quando a anterior tem métrica de Brier reportada e calibração medida**. Não há atalhos: sem baseline, não dá pra dizer se a fase seguinte agregou.

## Convenções

- Toda fase logga em **MLflow** (`models.<fase>.<run_id>`).
- Toda mudança de modelo passa por **walk-forward** antes de ir pra produção.
- Toda spec tem **rollback plan** — produção não pode ficar sem fallback.
- Constantes "mágicas" novas vão para `pipelines/wc_hyperparams.py`, não hardcoded.
