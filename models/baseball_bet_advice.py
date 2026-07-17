"""Recomendações de aporte para beisebol in-play (EV/Kelly)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import settings
from ingest.superbet.parser import SuperbetEventSnapshot
from models.baseball_inplay import BaseballInPlayResult
from models.economics import live_effective_min_edge
from models.ev_value import evaluate_outcome


@dataclass
class BaseballAporteAdvice:
    market: str
    outcome: str
    label: str
    model_prob: float
    market_odd: float
    implied_prob: float
    expected_value: float
    edge_pp: float
    kelly_quarter: float
    suggested_stake_pct: float
    action: str
    suggested_stake_brl: float | None = None


def _format_stake_line(opp: BaseballAporteAdvice, bankroll: float) -> BaseballAporteAdvice:
    if opp.action == "apostar":
        stake = bankroll * opp.suggested_stake_pct
        max_stake = settings.bet_max_stake_pct / 100.0 * bankroll
        stake = min(stake, max_stake)
        opp.suggested_stake_brl = round(stake, 2)
    return opp


def _aporte_from_eval(
    market: str,
    outcome: str,
    label: str,
    model_prob: float,
    odd: float,
    bankroll: float,
) -> BaseballAporteAdvice | None:
    if odd <= 1.0 or model_prob <= 0:
        return None
    ev = evaluate_outcome(outcome, model_prob, odd)
    min_edge = live_effective_min_edge(settings.ev_min_edge)
    if ev.expected_value < min_edge:
        return None
    edge_pp = (ev.model_prob - ev.implied_prob) * 100.0
    if edge_pp < settings.live_min_edge_pp:
        return None
    suggested_pct = max(0.0, ev.kelly_quarter)
    action = "apostar" if suggested_pct > 0 else "monitorar"
    return BaseballAporteAdvice(
        market=market,
        outcome=outcome,
        label=label,
        model_prob=ev.model_prob,
        market_odd=ev.odd,
        implied_prob=ev.implied_prob,
        expected_value=ev.expected_value,
        edge_pp=edge_pp,
        kelly_quarter=ev.kelly_quarter,
        suggested_stake_pct=suggested_pct,
        action=action,
    )


def _moneyline_aportes(
    inplay: BaseballInPlayResult,
    snapshot: SuperbetEventSnapshot,
    bankroll: float,
) -> list[BaseballAporteAdvice]:
    out: list[BaseballAporteAdvice] = []
    ml = snapshot.moneyline_odds or snapshot.h2h_odds
    if not ml:
        return out
    for key, prob in inplay.moneyline_probs.items():
        odd = ml.get(key)
        if odd is None:
            continue
        label = f"{inplay.home_team} vence" if key == "1" else f"{inplay.away_team} vence"
        opp = _aporte_from_eval("moneyline", key, label, prob, odd, bankroll)
        if opp:
            out.append(_format_stake_line(opp, bankroll))
    return out


def _spread_aportes(
    inplay: BaseballInPlayResult,
    snapshot: SuperbetEventSnapshot,
    bankroll: float,
) -> list[BaseballAporteAdvice]:
    out: list[BaseballAporteAdvice] = []
    spread = snapshot.spread_odds
    if not spread:
        return out
    for line_key, sides in spread.items():
        try:
            line_val = float(line_key.replace("p", "").replace("m", "-").replace("_", "."))
        except ValueError:
            continue
        for side, odd in sides.items():
            prob_key = f"{side}_{line_key}"
            prob = inplay.spread_probs.get(prob_key)
            if prob is None:
                # tenta chave normalizada
                lk = f"{line_val:g}".replace(".", "_").replace("-", "m")
                prob = inplay.spread_probs.get(f"{side}_{lk}")
            if prob is None:
                continue
            team = inplay.home_team if side == "home" else inplay.away_team
            sign = "+" if line_val > 0 else ""
            label = f"{team} {sign}{line_val:g} (run line)"
            opp = _aporte_from_eval("run_line", prob_key, label, prob, odd, bankroll)
            if opp:
                out.append(_format_stake_line(opp, bankroll))
    return out


def _total_aportes(
    inplay: BaseballInPlayResult,
    snapshot: SuperbetEventSnapshot,
    bankroll: float,
) -> list[BaseballAporteAdvice]:
    out: list[BaseballAporteAdvice] = []
    totals = snapshot.total_points_odds
    if not totals:
        return out
    for line, sides in totals.items():
        try:
            line_val = float(str(line).replace(",", "."))
        except ValueError:
            continue
        line_key = f"{line_val:g}".replace(".", "_")
        for outcome, odd in sides.items():
            prob_key = f"{outcome}_{line_key}"
            prob = inplay.total_probs.get(prob_key)
            if prob is None:
                continue
            label = f"{'Over' if outcome == 'over' else 'Under'} {line_val:g} corridas"
            opp = _aporte_from_eval("total_runs", prob_key, label, prob, odd, bankroll)
            if opp:
                out.append(_format_stake_line(opp, bankroll))
    return out


def _confidence_score(
    inplay: BaseballInPlayResult, aportes: list[BaseballAporteAdvice]
) -> dict[str, Any]:
    max_edge = max((a.edge_pp for a in aportes), default=0.0)
    ml_diff = abs(inplay.prob_home_win - inplay.prob_away_win)
    score = min(0.95, 0.45 + max_edge / 100.0 + ml_diff * 0.15)
    label = "Alta" if score >= 0.70 else "Média" if score >= 0.55 else "Baixa"
    return {"score": round(score, 4), "label": label, "max_edge_pp": round(max_edge, 2)}


def build_baseball_bet_advice_report(
    *,
    inplay: BaseballInPlayResult,
    snapshot: SuperbetEventSnapshot,
    bankroll: float = 1000.0,
) -> dict[str, Any]:
    """Constrói relatório de aportes para beisebol in-play."""
    aportes: list[BaseballAporteAdvice] = []
    aportes.extend(_moneyline_aportes(inplay, snapshot, bankroll))
    aportes.extend(_spread_aportes(inplay, snapshot, bankroll))
    aportes.extend(_total_aportes(inplay, snapshot, bankroll))
    aportes.sort(key=lambda a: a.expected_value, reverse=True)
    confidence = _confidence_score(inplay, aportes)
    return {
        "aportes": [
            {
                "market": a.market,
                "outcome": a.outcome,
                "label": a.label,
                "model_prob": round(a.model_prob, 4),
                "market_odd": round(a.market_odd, 2),
                "implied_prob": round(a.implied_prob, 4),
                "expected_value": round(a.expected_value, 4),
                "edge_pp": round(a.edge_pp, 2),
                "kelly_quarter": round(a.kelly_quarter, 4),
                "suggested_stake_pct": round(a.suggested_stake_pct, 4),
                "suggested_stake_value": a.suggested_stake_brl,
                "action": a.action,
            }
            for a in aportes
        ],
        "confidence": confidence,
    }
