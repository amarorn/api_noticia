# Prompt Técnico: Implementação de Handicap Asiático no Bolão AI

## Contexto
O Bolão AI é um sistema de previsões esportivas com modelos estatísticos (Poisson, Dixon-Coles, regressão logística) e integração ao vivo com a Superbet. Atualmente predizemos 1X2, Over/Under e BTTS. Precisamos adicionar **Handicap Asiático** como novo mercado.

## Objetivo
Implementar cálculo de probabilidades de handicap asiático usando a distribuição de gols já existente (Poisson bivariada com correlação ρ do Dixon-Coles), integrar ao pipeline de ao vivo (Superbet) e exibir no frontend.

---

## 1. Backend — Modelo de Handicap

### 1.1 Criar `models/wc_handicap.py`

```python
"""Modelo de Handicap Asiático baseado em simulação Monte Carlo."""

import numpy as np
from typing import Literal


def simulate_handicap_probabilities(
    home_lambda: float,
    away_lambda: float,
    rho: float = -0.13,
    max_goals: int = 10,
    n_simulations: int = 50_000,
) -> dict[str, float]:
    """
    Simula placares via Poisson bivariada (Dixon-Coles) e calcula
    probabilidades de cobertura para linhas de handicap comuns.

    Args:
        home_lambda: Taxa de gols esperada do mandante.
        away_lambda: Taxa de gols esperada do visitante.
        rho: Correlação de Dixon-Coles (default -0.13 para baixo placar).
        max_goals: Máximo de gols para truncar distribuição.
        n_simulations: Número de simulações Monte Carlo.

    Returns:
        Dict com chaves no formato "home_-1.5", "away_+1.5", etc.
    """
    # TODO: Implementar simulação com correlação ρ
    # Dica: usar rejection sampling ou copula para Poisson bivariada
    pass


def calculate_handicap_ev(
    model_prob: float,
    odd: float,
) -> float:
    """Expected Value para handicap: EV = P_modelo × ODD - 1."""
    return model_prob * odd - 1.0


def kelly_stake(
    model_prob: float,
    odd: float,
    bankroll: float,
    fraction: float = 0.25,
) -> float:
    """Kelly fraction para handicap, com fração conservadora."""
    if odd <= 1.0:
        return 0.0
    edge = model_prob - (1.0 / odd)
    kelly = edge / (1.0 - (1.0 / odd))
    return max(0.0, bankroll * kelly * fraction)
```

### Requisitos técnicos:
- Usar **scipy.stats.skellam** para distribuição da diferença de gols quando ρ ≈ 0
- Para ρ ≠ 0, usar **simulação Monte Carlo** com estrutura de dependência
- Truncar em max_goals=10 (suficiente para λ < 5)
- Cachear resultados por (home_lambda, away_lambda, rho) com LRU

---

## 2. Integração ao Pipeline Ao Vivo

### 2.1 Estender `models/wc_inplay.py`

Adicionar ao `simulate_inplay()`:

```python
# Após calcular probFinalHome, probFinalDraw, probFinalAway:
handicap_lines = [-2.5, -1.5, -0.5, 0, +0.5, +1.5, +2.5]
handicap_probs = {}

for line in handicap_lines:
    # Simular distribuição de gols condicionada ao placar atual + tempo restante
    home_adj, away_adj = adjust_lambda_for_score(
        home_lambda, away_lambda, 
        current_score, minute, phase
    )
    probs = simulate_handicap_probabilities(home_adj, away_adj, rho)
    handicap_probs[f"H{line}"] = probs.get(f"home_{line}", 0)
    handicap_probs[f"A{line}"] = probs.get(f"away_{line}", 0)

# Retornar no inplay_summary
```

### 2.2 Estender `ingest/superbet/parser.py`

No `SuperbetEventSnapshot`, adicionar parsing de mercados de handicap:

```python
# No parser de mercados:
if market.get("name", "").lower() in ["asian handicap", "handicap asiatico", "ah"]:
    for selection in market.get("selections", []):
        line = parse_handicap_line(selection["name"])  # ex: "-1.5"
        outcome = "home" if selection.get("type") == "1" else "away"
        snapshot.handicap_odds[f"{outcome}_{line}"] = selection["odds"]
```

---

## 3. API — Novo Endpoint

### 3.1 Adicionar a `api/main.py`

```python
@router.get("/worldcup/handicap/{event_id}")
async def get_handicap_analysis(
    event_id: int,
    bankroll: float = Query(default=1000.0, ge=10.0),
    phase: str = Query(default="group"),
) -> HandicapAnalysisResponse:
    """
    Retorna análise completa de handicap para um evento.

    Inclui:
    - Probabilidades modelo para cada linha (-2.5 a +2.5)
    - Odds da Superbet para comparação
    - EV e Kelly stake para edges positivos
    - Recomendação de aporte
    """
    pass
```

### 3.2 Schema Pydantic (`schemas/models.py`)

```python
class HandicapLine(BaseModel):
    line: float  # -1.5, +0.5, etc.
    side: Literal["home", "away"]
    model_prob: float
    superbet_odd: float | None
    ev: float
    kelly_stake: float
    recommendation: Literal["bet", "avoid", "watch"]

class HandicapAnalysisResponse(BaseModel):
    event_id: int
    home_team: str
    away_team: str
    current_score: str
    minute: int
    lines: list[HandicapLine]
    best_bet: HandicapLine | None
    timestamp: datetime
```

---

## 4. Frontend — Exibição

### 4.1 Novo componente: `LiveHandicapPanel.tsx`

```tsx
interface LiveHandicapPanelProps {
  lines: HandicapLine[];
  homeTeam: string;
  awayTeam: string;
}

export function LiveHandicapPanel({ lines, homeTeam, awayTeam }: LiveHandicapPanelProps) {
  // Agrupar por linha: mostrar Home -1.5 | Away +1.5 lado a lado
  // Destacar edges positivos (EV > 0) com cor neon-green
  // Mostrar barra de probabilidade modelo vs implícita da odd
}
```

### 4.2 Integrar ao `LiveInPlayPage.tsx`

Adicionar seção após "Mercados 2T viáveis":

```tsx
{/* ── Handicap Asiático ── */}
<section className="glass-card p-3">
  <div className="flex items-center gap-2 mb-3">
    <span className="font-mono text-[10px] text-neon-blue">:: HANDICAP</span>
    <span className="h-px flex-1 bg-gradient-to-r from-neon-blue/20 to-transparent" />
  </div>
  <LiveHandicapPanel 
    lines={data.handicapLines} 
    homeTeam={data.homeTeam} 
    awayTeam={data.awayTeam} 
  />
</section>
```

### 4.3 Design do card de linha

```
┌─────────────────────────────────────────┐
│  Home -1.5        │  Away +1.5          │
│  @2.10            │  @1.75              │
│  Modelo: 52%      │  Modelo: 48%        │
│  [██████░░░░]     │  [█████░░░░░]       │
│  EV: +9.2% ✓      │  EV: -4.0% ✗        │
│  Stake: R$ 23     │                     │
└─────────────────────────────────────────┘
```

---

## 5. Testes

### 5.1 Testes unitários (`tests/test_wc_handicap.py`)

```python
def test_handicap_simulation_symmetry():
    """P(home -1.5) + P(away +1.5) ≈ 1 (com tolerância para empates em linhas inteiras)."""
    probs = simulate_handicap_probabilities(1.8, 1.2, rho=-0.13)
    assert abs(probs["home_-1.5"] + probs["away_+1.5"] - 1.0) < 0.01

def test_handicap_ev_calculation():
    """EV = P × O - 1."""
    assert calculate_handicap_ev(0.5, 2.2) == pytest.approx(0.1)

def test_kelly_never_negative():
    """Kelly stake é 0 quando edge é negativo."""
    assert kelly_stake(0.4, 2.0, 1000) == 0.0
```

---

## 6. Critérios de Aceitação

- [ ] `simulate_handicap_probabilities()` retorna probabilidades para linhas -2.5 a +2.5
- [ ] Soma de P(home_H) + P(away_H) ≈ 1.0 para linhas meio-gol (±0.01)
- [ ] Para linhas inteiras (0, ±1, ±2), empate = stake devolvida (soma pode ser < 1)
- [ ] Endpoint `/handicap/{event_id}` responde em < 500ms (com cache)
- [ ] Frontend mostra linhas em grid responsivo (2 colunas mobile, 4 desktop)
- [ ] Edges positivos (EV > 0.05) destacados com badge verde
- [ ] Testes passando: `pytest tests/test_wc_handicap.py -v`

---

## Referências

1. **Dixon-Coles original**: Dixon, M. J., & Coles, S. G. (1997). Modelling association football scores and inefficiencies in the football betting market.
2. **penaltyblog**: `pip install penaltyblog` — já tem `asian_handicap()` implementado
3. **Wager Optimiser**: github.com/Jack-cky/Wager-Optimiser — modelo de 2 camadas para handicap

## Notas

- Usar **fração Kelly 0.25** (conservador) para stakes
- Handicap de **gol inteiro** (0, ±1, ±2): empate = push (stake devolvida)
- Handicap de **meio-gol** (±0.5, ±1.5): sempre resultado binário
- **Quarter goals** (±0.25, ±0.75): versão futura, não obrigatória agora
