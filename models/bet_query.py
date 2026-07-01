"""Query inteligente de bilhetes — analisa apostas abertas e sugere as mais promissoras.

Com base no histórico de apostas liquidadas do usuário, calcula um "Índice de Confiança"
para cada bilhete aberto, considerando:
- EV (Expected Value) da aposta
- Odds vs histórico de acerto do usuário por faixa de odd
- Tipo de mercado vs ROI histórico do usuário
- Momento do jogo (minuto) vs taxa de acerto por período
- Combos: número de pernas vs taxa de acerto histórica

Retorna bilhetes ranqueados por potencial de retorno, com explicação do score.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Estruturas de resultado
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class BetScoreBreakdown:
    """Componentes do score de um bilhete."""

    ev_score: float = 0.0           # 0-25: baseado no EV da aposta
    odd_score: float = 0.0          # 0-25: baseado na faixa de odd vs histórico
    market_score: float = 0.0       # 0-20: baseado no mercado vs ROI histórico
    timing_score: float = 0.0       # 0-15: baseado no minuto do jogo
    combo_penalty: float = 0.0      # 0-15: penalidade por múltiplas pernas
    total_score: float = 0.0        # 0-100


@dataclass
class ScoredBet:
    """Um bilhete com score e explicação."""

    bet_id: str
    event_name: str
    home_team: str
    away_team: str
    picks: list[dict[str, Any]]
    stake: float
    odds_placed: float
    potential_return: float
    cashout_value: float | None
    ticket_code: str | None
    minute: int | None
    status: str
    captured_at: str
    superbet_event_id: int | None
    source: str
    score: BetScoreBreakdown
    recommendation: str           # "HOLD" | "INCREASE" | "CASHOUT" | "AVOID"
    reasoning: str                # explicação em português
    potential_actions: list[str]   # ações sugeridas


@dataclass
class BetQueryResult:
    """Resultado completo da query inteligente."""

    total_open_bets: int = 0
    scored_bets: list[ScoredBet] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    user_patterns: dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────────
# Carregamento de dados
# ──────────────────────────────────────────────────────────────────────────────


def _load_open_bets() -> list[dict[str, Any]]:
    """Lê apostas abertas do JSON local."""
    from api.user_bets_store import _load_store

    store = _load_store()
    return [b for b in store.get("bets", []) if b.get("status") == "open"]


def _load_settled_bets() -> list[dict[str, Any]]:
    """Lê apostas liquidadas do JSON local."""
    from api.user_bets_store import list_settled_bets

    bets = list_settled_bets()
    return [b.model_dump(mode="json") for b in bets]


# ──────────────────────────────────────────────────────────────────────────────
# Análise de padrões do usuário
# ──────────────────────────────────────────────────────────────────────────────


def _analyze_user_patterns(settled_bets: list[dict[str, Any]]) -> dict[str, Any]:
    """Extrai padrões de performance do usuário a partir do histórico.

    Retorna dict com:
    - odd_range_stats: {faixa: {n_bets, wins, roi, avg_stake}}
    - market_stats: {mercado: {n_bets, wins, roi}}
    - combo_stats: {n_legs: {n_bets, wins, roi}}
    - timing_stats: {periodo: {n_bets, wins}}
    - overall_roi: float
    - best_odd_range: str
    - best_market: str
    """
    if not settled_bets:
        return {
            "odd_range_stats": {},
            "market_stats": {},
            "combo_stats": {},
            "timing_stats": {},
            "overall_roi": 0.0,
            "best_odd_range": "",
            "best_market": "",
            "has_history": False,
        }

    # Faixas de odd
    ODD_RANGES = [
        ("1.0-1.5", 1.0, 1.5),
        ("1.5-2.0", 1.5, 2.0),
        ("2.0-3.0", 2.0, 3.0),
        ("3.0-5.0", 3.0, 5.0),
        ("5.0-10.0", 5.0, 10.0),
        ("10.0+", 10.0, 9999.0),
    ]

    def _odd_range(odd: float) -> str:
        for label, low, high in ODD_RANGES:
            if low <= odd < high:
                return label
        return "10.0+"

    def _market_from_picks(picks: list[dict]) -> str:
        if not picks:
            return "unknown"
        markets = set()
        for p in picks:
            m = p.get("market", "unknown")
            base = m.split("_")[0] if "_" in m else m
            if base.startswith("totals"):
                base = "totals"
            markets.add(base)
        if len(markets) == 1:
            return markets.pop()
        return "combo"

    def _calculate_return(bet: dict) -> float:
        result = bet.get("result", "lost")
        stake = bet.get("stake", 0.0)
        potential = bet.get("potential_return", 0.0)
        cashout = bet.get("cashout_value")
        if result == "won":
            return potential if potential > 0 else stake * bet.get("odds_placed", 1.0)
        elif result == "cashout":
            return cashout if cashout else 0.0
        elif result == "void":
            return stake
        return 0.0

    # Odd range stats
    odd_stats: dict[str, dict] = {}
    for bet in settled_bets:
        odd = bet.get("odds_placed", 0.0)
        rng = _odd_range(odd)
        if rng not in odd_stats:
            odd_stats[rng] = {"n_bets": 0, "wins": 0, "total_stake": 0.0, "total_return": 0.0}
        odd_stats[rng]["n_bets"] += 1
        odd_stats[rng]["total_stake"] += bet.get("stake", 0.0)
        odd_stats[rng]["total_return"] += _calculate_return(bet)
        if bet.get("result") == "won":
            odd_stats[rng]["wins"] += 1

    odd_range_stats = {}
    for rng, stats in odd_stats.items():
        roi = ((stats["total_return"] - stats["total_stake"]) / stats["total_stake"] * 100) if stats["total_stake"] > 0 else 0
        odd_range_stats[rng] = {
            "n_bets": stats["n_bets"],
            "wins": stats["wins"],
            "win_rate": stats["wins"] / stats["n_bets"] if stats["n_bets"] > 0 else 0,
            "roi": round(roi, 2),
            "avg_stake": round(stats["total_stake"] / stats["n_bets"], 2) if stats["n_bets"] > 0 else 0,
        }

    # Market stats
    market_stats: dict[str, dict] = {}
    for bet in settled_bets:
        market = _market_from_picks(bet.get("picks", []))
        if market not in market_stats:
            market_stats[market] = {"n_bets": 0, "wins": 0, "total_stake": 0.0, "total_return": 0.0}
        market_stats[market]["n_bets"] += 1
        market_stats[market]["total_stake"] += bet.get("stake", 0.0)
        market_stats[market]["total_return"] += _calculate_return(bet)
        if bet.get("result") == "won":
            market_stats[market]["wins"] += 1

    market_stats_out = {}
    for mkt, stats in market_stats.items():
        roi = ((stats["total_return"] - stats["total_stake"]) / stats["total_stake"] * 100) if stats["total_stake"] > 0 else 0
        market_stats_out[mkt] = {
            "n_bets": stats["n_bets"],
            "wins": stats["wins"],
            "win_rate": stats["wins"] / stats["n_bets"] if stats["n_bets"] > 0 else 0,
            "roi": round(roi, 2),
        }

    # Combo stats (por número de pernas)
    combo_stats: dict[int, dict] = {}
    for bet in settled_bets:
        n_legs = len(bet.get("picks", []))
        if n_legs not in combo_stats:
            combo_stats[n_legs] = {"n_bets": 0, "wins": 0, "total_stake": 0.0, "total_return": 0.0}
        combo_stats[n_legs]["n_bets"] += 1
        combo_stats[n_legs]["total_stake"] += bet.get("stake", 0.0)
        combo_stats[n_legs]["total_return"] += _calculate_return(bet)
        if bet.get("result") == "won":
            combo_stats[n_legs]["wins"] += 1

    combo_stats_out = {}
    for legs, stats in combo_stats.items():
        roi = ((stats["total_return"] - stats["total_stake"]) / stats["total_stake"] * 100) if stats["total_stake"] > 0 else 0
        combo_stats_out[legs] = {
            "n_bets": stats["n_bets"],
            "wins": stats["wins"],
            "win_rate": stats["wins"] / stats["n_bets"] if stats["n_bets"] > 0 else 0,
            "roi": round(roi, 2),
        }

    # Overall
    total_stake = sum(b.get("stake", 0.0) for b in settled_bets)
    total_return = sum(_calculate_return(b) for b in settled_bets)
    overall_roi = ((total_return - total_stake) / total_stake * 100) if total_stake > 0 else 0

    # Best ranges
    best_odd_range = ""
    best_odd_roi = -999
    for rng, stats in odd_range_stats.items():
        if stats["n_bets"] >= 2 and stats["roi"] > best_odd_roi:
            best_odd_roi = stats["roi"]
            best_odd_range = rng

    best_market = ""
    best_market_roi = -999
    for mkt, stats in market_stats_out.items():
        if stats["n_bets"] >= 2 and stats["roi"] > best_market_roi:
            best_market_roi = stats["roi"]
            best_market = mkt

    return {
        "odd_range_stats": odd_range_stats,
        "market_stats": market_stats_out,
        "combo_stats": combo_stats_out,
        "overall_roi": round(overall_roi, 2),
        "best_odd_range": best_odd_range,
        "best_market": best_market,
        "has_history": True,
        "total_settled": len(settled_bets),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Scoring de bilhetes abertos
# ──────────────────────────────────────────────────────────────────────────────


def _score_bet(
    bet: dict[str, Any],
    patterns: dict[str, Any],
) -> tuple[BetScoreBreakdown, str, str, list[str]]:
    """Calcula score e recomendação para um bilhete aberto.

    Returns: (score_breakdown, recommendation, reasoning, potential_actions)
    """
    score = BetScoreBreakdown()
    picks = bet.get("picks", []) or []
    odd = bet.get("odds_placed", 1.0)
    stake = bet.get("stake", 0.0)
    potential = bet.get("potential_return", 0.0)
    minute = bet.get("minute") or bet.get("register_minute") or bet.get("proposal_minute")
    cashout = bet.get("cashout_value")
    n_legs = len(picks)

    # --- 1. EV Score (0-25) ---
    # Usar combined_ev se disponível, senão estimar a partir da odd
    combined_ev = bet.get("combined_ev")
    if combined_ev is not None:
        ev = float(combined_ev)
    else:
        # Estimativa conservadora: EV = prob_estimada * odd - 1
        # Prob estimada: 1/odd * 0.85 (overround ajustado)
        prob_est = (1.0 / odd) * 0.85 if odd > 1 else 0.5
        ev = prob_est * odd - 1.0

    if ev >= 0.15:
        score.ev_score = 25
    elif ev >= 0.05:
        score.ev_score = 20
    elif ev >= 0:
        score.ev_score = 15
    elif ev >= -0.1:
        score.ev_score = 8
    else:
        score.ev_score = 2

    # --- 2. Odd Score (0-25) ---
    odd_range_stats = patterns.get("odd_range_stats", {})
    ODD_RANGES = [
        ("1.0-1.5", 1.0, 1.5),
        ("1.5-2.0", 1.5, 2.0),
        ("2.0-3.0", 2.0, 3.0),
        ("3.0-5.0", 3.0, 5.0),
        ("5.0-10.0", 5.0, 10.0),
        ("10.0+", 10.0, 9999.0),
    ]
    bet_range = ""
    for label, low, high in ODD_RANGES:
        if low <= odd < high:
            bet_range = label
            break
    if not bet_range:
        bet_range = "10.0+"

    if bet_range in odd_range_stats and odd_range_stats[bet_range]["n_bets"] >= 2:
        stats = odd_range_stats[bet_range]
        wr = stats["win_rate"]
        roi = stats["roi"]
        if roi > 10 and wr > 0.5:
            score.odd_score = 25
        elif roi > 0 and wr > 0.4:
            score.odd_score = 20
        elif roi > -10 and wr > 0.35:
            score.odd_score = 15
        elif roi > -20:
            score.odd_score = 8
        else:
            score.odd_score = 3
    else:
        # Sem histórico — odds 1.5-3.0 são "sweet spot" geral
        if 1.5 <= odd < 3.0:
            score.odd_score = 18
        elif 1.0 <= odd < 1.5:
            score.odd_score = 15
        elif 3.0 <= odd < 5.0:
            score.odd_score = 12
        else:
            score.odd_score = 6

    # --- 3. Market Score (0-20) ---
    market_stats = patterns.get("market_stats", {})
    market = _market_from_picks(picks)
    if market in market_stats and market_stats[market]["n_bets"] >= 2:
        mstats = market_stats[market]
        if mstats["roi"] > 10 and mstats["win_rate"] > 0.5:
            score.market_score = 20
        elif mstats["roi"] > 0 and mstats["win_rate"] > 0.4:
            score.market_score = 16
        elif mstats["roi"] > -10:
            score.market_score = 10
        elif mstats["roi"] > -20:
            score.market_score = 5
        else:
            score.market_score = 2
    else:
        # Sem histórico — mercados simples são mais previsíveis
        if market in ("h2h", "totals"):
            score.market_score = 15
        elif market == "combo":
            score.market_score = 8
        else:
            score.market_score = 10

    # --- 4. Timing Score (0-15) ---
    # Apostas em minutos mais precoces têm mais incerteza (mais valor)
    # Apostas muito tardias têm menos valor mas mais certeza
    if minute is not None:
        if 30 <= minute <= 70:
            score.timing_score = 15  # Sweet spot: jogo definindo
        elif 15 <= minute < 30 or 70 <= minute <= 85:
            score.timing_score = 12
        elif minute < 15:
            score.timing_score = 8   # Muito cedo, incerto
        else:
            score.timing_score = 6   # Muito tarde, pouco valor
    else:
        score.timing_score = 10  # Desconhecido

    # --- 5. Combo Penalty (0-15, subtrai do total) ---
    combo_stats = patterns.get("combo_stats", {})
    if n_legs == 1:
        score.combo_penalty = 0  # Simples = melhor
    elif n_legs == 2:
        if 2 in combo_stats and combo_stats[2]["n_bets"] >= 2:
            wr2 = combo_stats[2]["win_rate"]
            if wr2 > 0.4:
                score.combo_penalty = 2
            else:
                score.combo_penalty = 5
        else:
            score.combo_penalty = 3
    elif n_legs == 3:
        if 3 in combo_stats and combo_stats[3]["n_bets"] >= 2:
            wr3 = combo_stats[3]["win_rate"]
            if wr3 > 0.3:
                score.combo_penalty = 5
            else:
                score.combo_penalty = 10
        else:
            score.combo_penalty = 8
    else:
        # 4+ pernas = muito arriscado
        score.combo_penalty = 12 + min(n_legs - 4, 3)

    # Total
    score.total_score = (
        score.ev_score
        + score.odd_score
        + score.market_score
        + score.timing_score
        - score.combo_penalty
    )
    score.total_score = max(0, min(100, score.total_score))

    # --- Recomendação ---
    actions: list[str] = []

    if score.total_score >= 75:
        recommendation = "HOLD"
        reasoning = (
            f"Bilhete com alto potencial (score {score.total_score:.0f}/100). "
            f"EV positivo, odd na faixa favorável e mercado com histórico positivo. "
            f"Manter posição."
        )
        actions.append("Manter aposta até o final")
        if potential > stake * 3:
            actions.append("Considerar cash-out parcial se atingir 70% do retorno potencial")

    elif score.total_score >= 55:
        recommendation = "HOLD"
        reasoning = (
            f"Bilhete com potencial moderado (score {score.total_score:.0f}/100). "
            f"Posição razoável, monitorar evolução do jogo."
        )
        actions.append("Manter e monitorar")
        actions.append("Avaliar cash-out se o jogo mudar de tendência")

    elif score.total_score >= 35:
        recommendation = "MONITOR"
        reasoning = (
            f"Bilhete com potencial incerto (score {score.total_score:.0f}/100). "
            f"Riscos identificados — mercado ou odd fora da zona de conforto do histórico."
        )
        actions.append("Monitorar de perto")
        if cashout and cashout > stake * 0.5:
            actions.append(f"Cash-out disponível: R$ {cashout:.2f} — considerar se o jogo piorar")

    elif score.total_score >= 20:
        recommendation = "CASHOUT"
        reasoning = (
            f"Bilhete com baixo potencial (score {score.total_score:.0f}/100). "
            f"Múltiplos fatores desfavoráveis: combo complexo, odd fora da faixa lucrativa, "
            f"ou mercado com histórico negativo."
        )
        actions.append("Buscar cash-out se disponível")
        actions.append("Evitar aumentar stake neste tipo de aposta no futuro")

    else:
        recommendation = "AVOID"
        reasoning = (
            f"Bilhete com potencial muito baixo (score {score.total_score:.0f}/100). "
            f"Alto risco de perda. Aprender com este padrão para apostas futuras."
        )
        actions.append("Não aumentar exposição")
        actions.append("Anotar lição: evitar este perfil de aposta")
        if cashout and cashout > 0:
            actions.append(f"Cash-out de R$ {cashout:.2f} pode ser a melhor saída")

    return score, recommendation, reasoning, actions


def _market_from_picks(picks: list[dict]) -> str:
    """Extrai mercado principal dos picks."""
    if not picks:
        return "unknown"
    markets = set()
    for p in picks:
        m = p.get("market", "unknown") if isinstance(p, dict) else "unknown"
        base = m.split("_")[0] if "_" in m and m[0] != "h" else m
        if base.startswith("totals"):
            base = "totals"
        markets.add(base)
    if len(markets) == 1:
        return markets.pop()
    return "combo"


# ──────────────────────────────────────────────────────────────────────────────
# Função principal
# ──────────────────────────────────────────────────────────────────────────────


def query_bets(
    *,
    min_score: int = 0,
    max_results: int = 50,
    include_settled_patterns: bool = True,
) -> BetQueryResult:
    """Executa a query inteligente sobre bilhetes abertos.

    Args:
        min_score: score mínimo para incluir no resultado (0-100)
        max_results: máximo de bilhetes retornados
        include_settled_patterns: se True, analisa histórico liquidado

    Returns:
        BetQueryResult com bilhetes ranqueados e análise
    """
    open_bets = _load_open_bets()
    settled_bets = _load_settled_bets() if include_settled_patterns else []
    patterns = _analyze_user_patterns(settled_bets)

    result = BetQueryResult(
        total_open_bets=len(open_bets),
        user_patterns=patterns,
    )

    scored: list[ScoredBet] = []
    for bet in open_bets:
        score, rec, reasoning, actions = _score_bet(bet, patterns)
        if score.total_score < min_score:
            continue

        sb = ScoredBet(
            bet_id=bet.get("id", ""),
            event_name=bet.get("event_name", ""),
            home_team=bet.get("home_team", ""),
            away_team=bet.get("away_team", ""),
            picks=bet.get("picks", []) or [],
            stake=bet.get("stake", 0.0),
            odds_placed=bet.get("odds_placed", 1.0),
            potential_return=bet.get("potential_return", 0.0),
            cashout_value=bet.get("cashout_value"),
            ticket_code=bet.get("ticket_code"),
            minute=bet.get("minute") or bet.get("register_minute") or bet.get("proposal_minute"),
            status=bet.get("status", "open"),
            captured_at=bet.get("captured_at", ""),
            superbet_event_id=bet.get("superbet_event_id"),
            source=bet.get("source", "manual"),
            score=score,
            recommendation=rec,
            reasoning=reasoning,
            potential_actions=actions,
        )
        scored.append(sb)

    # Ordenar por score decrescente
    scored.sort(key=lambda x: x.score.total_score, reverse=True)
    result.scored_bets = scored[:max_results]

    # Summary
    n_high = sum(1 for s in scored if s.score.total_score >= 75)
    n_medium = sum(1 for s in scored if 55 <= s.score.total_score < 75)
    n_low = sum(1 for s in scored if 35 <= s.score.total_score < 55)
    n_poor = sum(1 for s in scored if s.score.total_score < 35)
    total_potential = sum(s.potential_return for s in scored)
    total_staked = sum(s.stake for s in scored)

    result.summary = {
        "n_high_potential": n_high,
        "n_medium_potential": n_medium,
        "n_low_potential": n_low,
        "n_poor_potential": n_poor,
        "total_open_bets": len(open_bets),
        "total_scored": len(scored),
        "total_potential_return": round(total_potential, 2),
        "total_staked": round(total_staked, 2),
        "avg_score": round(sum(s.score.total_score for s in scored) / len(scored), 1) if scored else 0,
        "has_history": patterns.get("has_history", False),
        "best_odd_range": patterns.get("best_odd_range", ""),
        "best_market": patterns.get("best_market", ""),
        "overall_roi": patterns.get("overall_roi", 0.0),
    }

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Serialização para API
# ──────────────────────────────────────────────────────────────────────────────


def bet_query_to_dict(result: BetQueryResult) -> dict[str, Any]:
    """Converte BetQueryResult para dict JSON-friendly."""
    return {
        "total_open_bets": result.total_open_bets,
        "summary": result.summary,
        "user_patterns": result.user_patterns,
        "scored_bets": [
            {
                "bet_id": sb.bet_id,
                "event_name": sb.event_name,
                "home_team": sb.home_team,
                "away_team": sb.away_team,
                "picks": sb.picks,
                "stake": sb.stake,
                "odds_placed": sb.odds_placed,
                "potential_return": sb.potential_return,
                "cashout_value": sb.cashout_value,
                "ticket_code": sb.ticket_code,
                "minute": sb.minute,
                "status": sb.status,
                "captured_at": sb.captured_at,
                "superbet_event_id": sb.superbet_event_id,
                "source": sb.source,
                "score": {
                    "ev_score": sb.score.ev_score,
                    "odd_score": sb.score.odd_score,
                    "market_score": sb.score.market_score,
                    "timing_score": sb.score.timing_score,
                    "combo_penalty": sb.score.combo_penalty,
                    "total_score": sb.score.total_score,
                },
                "recommendation": sb.recommendation,
                "reasoning": sb.reasoning,
                "potential_actions": sb.potential_actions,
            }
            for sb in result.scored_bets
        ],
    }
