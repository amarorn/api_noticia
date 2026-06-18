# Análise: Modelo In-Play vs Superbet — Onde Estamos e Onde Podemos Melhorar

> Data: 2026-06-08 · **Atualização status: 2026-06-17**
> Analista: Verdent
> Branch: `feature/superbet-live-inplay`

---

## 0. Status de implementação (2026-06-17)

| Item doc | Status | Onde |
|----------|--------|------|
| **P0** Bayesian update λ | ✅ Feito | `models/wc_inplay.py` → `bayesian_lambda_update` |
| **P0** Linha garantida (totals) | ✅ Feito | `_apply_guaranteed_lines`, `_apply_team_guaranteed_lines` |
| **P0** Mercados mortos BTTS/Over | ✅ Feito | `models/inplay_dead_market.py` + filtro em `wc_bet_advice` |
| **P1** Momentum placar/minuto/eventos | ✅ Feito | `models/wc_live_momentum.py` |
| **P1** Time decay / threshold por minuto | ✅ Feito | `config.py` (`live_midgame_*`, `live_late_game_*`) |
| **P1** λ ao vivo (posse, SOT, timeline) | ✅ Feito | `models/wc_inplay_live_adjust.py` + ScoreAlarm |
| **P1** Cash-out + momentum de mercado | ✅ Feito | `apply_trend_to_cashout` ← `wc_trend_advisor` |
| **P2** xG Sofascore calibrando λ pré-jogo | ✅ Feito | `models/xg_lambda_blend.py` → `goal_model_factors` / `inplay_from_predictor` |
| **P2** Eventos Sofascore ao vivo | 🟡 Parcial | `ingest/sofascore/live_events.py`, `live_momentum` |
| **P2** MLE momentum com live_ticks | ✅ Feito | `tune-inplay --source ticks|both`; `wc_inplay_ticks_dataset.py` |
| **Validação** benchmark_inplay CLI | ✅ Feito | `benchmark-inplay` (+ `--ab-momentum`, `--tune-ticks`) |

**Config operacional (ganhos):** respeitar `LIVE_BLOCK_MINUTE=45`, `LIVE_HARD_STOP_MINUTE=88`, `LIVE_CASHOUT_USE_TREND=true`.

---

## 1. Arquitetura da Cadeia In-Play

```
┌──────────────────┐
│  Superbet API    │──→ fetch_event() → SuperbetEventSnapshot
│  (curl_cffi)     │
└──────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────┐
│  ingest/superbet/advice.py: run_live_advice()                    │
│                                                                  │
│  1. Normaliza nomes (normalize_national_team)                   │
│  2. Monte Carlo in-play: inplay_from_predictor()                 │
│  3. Constrói build_bet_advice_report()                          │
│  4. Constrói build_bet_strategy_report()                        │
│  5. Junte em JSON → frontend                                     │
└──────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────┐
│  models/wc_inplay.py → simulate_inplay()                       │
│                                                                  │
│  Entrada: casa, fora, placar, minuto, λ_casa, λ_fora, rho      │
│  Saída: prob_final_home/away/draw, prob_next_goal, BTTS,        │
│         over/under, combos, top_scores — tudo via MC Poisson   │
│                                                                  │
│  Critério central: λ é constante durante o jogo!                 │
│  (NÃO depende do evento táctico real que acontece no minuto 67)│
└──────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────┐
│  models/wc_bet_advice.py → advise_aportes() / advise_cashout()   │
│                                                                  │
│  Lógica: EV = P(modelo) × odd - 1                               │
│  Se EV >= threshold → oportunidade                              │
│  Kelly quarter → sugestão de stake %                           │
│                                                                  │
│  Cashout: remaining_ev = P(atual) × odd_entrada - 1            │
│  Se remaining_ev < -10% → cash-out                            │
│  Se prob_ratio < 0.65 → cash-out                              │
└──────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────┐
│  models/wc_bet_strategy.py → build_bet_strategy_report()       │
│                                                                  │
│  Postura: defensivo / neutro / atacar                           │
│  Warnings: correlação, house trap, hedge, fase tardia           │
│  Watch list: top 3 mercados com EV mais alto                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Onde Estamos Acertando (confirmado)

| Aspecto | Como funciona | Status |
|---|---|---|
| **Monte Carlo in-play** | 5k simulações Poisson bivariadas com Dixon-Coles rho | Bom para partida neutra sem dados Ao Vivo |
| **Cálculo de EV** | Simples e correto: P × O - 1 | Correto |
| **Cash-out** | Remaining EV + prob_ratio + late game gates | Razoável — evita prejuízo bruto |
| **Kelly** | Quarter-Kelly com teto de 5% banca | Conservador, adequado para in-play |
| **Blindagem** | Correlation warnings, house trap, late game, overround | Excelente para gestão de risco |
| **Persistência** | live_ticks Parquet com snapshot + modelo + aporte | Operação de dados conectada |

---

## 3. Onde Estamos Errando ou Sub-otimizando

### 3.1. O modelo não vê o jogo que está acontecendo agora (ERRO CRÍTICO — mitigado)

**Problema original:** λ fixo pré-jogo.

**Mitigações ativas (2026-06-17):** Bayes com gols observados, momentum (`wc_live_momentum`), ajuste ScoreAlarm (posse/SOT), boost pós-gol na timeline, ajuste HT (`wc_halftime_adjust`). λ ainda não incorpora substituições táticas nem xG acumulado Sofascore em tempo real.

```python
# Em wc_inplay.py (simplificado):
result = inplay_from_predictor(
    predictor, home_team="Colômbia", away_team="Jordânia",
    minute=67, home_score=2, away_score=0,
    lambda_full_home=factors.lambda_home,  # <-- ESTE VALOR É FIXO DO PRÉ-JOGO
    lambda_full_away=factors.lambda_away,
)
```

**O que falta:**
- A Colômbia está com 2 gols de vantagem aos 67 minutos → λ_casa deveria estar **maior** (confiança alta)
- Se a Jordânia está empurrando para frente → λ_fora deveria estar **maior** no segundo tempo
- Se houve cartão vermelho → λ afetado
- Se houve substituição ofensiva → λ afetado
- Posse de bola, xG real, chutes no gol — **nada disso entra**

**Consequência:** O modelo gera a mesma probabilidade para um jogo 2×0 dominante aos 67' e um jogo 2×0 frágil onde a equipe está recuando. Isso é **grosseiramente sub-ótimo**.

### 3.2. Dados reais do jogo ignorados completamente

**Atualização 2026-06-17:** parcialmente resolvido via ScoreAlarm + Sofascore live.

| Dado real disponível | Usado no pipeline? | Onde entra |
|---|---|---|
| Eventos (gol, cartão vermelho) | **Sim** | timeline → `wc_live_momentum` |
| Posse de bola | **Sim** | `adjust_lambdas_from_live_stats` |
| Chutes no gol (overview) | **Sim** | ScoreAlarm → `live_stats` |
| xG acumulado (Sofascore) | **Parcial** | pré-jogo; ao vivo limitado |
| Substituição ofensiva/defensiva | **Não** | pendente feed FIFA/Sofascore |
| Vento, KXL emoção | **Não** | só pré-jogo |

### 3.3. O "próximo gol" usa regra de equipamento, não tática

```python
# wc_inplay.py linhas 266-272:
lam_sum = lam_h + lam_a
if lam_sum > 0:
    p_any = 1.0 - (no_more / n)
    p_next_home = (lam_h / lam_sum) * p_any
    p_next_away = (lam_a / lam_sum) * p_any
```

Isso assume que o próximo gol segue a proporção de força pré-jogo. Se a equipe da casa está recuada protegendo resultado, a força de ataque dela **no momento** é menor. A proporção deveria ser reavaliada.

### 3.4. Cash-out usa probabilidade estática, não momentum

~~O cashout compara `current_model_prob` com `placed_implied_prob`. Mas `current_model_prob` vem do MC estático, não do **momentum** real.~~

**Atualização 2026-06-17:** `advise_cashout()` aplica `apply_trend_to_cashout()` quando `LIVE_CASHOUT_USE_TREND=true`, fundindo `trend_report` (`wc_trend_advisor`: colapso de odds, sequência de gols, mercado decidido). A prob mecânica continua vinda do MC; a **decisão de saída** sobe de grau (`manter` → `cashout_parcial` → `cashout`) se o copiloto detectar conflito crítico com a aposta aberta.

Resposta API: `cashout.trend_influenced`, `cashout.trend_urgency`.

### 3.5. Oportunidades não diferenciam fase do jogo

```python
# wc_bet_strategy.py → aportes são ranqueados só por EV
if ev.expected_value < threshold:
    continue
# NÃO considera: minuto, placar, momentum, eventos
```

Uma oportunidade de 1X2 no minuto 80' é muito mais volátil do que no minuto 20'. O modelo não aplica **decaimento de confiança temporal**.

### 3.6. Totais de gols não ajustam por placar atual

**Resolvido (P0):** `_apply_guaranteed_lines` + `inplay_dead_market` — Over já batido não aparece como “sem valor”; BTTS/Over mortos são filtrados em `advise_aportes`.

### 3.7. Configuração `live_ev_min_edge=4%` pode ser muito conservadora

No pré-jogo a edge mínima é 3% (`ev_min_edge`). Ao vivo, com informação temporal, poderíamos ser mais seletivos — mas também mais agressivos quando o jogo confirma o cenário. Hoje usa-se `live_ev_min_edge=4%` fixo, sem ajuste dinâmico.

---

## 4. O Que Podemos Melhorar (Back-End)

### 4.1. Parâmetro de momentum (ALTO IMPACTO / MÉDIO ESFORÇO)

**Ideia:** criar um `momentum_factor` que ajuste λ com base no jogo real.

```python
class LiveMomentum:
    goal_diff: int          # vantagem no placar
    minute: int             # minuto atual
    events: list[GameEvent] # gols, cartões, substituições (via Sofascore/FIFA)

    def adjust_lambdas(self, lambda_h: float, lambda_a: float) -> tuple[float, float]:
        """
        - Equipe na frente → reduzir λ própria (defensiva), aumenta do adversário (pressão)
        - Cartão vermelho → reduzir λ do time com menos jogadores
        - Substituição ofensiva → aumentar λ daquele time
        - Min > 80' → compressão geral (menos gols esperados no restante)
        """
```

**Implementação sugerida:**
1. Criar `models/wc_live_momentum.py` com regras simples primeiro (placar + minuto)
2. Depois integrar feed de eventos (Sofascore `events` endpoint ou FIFA `live`)
3. Parâmetros tunáveis via `settings.live_momentum_enabled`

### 4.2. Bayesian update de λ com gols observados (MÉDIO IMPACTO / MÉDIO ESFORÇO)

Agora, com o placar atual conhecido, podemos fazer **inferência Bayesiana** do λ real:

```python
# Se a casa marcou 2 gols em 67 minutos:
# E[λ_casa | observed] > λ_casa_prior
# Usar Gamma posterior: α_post = α_prior + goals, β_post = β_prior + minutes

# Isso daria uma estimativa de λ "ao vivo" mais precisa do que o λ pré-jogo fixo
```

Isso é **matematicamente sólido** e leva a previsões mais acertivas.

### 4.3. Mediação temporal: confiança decresce no final do jogo (ALTO IMPACTO / BAIXO ESFORÇO)

```python
def time_decay_confidence(minute: int) -> float:
    """
    Aos 90' a variância é alta — qualquer evento pode decidir.
    Reduzir "aposta forte" nos últimos 15 minutos.
    """
    if minute >= 80:
        return 0.6
    if minute >= 70:
        return 0.75
    return 1.0
```

Aplicar como multiplicador no threshold:
```python
effective_threshold = threshold / time_decay_confidence(minute)
# Aos 80': threshold 4% → 4%/0.6 = 6.67% (mais rigoroso)
```

### 4.4. Mercado "Linha Garantida" para totais com placar conhecido (BAIXO IMPACTO / BAIXO ESFORÇO)

Se já ocorreram 3 gols totais, a linha Over 2.5 deveria ser **100%** (ou muito próximo):

```python
def guaranteed_line_prob(total_goals: int, line: float) -> float | None:
    """Retorna 1.0 se a linha já foi batida, 0.0 se impossível, None se incerto."""
    if total_goals > line:
        return 1.0
    if total_goals + max_possible_remaining <= line:
        return 0.0
    return None  # fallback para MC
```

Isso evita "falsos sem valor" para over 2.5 quando já há 3 gols.

### 4.5. Integrar xG/histórico Sofascore para calibrar λ pré-jogo (ALTO IMPACTO / MÉDIO ESFORÇO)

Hoje `goal_model_factors()` usa:
- `fixtures_df` (histórico de jogos da Copa)
- features de Elo
- **NÃO usa** dados Sofascore recentes do time

Se temos `match_stats.parquet` com xG atual dos times, podemos calibrar:
```python
# Se o time X tem xG médio 1.8 nos últimos 5 jogos (Sofascore),
# mas o modelo histórico dá λ=1.2:
# Calibração bayesiana: λ_adj = w * λ_hist + (1-w) * λ_xg_recente
```

**Arquivos relevantes:** `ingest/sofascore/stats_dataset.py`, `data/lake/sofascore/match_stats.parquet`

### 4.6. Modulador KXL para evento ao vivo (ALTO IMPACTO / ALTO ESFORÇO)

O KXL (`pipelines/wc_kxl_collision.py`) calcula:
- `Vcar` (vetor ataque) × `Vesc` (vetor defesa)
- Colisões setoriais, matriz de letalidade
- Moduladores: clima, árbitro, escalações, emoção

Hoje KXL roda **só no pré-jogo**. A lógica poderia ser:
1. Rodar KXL a cada update de eventos (sub, cartão, lesão)
2. Gerar um `kxl_momentum_score` em tempo real
3. Usar como modulador do λ in-play: aumentar/diminuir λ conforme vantagem setorial

### 4.7. Pipeline de eventos Sofascore/FIFA ao vivo (ALTO IMPACTO / ALTO ESFORÇO)

**Cadeia desejada:**
```
Sofascore API → eventos ao vivo (gol, cartão, sub, lesão, penalti)
            ↓
        ingest/sofascore/live_events.py
            ↓
        Mapeia evento → ajuste de λ (momentum)
            ↓
        Re-roda inplay_from_predictor() com λ atualizado
            ↓
        Atualiza resposta JSON em tempo real
```

**Nota:** Sofascore tem API de `events/{id}` com timeline. FIFA tem `api.fifa.com` com eventos ao vivo.

---

## 5. Checklist de Implementação Priorizado

| Prioridade | Melhoria | Arquivo a alterar | Esforço |
|---|---|---|---|
| **P0** | Bayesian update de λ com gols observados | `models/wc_inplay.py` | 4h |
| **P0** | Mercado "linha garantida" para totais | `models/wc_inplay.py` / `wc_bet_advice.py` | 2h |
| **P1** | Momentum por placar + minuto | `models/wc_live_momentum.py` (novo) | 6h |
| **P1** | Time decay de confiança em fase final | `wc_bet_strategy.py` / `config.py` | ✅ Feito |
| **P1** | Cash-out + trend advisor | `wc_bet_advice.apply_trend_to_cashout` | ✅ Feito |
| **P2** | xG recente calibrando λ pré-jogo | `models/poisson_wc.py` | 8h |
| **P2** | Integrar eventos Sofascore ao vivo | `ingest/sofascore/live_events.py` (novo) | 16h |
| **P3** | KXL dinâmico em tempo real | `pipelines/wc_kxl_collision.py` | 20h |
| **P3** | Modelo de próximo gol com momentum | `models/wc_inplay.py` | 6h |

---

## 6. Validação: Como Saber Se Melhorou

| Métrica | Como medir |
|---|---|
| **Brier in-play** | Comparar prob_final_X com resultado real em jogos acabados |
| **ROI de apostas simuladas** | Executar 30 dias de "aposta virtual" com estratégia EV+, medir retorno |
| **Log-loss por minuto** | Calcular log-loss em cada intervalo de tempo (deve decrescer com momentum) |
| **Número de cash-outs corretos** | Cash-out executado antes de gol contrário = acerto |
| **Precisão de "próximo gol"** | Em jogos com mais gols, verificar se prob_next_goal acerta direção |

**Pipeline de validação sugerido:**
```bash
# 1. Coletar 2 semanas de live_ticks (já roda)
ingest-sofascore --history --all-teams   # stats pré-jogo
poll-superbet-live --event-ids ...     # live_ticks parquet

# 2. Rodar benchmark
python -m tests.benchmark_inplay --season 2026 --min-games 50

# 3. Comparar Brier com/sem momentum
python -m tests.benchmark_inplay --ab-test momentum
```

---

## 7. Conclusão Executiva

### O que funciona bem hoje
- Estrutura de Monte Carlo com Dixon-Coles é sólida para pré-jogo
- Cálculo de EV, cash-out e Kelly estão matematicamente corretos
- Blindagens (correlation, house trap, late game) protegem bem o apostador

### O que precisa de atenção agora
1. **Calibrar coeficientes de momentum** com `live_ticks.parquet` (MLE em `wc_inplay_coefficients.json`).
2. **Blend xG Sofascore** no λ pré-jogo (`poisson_wc.py`) — P2.
3. **Benchmark Brier in-play** automatizado — §6 ainda manual.
4. **KXL dinâmico** — P3 longo prazo.

### Maior alavanca de melhoria (atualizada)
**Operação + calibração:** respeitar filtros de minuto (45'/88'), usar cash-out com `trend_influenced`, e calibrar β do momentum com ticks reais da Copa. P0/P1 de código estão largamente implementados.

### Visão de longo prazo
A convergência final é integrar:
- **Feed de eventos ao vivo** (Sofascore/FIFA timeline)
- **KXL dinâmico** (atualizado a cada evento)
- **Bayesian online** (λ se adapta aos eventos)

Isso transformaria o sistema de "modelo estático com McCondicionado ao placar" para "modelo reativo que vê o jogo acontecendo".

---
