# Roadmap — Plataforma ML (melhoria contínua)

North star: **Brier in-play vs mercado** e **P&L operacional reconciliado** — visível em `/modelos` e `/carteira`.

Última revisão: **2026-06-11**.

---

## Status por fase

Legenda: ✅ feito · 🟡 parcial · ❌ pendente

### Fase A — Quick wins (semanas 1–2)

| Item | Status | Evidência / notas |
|------|--------|-------------------|
| Corrigir empates WC | ✅ | `resolve_wc_outcome()` em `models/wc_draw_model.py`; rodada 2026: **6×X** (antes 0×X) |
| Cron `poll-superbet-live` para eventos WC | 🟡 | `POLL_WC_COPA=true` + `./scripts/install-platform-cron.sh` |
| Upload CSV semanal automático | 🟡 | Inbox semi-auto: `watch-wallet-csv` + hook pós-jogo; export Superbet ainda manual |
| Dashboard `/modelos` como north star | ✅ | `ModelBenchmarkPage`, `GET /worldcup/benchmarks/history`, histórico em `data/lake/reports/model_benchmark_history.json` |

### Fase B — Dados vivos (semanas 3–6)

| Item | Status | Evidência / notas |
|------|--------|-------------------|
| Ingest Sofascore live → `silver/inplay/match_states` | 🟡 | `ingest/sofascore/live_momentum.py`, `pipelines/inplay_match_states.py`, CLI `build-inplay-states`; ~917 ticks, 40 eventos, **2 labeled** |
| Bayesian λ update integrado em `wc_inplay.py` | 🟡 | Bayesian ativo; **ajuste por placar** liga com eventos Sofascore (`INPLAY_SCORE_LAMBDA_ADJUST_WITH_SOFASCORE=true`) |
| Expandir `live_ticks` com xG/cartões do snapshot | 🟡 | xG + posse Sofascore no Parquet; cartões/escanteios via snapshot |

### Fase C — Loop fechado (semanas 7–10)

| Item | Status | Evidência / notas |
|------|--------|-------------------|
| 500+ exemplos reconciliados | ❌ | **93** alta confiança CSV; ticks rotulados alimentam GBM via `inplay_synthetic_feedback` |
| Feedback GBM aceito em produção | ❌ | ~93 ex.; gate rejeita retreino (delta Brier +0,00015) |
| A/B: Poisson puro vs Poisson+GBM stack | 🟡 | Shadow A/B em `live_ticks` (`ens_prob_*`); gate `check-inplay-ensemble`; API `/worldcup/inplay/ensemble-status` + card em `/modelos` |

### Fase D — Escala (semanas 11–12)

| Item | Status | Evidência / notas |
|------|--------|-------------------|
| `LAKE_PRIMARY=cloud` + sync GCS (backup, CI) | 🟡 | Dev `local`; `scripts/lake-cloud-backup.sh` + cron domingo (`sync-gcp --layer all`) |
| Retreino automático pós-evento | 🟡 | gold + inbox + settle open bets + retreino; reconcile sobre CSV em bronze |
| Relatório semanal P&L vs Brier | 🟡 | `weekly-pl-report` + backtest filtros (`backtest-inplay-filters`) |

---

## Carteira pós-partida — análise e plano

### O que já acontece quando a partida termina

Fluxo em `maybe_finalize_finished_event()` (`ingest/superbet/event_finalize.py`):

```
Superbet FINISHED → gold/superbet/events/{id}/final.json
                 → silver/inplay/match_states (upsert)
                 → settle user_open_bets → user_settled_bets.json
                 → wallet inbox import (se CSV na pasta)
                 → merge odds pós-jogo
                 → fila background: reconcile → retrain-with-feedback → train-inplay-gbm
```

**Importante:** o passo `reconcile_user_transactions()` **reprocessa** transações que já estão em `bronze/user_transactions/`. Ele **não baixa** um CSV novo da Superbet.

### O que já temos para dados de carteira

| Fonte | O que captura | Automático? |
|-------|---------------|-------------|
| CSV Superbet (upload manual) | Extrato completo: bilhetes, ganhos, P&L | ❌ manual |
| Extensão Chrome `superbet-capture` | Apostas **abertas** → `user_open_bets.json` | Semi (1 clique na aba Minhas Apostas) |
| `live_ticks.parquet` + snapshots | Probabilidades do modelo no momento da aposta | ✅ via poll |
| Reconciliação heurística | Emparelha bilhete ↔ tick (±5 min, TZ SP) | ✅ se CSV existir |

**Não existe** endpoint público Superbet para exportar carteira/transações no nosso `ingest/superbet/client.py`.

### Caminhos viáveis (do mais rápido ao mais robusto)

#### 1. Watch folder CSV (recomendado — Fase A+)

Usuário exporta CSV na Superbet (mesmo fluxo de hoje) e salva em pasta monitorada:

```text
data/lake/inbox/wallet/{user_id}/*.csv
```

Cron ou hook pós-`event_finalize`:

1. `upload-user-csv --file … --user …`
2. `reconcile_user_transactions(user_id)`
3. Invalidar cache `/carteira`

**Esforço:** ~1 dia. **Dependência humana:** exportar CSV (1× por semana ou após rodada).

#### 2. Liquidação automática de apostas abertas (complementar — Fase B)

Quando `event_finalize` grava placar final:

1. Ler `user_open_bets.json` (extensão já populou durante o jogo)
2. Marcar apostas do `event_id`/nome do jogo como **settled** com resultado derivado do placar
3. Alimentar analytics P&L parcial **sem** CSV completo

**Esforço:** ~2 dias. **Limitação:** não substitui extrato oficial (cash-out parcial, combos, taxas).

#### 3. Extensão v2 — histórico de transações (médio prazo — Fase B/C)

Estender `extensions/superbet-capture` para a página de **histórico/extrato** (não só apostas abertas):

- Scrape DOM → JSON/CSV normalizado → `POST /user/transactions/upload`
- Opcional: disparar após notificação da API (`GET /worldcup/superbet/pending-wallet-sync`)

**Esforço:** ~3–5 dias. **Risco:** DOM da Superbet muda (mesmo risco da v1).

#### 4. Labels sintéticos só para GBM (paralelo — Fase C)

Para **treino de modelo** (não P&L operacional):

- Usar ticks + placar final em `gold/…/final.json` como labels
- Reduz dependência de CSV para fechar loop GBM; mantém CSV para `/carteira` e auditoria

**Esforço:** ~2–3 dias. Já parcialmente coberto por `find_global_tick_for_bet()`.

#### 5. API autenticada Superbet (longo prazo — não priorizar)

Reverse-engineering de endpoints web com cookie/sessão do usuário. Frágil (ToS, 2FA, rate limit).

---

## Itens novos no roadmap (prioridade sugerida)

### Fase A+ — Carteira semi-automática (inserir antes de escalar Fase C)

| # | Entrega | Fase | Esforço |
|---|---------|------|---------|
| A+1 | **Watch folder** `inbox/wallet` + CLI `watch-wallet-csv` | A+ | ✅ |
| A+2 | Hook pós-`event_finalize`: inbox → upload + reconcile | A+ | ✅ |
| A+3 | Banner `/carteira`: "CSV desatualizado — último upload há N dias" | A+ | ✅ |
| A+4 | Lembrete semanal (cron + log) para exportar CSV | A | ✅ |

### Fase B+ — Carteira durante o jogo

| # | Entrega | Fase | Esforço |
|---|---------|------|---------|
| B+1 | **Settle** `user_open_bets` no `event_finalize` | B+ | ✅ |
| B+2 | Extensão v2: captura histórico → upload API | B/C | ✅ |
| B+3 | Endpoint `GET /user/wallet/sync-status` | B+ | ✅ |

### Métricas alvo (inalteradas)

| Métrica | Atual (ref.) | Meta |
|---------|--------------|------|
| Reconciliação alta confiança | 93 | ≥ 500 |
| Match rate (≥0,5) | ~47% | ≥ 60% |
| Brier in-play vs mercado | 0,078 vs 0,108 | manter gap ≥ 0,02 |
| Feedback GBM aceito | não | ≥ 1 promoção em prod |

---

## Próximos passos recomendados

1. **Implementar A+1–A+2** (watch folder) — maior ROI com menor risco
2. Corrigir poll WC (cron em vez de launchd, ou mover repo fora de `Documents/`)
3. Ativar `inplay_score_lambda_adjust` quando Sofascore events presentes
4. Acumular CSV + poll até 500 exemplos; `check-inplay-ensemble` indica quando desligar `inplay_ensemble_shadow_mode`
5. Relatório semanal (`scripts/weekly-pl-report.sh` → JSON + e-mail/log)

---

## Referências

- Feedback loop: [feedback-loop-aposta-modelo.md](feedback-loop-aposta-modelo.md)
- Spec Fase 4: [specs/spec-fase-4-feedback-loop.md](specs/spec-fase-4-feedback-loop.md)
- Finalização evento: `ingest/superbet/event_finalize.py`
- Extensão captura: `extensions/superbet-capture/README.md`
- Benchmark histórico: `pipelines/model_benchmark_history.py`, `/modelos`
