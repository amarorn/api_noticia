# Spec — Fase 4: Reconciliação Aposta-Modelo

**Status:** Accepted (implementada 2026-06-10)
**Depende de:** Fases 0–3 (Hawkes + GBM + Ensemble já em produção)
**Habilita:** Calibração contínua baseada no histórico real do usuário

---

## 1. Goal

Fechar o loop entre **aposta real do usuário** e **predição do modelo** para:

1. Dar visibilidade financeira didática: **quanto ganhou, quanto perdeu, quando, em que tipo de aposta**.
2. Identificar **padrões sistemáticos de erro do modelo** cruzando com snapshots históricos (`bronze/superbet/events/<event_id>/<timestamp>.json`).
3. Gerar um **dataset de calibração supervisionada** que alimenta retreino do ensemble (Fase 3).
4. Aumentar a precisão do modelo nos buckets onde ele mais erra, medido por Brier por segmento.

## 2. Non-goals

- ❌ Não vira plataforma de gestão de banca completa (Kelly avançado, multi-conta, etc.).
- ❌ Não tenta inferir bilhetes não capturados — só processa o que está no CSV.
- ❌ Não integra com Pix/banco para reconciliar depósitos.
- ❌ Não muda a arquitetura do modelo Fase 3 — só alimenta retreino com dados melhores.

## 3. Motivação

O CSV de transações da Superbet tem informação que **hoje não capturamos**:
- Bilhetes confirmados, cancelados, valores ganhos por timestamp exato.
- Saldo antes/depois → permite reconstruir P&L real por bilhete.

Hoje:
- `data/lake/bronze/superbet/events/<event_id>/*.json` tem ~50 snapshots por jogo (a cada ~2min).
- `user_open_bets.json` só guarda apostas registradas via extensão/API.

O **gap**: nunca cruzamos uma aposta real (que ganhou ou perdeu) com o snapshot do jogo no minuto da aposta. Sem isso, o modelo continua treinando em features sintéticas (Fase 3 usa goals reconstruídos via NHPP) e nunca aprende com **a calibração real** do mercado naquele momento.

Esta fase fecha esse loop.

## 4. Success Metrics

| Métrica | Baseline | Alvo |
|---|---|---|
| % de bilhetes do CSV reconciliados com snapshot do evento | 0% | ≥ 60% |
| Brier por bucket de minuto/score (medido) | ainda não medido | reportar e baseline |
| Brier após retreino com dataset de feedback | Fase 3 atual | -0.003 |
| ROI simulado vs ROI real do usuário (delta) | desconhecido | ≤ 5pp de gap |
| Tempo de upload + processamento de CSV (200 linhas) | — | < 3s |

## 5. Design Técnico

### 5.1 Fluxo geral

```
Usuário CSV → POST /user/transactions/upload
            → Parser → Bronze Parquet
            → Reconciliador (match com bronze/superbet/events/)
            → Silver Parquet (silver_bet_reconciliation)
            → Frontend /carteira (KPIs, gráficos, tabela)
            → Pipeline retreino (feedback_retrain.py)
            → Modelo Fase 3 atualizado
```

### 5.2 Schema das transações (bronze)

`schemas/user_transaction.py`:

```python
class UserTransactionRow(BaseModel):
    transaction_at: datetime
    transaction_type: str
    payment_method: str | None
    amount: float
    cash_balance: float
    cash_balance_prev: float
    bonus_balance: float
    bonus_balance_prev: float
    game_name: str
    user_id: str
    upload_id: str
```

Particionamento: `data/lake/bronze/user_transactions/user=<id>/year=<>/month=<>/transactions_<upload_id>.parquet`.

### 5.3 Reconciliação

Heurística: para cada `bilhete colocado`, varrer `bronze/superbet/events/` e procurar snapshot mais próximo dentro de ±2 min com `is_live=true`. Score por proximidade temporal + match de odds.

### 5.4 Endpoints

- `POST /user/transactions/upload` (multipart CSV)
- `GET /user/transactions/summary` (KPIs)
- `GET /user/transactions/reconciliation` (tabela paginada)
- `GET /user/transactions/model-errors` (heatmap data)

### 5.5 Frontend `/carteira`

Componentes: `CsvDropzone`, `WalletKpiCards`, `BalanceChart`, `BetTypePie`, `DailyPnlBars`, `ReconciliationTable`, `ModelErrorHeatmap`.

### 5.6 Feedback retrain

`pipelines/feedback_retrain.py` combina dataset sintético (Fase 3) com exemplos reais reconciliados. Gate: aceita só se `Brier_novo < Brier_atual - 0.002`.

## 6. Plano de Implementação

- [x] **Marco A**: upload + parser + `upload-user-csv`.
- [x] **Marco B**: reconciliação + enrich `live_ticks`.
- [x] **Marco C**: analytics + endpoints summary/reconciliation/model-errors.
- [x] **Marco D**: frontend `/carteira` + nav.
- [x] **Marco E**: `retrain-with-feedback` + `validate-inplay-phase4`.

## 7. Test Plan

- Unit: parser CSV, reconciliação com fixtures sintéticas, analytics.
- Integration: upload via TestClient, endpoints retornam estrutura correta.
- Backtest: CSV real do `jamarorn` deve reportar ≥ 60% match e P&L bater com saldo final.

## 8. Rollback Plan

- Feature flag `wallet_dashboard_enabled` em config.
- Gate de aceitação automático no retreino.
- Bronze é gitignored e regenerável.

## 9. Riscos

| Risco | Mitigação |
|---|---|
| CSV sem `event_id`/`ticket_code` → match heurístico falso | `match_confidence` ≥ 0.7 obrigatório para retreino |
| Inferência de mercado ambígua | Top-3 candidatos + flag "ambíguo" |
| LGPD/PII no CSV | Local-only; nunca subir para GCS por padrão |
| Retreino piora modelo | Gate por Brier delta automático |

## 10. Definition of Done

- [x] Upload CSV via API e `upload-user-csv`.
- [x] Tela `/carteira` com P&L, gráficos, tabela, heatmap.
- [ ] ≥ 60% bilhetes com `match_confidence ≥ 0.7` (medir após CSV real + ticks).
- [x] Brier por bucket (`compute_model_errors_heatmap`).
- [x] `retrain-with-feedback` com gate Brier.
- [x] `validate-inplay-phase4`.
- [x] Documentação em `docs/feedback-loop-aposta-modelo.md`.
- [x] `tests/test_user_wallet_phase4.py` (15 testes).
