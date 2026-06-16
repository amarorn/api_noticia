# Feedback Loop — Aposta × Modelo (Fase 4)

Fecha o ciclo entre apostas reais (CSV Superbet) e predições do modelo in-play.

## Fluxo

```
CSV Superbet → POST /user/transactions/upload
            → bronze/user_transactions/
            → POST /user/transactions/reconcile
            → silver/bet_reconciliation/reconciliation_{user}.parquet
            → GET /user/transactions/summary|reconciliation|model-errors
            → Frontend /carteira
            → retrain-with-feedback (opcional, gate Brier)
```

## Comandos

```bash
# Upload via CLI
upload-user-csv --file extrato.csv --user jamarorn

# Inbox semi-automática (exporte CSV na Superbet → salve na pasta)
# data/lake/inbox/wallet/jamarorn/extrato.csv
watch-wallet-csv --user jamarorn
./scripts/watch-wallet-cron.sh jamarorn

# Reconciliar + validar
validate-inplay-phase4 --user jamarorn --csv extrato.csv --json

# Retreino GBM com feedback (só aceita se Brier melhorar ≥ 0.002)
retrain-with-feedback --user jamarorn --min-confidence 0.7
```

## Reconciliação

Para cada `bilhete colocado` in-play:

1. Emparelha com `valor ganhado` (janela 4h).
2. Busca snapshot em `bronze/superbet/events/{event_id}/` (±3 min, UTC).
3. Enriquece com `live_ticks.parquet` (`prob_final_*` do modelo).
4. Calcula `brier_contribution` e `match_confidence`.

Alvo: ≥ 60% dos bilhetes com `match_confidence ≥ 0.7`.

## Frontend

`/carteira` — upload CSV, KPIs, gráficos P&L, tabela reconciliada, heatmap de erros.

## Config

```env
WALLET_DASHBOARD_ENABLED=true
```

## Limitações

- CSV não traz `event_id` nem mercado explícito — match heurístico por tempo.
- Retreino GBM usa target aproximado (won/lost por placar).
- Dados locais (`LAKE_PRIMARY=local`); não sincroniza GCS por padrão.
