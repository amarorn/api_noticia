# Super Múltipla — Bolão AI

Sistema de **odds combinadas** com promo **Super Múltipla** (+5% no retorno quando todas as pernas têm odd ≥ 1,35), integrado ao painel ao vivo Superbet.

## Escopo

O Bolão AI é **copiloto analítico** — não coloca apostas na Superbet. O fluxo é:

1. Calcular / validar múltipla (modelo × mercado)
2. Montar na Superbet manualmente ou via extensão Chrome
3. Registrar em `POST /user/open-bets` para tracking e cash-out

## API

### `POST /worldcup/superbet/multiple/calculate`

Cálculo stateless de slip (sem sessão server-side).

**Request (exemplo):**

```json
{
  "legs": [
    {
      "market": "h2h",
      "outcome": "1",
      "market_odd": 1.80,
      "model_prob": 0.58,
      "superbet_event_id": 13127506,
      "is_live": true,
      "minute": 23
    },
    {
      "market": "over_2_5",
      "outcome": "yes",
      "market_odd": 2.10,
      "model_prob": 0.52,
      "superbet_event_id": 13127506,
      "is_live": true
    }
  ],
  "stake": 5.0,
  "bet_type": "MULTIPLE",
  "minute": 23,
  "home_score": 0,
  "away_score": 0
}
```

**Response:** `total_odds`, `potential_payout`, `bonus_eligible`, `bonus_percentage`, `final_payout`, `combined_prob`, `combined_ev`, `warnings`, `builder_validation`.

### `GET /worldcup/superbet/live/{event_id}/advice`

Quando `fast=false`, inclui bloco `super_multipla`:

```json
{
  "super_multipla": {
    "min_leg_odd_for_bonus": 1.35,
    "bonus_pct": 0.05,
    "default_stake": 10.0,
    "suggested_combos": [...]
  }
}
```

### `POST /user/open-bets`

Para `len(picks) >= 2`, recalcula automaticamente bônus e persiste `bonus_eligible`, `bonus_percentage`, `final_payout`.

## Regras de negócio

| Regra | Valor | Config |
|-------|-------|--------|
| Odd mínima por perna | 1,01 | validação schema |
| Odd mínima promo Super Múltipla | 1,35 | `SUPER_MULTIPLA_MIN_LEG_ODD` |
| Bônus no retorno | +5% | `SUPER_MULTIPLA_BONUS_PCT` |
| Stake máxima | R$ 50 (default) | `BET_MAX_STAKE` |
| Overround extra | **não aplicado** | odd já é da Superbet |

## Validações cruzadas

- **Criar Aposta (mesmo evento):** `validate_bet_builder()` por grupo de pernas
- **Proposta Bolão:** `validate_combo_proposal()` exige EV combinado > 0
- **Guardrail P0:** após `live_block_minute` (45'), warning em novas múltiplas ao vivo

## Frontend

| Componente | Descrição |
|------------|-----------|
| `LiveSuperMultiplaPanel` | Slip interativo em `/ao-vivo/:eventId` |
| `LiveBestCombosPanel` / `LiveLongshotCombosPanel` | Badge +5% quando elegível |
| `useSuperMultiplaSlip` | Hook com React Query → `calculate` |

## Módulos Python

| Arquivo | Responsabilidade |
|---------|------------------|
| `models/super_multipla.py` | Cálculo puro + enrich cadastro |
| `models/super_multipla_suggestions.py` | Sugestões a partir do `market_scan` |
| `schemas/super_multipla.py` | Contratos Pydantic |

## Testes

```bash
pytest tests/test_super_multipla.py tests/test_super_multipla_suggestions.py -q
```
