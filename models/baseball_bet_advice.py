"""Recomendações de aporte para beisebol in-play (EV/Kelly)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import settings
from ingest.superbet.parser import SuperbetEventSnapshot
from models.baseball_inplay import BaseballInPlayResult, _parse_spread_line_key
from models.baseball_market_labels import (
    format_baseball_selection_label,
    resolve_baseball_market_display,
)
from models.baseball_aporte_sanity import filter_sane_baseball_aportes, annotate_baseball_line_tiers
from models.baseball_dead_market import is_dead_baseball_market
from models.economics import live_effective_min_edge
from models.ev_value import evaluate_outcome


@dataclass
class BaseballAporteAdvice:
    market: str
    outcome: str
    label: str
    market_display: str
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
    market_display: str,
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
    if edge_pp < settings.baseball_live_min_edge_pp:
        return None
    suggested_pct = max(0.0, ev.kelly_quarter)
    action = "apostar" if suggested_pct > 0 else "monitorar"
    return BaseballAporteAdvice(
        market=market,
        outcome=outcome,
        label=label,
        market_display=market_display,
        model_prob=ev.model_prob,
        market_odd=ev.odd,
        implied_prob=ev.implied_prob,
        expected_value=ev.expected_value,
        edge_pp=edge_pp,
        kelly_quarter=ev.kelly_quarter,
        suggested_stake_pct=suggested_pct,
        action=action,
    )


def _market_names(snapshot: SuperbetEventSnapshot) -> dict[str, str]:
    return getattr(snapshot, "baseball_market_names", None) or {}


def _moneyline_aportes(
    inplay: BaseballInPlayResult,
    snapshot: SuperbetEventSnapshot,
    bankroll: float,
) -> list[BaseballAporteAdvice]:
    out: list[BaseballAporteAdvice] = []
    ml = snapshot.moneyline_odds or snapshot.h2h_odds
    if not ml:
        return out
    names = _market_names(snapshot)
    market_display = resolve_baseball_market_display("moneyline", market_names=names)
    for key, prob in inplay.moneyline_probs.items():
        odd = ml.get(key)
        if odd is None:
            continue
        team = inplay.home_team if key == "1" else inplay.away_team
        label = format_baseball_selection_label("moneyline", team=team)
        opp = _aporte_from_eval("moneyline", key, label, market_display, prob, odd, bankroll)
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
    names = _market_names(snapshot)
    market_display = resolve_baseball_market_display("run_line", market_names=names)
    for line_key, sides in spread.items():
        line_val = None
        try:
            line_val = float(line_key.replace("p", "").replace("m", "-").replace("_", "."))
        except ValueError:
            pass
        for side, odd in sides.items():
            prob_key = f"{side}_{line_key}"
            prob = inplay.spread_probs.get(prob_key)
            if prob is None:
                continue
            team = inplay.home_team if side == "home" else inplay.away_team
            if line_val is None:
                label = f"{team} handicap ({line_key})"
            else:
                label = format_baseball_selection_label("run_line", team=team, line=line_val)
            opp = _aporte_from_eval("run_line", prob_key, label, market_display, prob, odd, bankroll)
            if opp:
                out.append(_format_stake_line(opp, bankroll))
    return out


def _team_total_aportes(
    inplay: BaseballInPlayResult,
    snapshot: SuperbetEventSnapshot,
    bankroll: float,
) -> list[BaseballAporteAdvice]:
    """Aportes em totais por time (mercado comum na Superbet BR para beisebol)."""
    out: list[BaseballAporteAdvice] = []
    team_totals = snapshot.team_totals or {}
    names = _market_names(snapshot)
    for side, lines in team_totals.items():
        if not lines:
            continue
        team = inplay.home_team if side == "home" else inplay.away_team
        market_display = resolve_baseball_market_display(
            "team_total_runs",
            team=team,
            side=side,
            market_names=names,
        )
        for line_str, sides in lines.items():
            try:
                line_val = float(str(line_str).replace(",", "."))
            except ValueError:
                continue
            line_key = f"{line_val:g}".replace(".", "_")
            for outcome, odd in sides.items():
                prob_key = f"{side}_{outcome}_{line_key}"
                prob = inplay.team_total_probs.get(prob_key)
                if prob is None:
                    continue
                label = format_baseball_selection_label(
                    "team_total_runs",
                    team=team,
                    outcome=outcome,
                    line=line_val,
                )
                opp = _aporte_from_eval(
                    "team_total_runs",
                    prob_key,
                    label,
                    market_display,
                    prob,
                    odd,
                    bankroll,
                )
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
    names = _market_names(snapshot)
    market_display = resolve_baseball_market_display("total_runs", market_names=names)
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
            label = format_baseball_selection_label("total_runs", outcome=outcome, line=line_val)
            opp = _aporte_from_eval("total_runs", prob_key, label, market_display, prob, odd, bankroll)
            if opp:
                out.append(_format_stake_line(opp, bankroll))
    return out


def _period_aportes(
    inplay: BaseballInPlayResult,
    snapshot: SuperbetEventSnapshot,
    bankroll: float,
) -> list[BaseballAporteAdvice]:
    """Aportes em mercados F5, por entrada, maior pontuação e corrida N."""
    out: list[BaseballAporteAdvice] = []
    period_markets = getattr(snapshot, "baseball_period_markets", None) or {}
    if not period_markets or not inplay.period_probs:
        return out

    names = _market_names(snapshot)
    probs = inplay.period_probs
    current_inning = inplay.inning
    f5 = period_markets.get("f5") or {}

    if current_inning <= 5:
        market_display = resolve_baseball_market_display("f5_total", market_names=names)
        for line_str, sides in (f5.get("total") or {}).items():
            try:
                line_val = float(str(line_str).replace(",", "."))
            except ValueError:
                continue
            lk = f"{line_val:g}".replace(".", "_")
            for outcome, odd in sides.items():
                prob_key = f"f5_{outcome}_{lk}"
                prob = probs.get(prob_key)
                if prob is None:
                    continue
                label = format_baseball_selection_label("f5_total", outcome=outcome, line=line_val)
                opp = _aporte_from_eval(
                    "f5_total", prob_key, label, market_display, prob, odd, bankroll
                )
                if opp:
                    out.append(_format_stake_line(opp, bankroll))

        market_display = resolve_baseball_market_display("f5_moneyline", market_names=names)
        for key, odd in (f5.get("moneyline") or {}).items():
            prob_key = f"f5_ml_{key}"
            prob = probs.get(prob_key)
            if prob is None:
                continue
            if key == "X":
                label = format_baseball_selection_label("f5_moneyline", outcome="X")
            else:
                team = inplay.home_team if key == "1" else inplay.away_team
                label = format_baseball_selection_label("f5_moneyline", team=team, outcome=key)
            opp = _aporte_from_eval(
                "f5_moneyline", prob_key, label, market_display, prob, odd, bankroll
            )
            if opp:
                out.append(_format_stake_line(opp, bankroll))

        market_display = resolve_baseball_market_display("f5_spread", market_names=names)
        for line_key, sides in (f5.get("spread") or {}).items():
            line_val = _parse_spread_line_key(line_key)
            for side, odd in sides.items():
                prob_key = f"f5_{side}_{line_key}"
                prob = probs.get(prob_key)
                if prob is None:
                    continue
                team = inplay.home_team if side == "home" else inplay.away_team
                label = format_baseball_selection_label(
                    "f5_spread",
                    team=team,
                    line=line_val if line_val is not None else 0.0,
                )
                opp = _aporte_from_eval(
                    "f5_spread", prob_key, label, market_display, prob, odd, bankroll
                )
                if opp:
                    out.append(_format_stake_line(opp, bankroll))

    for inn_str, bucket in (period_markets.get("innings") or {}).items():
        try:
            inn = int(inn_str)
        except ValueError:
            continue
        if current_inning > inn:
            continue

        market_display = resolve_baseball_market_display(
            "inning_total", inning=inn, market_names=names
        )
        for line_str, sides in (bucket.get("total") or {}).items():
            try:
                line_val = float(str(line_str).replace(",", "."))
            except ValueError:
                continue
            lk = f"{line_val:g}".replace(".", "_")
            for outcome, odd in sides.items():
                prob_key = f"inning_{inn}_{outcome}_{lk}"
                prob = probs.get(prob_key)
                if prob is None:
                    continue
                label = format_baseball_selection_label(
                    "inning_total", outcome=outcome, line=line_val, inning=inn
                )
                opp = _aporte_from_eval(
                    "inning_total", prob_key, label, market_display, prob, odd, bankroll
                )
                if opp:
                    out.append(_format_stake_line(opp, bankroll))

        market_display = resolve_baseball_market_display(
            "inning_1x2", inning=inn, market_names=names
        )
        for key, odd in (bucket.get("1x2") or {}).items():
            prob_key = f"inning_{inn}_1x2_{key}"
            prob = probs.get(prob_key)
            if prob is None:
                continue
            if key == "1":
                team = inplay.home_team
            elif key == "2":
                team = inplay.away_team
            else:
                team = None
            label = format_baseball_selection_label(
                "inning_1x2", team=team, outcome=key, inning=inn
            )
            opp = _aporte_from_eval(
                "inning_1x2", prob_key, label, market_display, prob, odd, bankroll
            )
            if opp:
                out.append(_format_stake_line(opp, bankroll))

    if period_markets.get("highest_inning"):
        market_display = resolve_baseball_market_display("highest_inning", market_names=names)
        for inn_str, odd in period_markets["highest_inning"].items():
            try:
                inn = int(inn_str)
            except ValueError:
                continue
            prob_key = f"highest_inning_{inn}"
            prob = probs.get(prob_key)
            if prob is None:
                continue
            label = format_baseball_selection_label("highest_inning", inning=inn)
            opp = _aporte_from_eval(
                "highest_inning", prob_key, label, market_display, prob, odd, bankroll
            )
            if opp:
                out.append(_format_stake_line(opp, bankroll))

    for run_str, sides in (period_markets.get("run_n") or {}).items():
        try:
            run_num = int(run_str)
        except ValueError:
            continue
        market_display = resolve_baseball_market_display(
            "run_n", run_number=run_num, market_names=names
        )
        for outcome, odd in sides.items():
            prob_key = f"run_{run_num}_{outcome}"
            prob = probs.get(prob_key)
            if prob is None:
                continue
            label = format_baseball_selection_label(
                "run_n", outcome=outcome, run_number=run_num
            )
            opp = _aporte_from_eval(
                "run_n", prob_key, label, market_display, prob, odd, bankroll
            )
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
    baseball_innings: list[dict[str, int]] | None = None,
) -> dict[str, Any]:
    """Constrói relatório de aportes para beisebol in-play."""
    aportes: list[BaseballAporteAdvice] = []
    aportes.extend(_moneyline_aportes(inplay, snapshot, bankroll))
    aportes.extend(_spread_aportes(inplay, snapshot, bankroll))
    aportes.extend(_total_aportes(inplay, snapshot, bankroll))
    aportes.extend(_team_total_aportes(inplay, snapshot, bankroll))
    aportes.extend(_period_aportes(inplay, snapshot, bankroll))
    aportes.sort(key=lambda a: a.expected_value, reverse=True)
    raw_aportes = [
        {
            "market": a.market,
            "outcome": a.outcome,
            "label": a.label,
            "market_display": a.market_display,
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
    ]
    filtered = filter_live_baseball_aportes(
        raw_aportes,
        home_score=inplay.home_score,
        away_score=inplay.away_score,
        inning=inplay.inning,
        baseball_innings=baseball_innings,
    )
    filtered, sanity_warnings = filter_sane_baseball_aportes(filtered, inplay=inplay)
    filtered = annotate_baseball_line_tiers(filtered, inplay=inplay)
    confidence = _confidence_score(inplay, [
        BaseballAporteAdvice(
            market=a["market"],
            outcome=a["outcome"],
            label=a["label"],
            market_display=a.get("market_display") or a["label"],
            model_prob=a["model_prob"],
            market_odd=a["market_odd"],
            implied_prob=a["implied_prob"],
            expected_value=a["expected_value"],
            edge_pp=a["edge_pp"],
            kelly_quarter=a["kelly_quarter"],
            suggested_stake_pct=a["suggested_stake_pct"],
            action=a["action"],
        )
        for a in filtered
    ])
    return {
        "aportes": filtered,
        "confidence": confidence,
        "sanity_warnings": sanity_warnings,
    }


def filter_live_baseball_aportes(
    aportes: list[dict[str, Any]],
    *,
    home_score: int,
    away_score: int,
    inning: int,
    baseball_innings: list[dict[str, int]] | None = None,
) -> list[dict[str, Any]]:
    """Remove aportes em mercados mortos ou período encerrado."""
    kept: list[dict[str, Any]] = []
    for a in aportes:
        dead, _ = is_dead_baseball_market(
            a.get("market", ""),
            a.get("outcome", ""),
            home_score=home_score,
            away_score=away_score,
            inning=inning,
            baseball_innings=baseball_innings,
        )
        if not dead:
            kept.append(a)
    return kept
