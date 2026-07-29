"""Recomendações de aporte para basquete in-play (EV/Kelly)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import settings
from ingest.superbet.parser import SuperbetEventSnapshot
from models.basket_inplay import BasketInPlayResult
from models.basket_market_labels import format_basket_selection_label, resolve_basket_market_display
from models.economics import live_effective_min_edge
from models.ev_value import evaluate_outcome


@dataclass
class BasketAporteAdvice:
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


def _market_names(snapshot: SuperbetEventSnapshot) -> dict[str, str]:
    period = getattr(snapshot, "basket_period_markets", None) or {}
    return dict(period.get("display_names") or {})


def _parse_spread_line_key(line_key: str) -> float | None:
    try:
        return float(line_key.replace("p", "").replace("m", "-").replace("_", "."))
    except ValueError:
        return None


def _spread_side_line(prob_key: str) -> tuple[str, float] | None:
    for side in ("home", "away"):
        needle = f"_{side}_"
        if needle in prob_key:
            line_key = prob_key.split(needle, 1)[1]
            line_val = _parse_spread_line_key(line_key)
            if line_val is not None:
                return side, line_val
    return None


def _format_stake_line(opp: BasketAporteAdvice, bankroll: float) -> BasketAporteAdvice:
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
) -> BasketAporteAdvice | None:
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
    return BasketAporteAdvice(
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


def _moneyline_aportes(
    inplay: BasketInPlayResult,
    snapshot: SuperbetEventSnapshot,
    bankroll: float,
) -> list[BasketAporteAdvice]:
    out: list[BasketAporteAdvice] = []
    ml = snapshot.moneyline_odds
    if not ml:
        return out
    names = _market_names(snapshot)
    market_display = resolve_basket_market_display("moneyline", market_names=names)
    for key, prob in inplay.moneyline_probs.items():
        odd = ml.get(key)
        if odd is None:
            continue
        team = inplay.home_team if key == "1" else inplay.away_team
        label = format_basket_selection_label("moneyline", team=team)
        opp = _aporte_from_eval("moneyline", key, label, market_display, prob, odd, bankroll)
        if opp:
            out.append(_format_stake_line(opp, bankroll))
    return out


def _spread_aportes(
    inplay: BasketInPlayResult,
    snapshot: SuperbetEventSnapshot,
    bankroll: float,
) -> list[BasketAporteAdvice]:
    out: list[BasketAporteAdvice] = []
    spread = snapshot.spread_odds
    if not spread:
        return out
    names = _market_names(snapshot)
    market_display = resolve_basket_market_display("spread", market_names=names)
    for line_key, sides in spread.items():
        line_val = _parse_spread_line_key(line_key)
        for side, odd in sides.items():
            prob_key = f"{side}_{line_key}"
            prob = inplay.spread_probs.get(prob_key)
            if prob is None or line_val is None:
                continue
            team = inplay.home_team if side == "home" else inplay.away_team
            label = format_basket_selection_label("spread", team=team, line=line_val)
            opp = _aporte_from_eval("spread", prob_key, label, market_display, prob, odd, bankroll)
            if opp:
                out.append(_format_stake_line(opp, bankroll))
    return out


def _total_aportes(
    inplay: BasketInPlayResult,
    snapshot: SuperbetEventSnapshot,
    bankroll: float,
) -> list[BasketAporteAdvice]:
    out: list[BasketAporteAdvice] = []
    totals = snapshot.total_points_odds
    if not totals:
        return out
    names = _market_names(snapshot)
    market_display = resolve_basket_market_display("total", market_names=names)
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
            label = format_basket_selection_label("total", outcome=outcome, line=line_val)
            opp = _aporte_from_eval("total", prob_key, label, market_display, prob, odd, bankroll)
            if opp:
                out.append(_format_stake_line(opp, bankroll))
    return out


def _team_total_aportes(
    inplay: BasketInPlayResult,
    snapshot: SuperbetEventSnapshot,
    bankroll: float,
) -> list[BasketAporteAdvice]:
    out: list[BasketAporteAdvice] = []
    period_markets = getattr(snapshot, "basket_period_markets", None) or {}
    team_totals = period_markets.get("team_totals_ft") or {}
    names = _market_names(snapshot)
    for side, lines in team_totals.items():
        if not lines:
            continue
        team = inplay.home_team if side == "home" else inplay.away_team
        market_display = resolve_basket_market_display(
            "team_total_points", team=team, side=side, market_names=names
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
                label = format_basket_selection_label(
                    "team_total_points", team=team, outcome=outcome, line=line_val
                )
                opp = _aporte_from_eval(
                    "team_total_points", prob_key, label, market_display, prob, odd, bankroll
                )
                if opp:
                    out.append(_format_stake_line(opp, bankroll))
    return out


def _regulation_ml_aportes(
    inplay: BasketInPlayResult,
    snapshot: SuperbetEventSnapshot,
    bankroll: float,
) -> list[BasketAporteAdvice]:
    out: list[BasketAporteAdvice] = []
    ml = getattr(snapshot, "regulation_ml_odds", None) or {}
    if not ml:
        return out
    names = _market_names(snapshot)
    market_display = resolve_basket_market_display("regulation_ml", market_names=names)
    for key, prob in inplay.regulation_ml_probs.items():
        odd = ml.get(key)
        if odd is None:
            continue
        if key == "X":
            label = format_basket_selection_label("regulation_ml", outcome="X")
        else:
            team = inplay.home_team if key == "1" else inplay.away_team
            label = format_basket_selection_label("regulation_ml", team=team, outcome=key)
        opp = _aporte_from_eval("regulation_ml", key, label, market_display, prob, odd, bankroll)
        if opp:
            out.append(_format_stake_line(opp, bankroll))
    return out


def _odd_even_aportes(
    inplay: BasketInPlayResult,
    snapshot: SuperbetEventSnapshot,
    bankroll: float,
) -> list[BasketAporteAdvice]:
    out: list[BasketAporteAdvice] = []
    odds = getattr(snapshot, "odd_even_odds", None) or {}
    if not odds:
        return out
    names = _market_names(snapshot)
    market_display = resolve_basket_market_display("odd_even", market_names=names)
    for key, prob in inplay.odd_even_probs.items():
        odd = odds.get(key)
        if odd is None:
            continue
        label = format_basket_selection_label("odd_even", outcome=key)
        opp = _aporte_from_eval("odd_even", key, label, market_display, prob, odd, bankroll)
        if opp:
            out.append(_format_stake_line(opp, bankroll))
    return out


def _period_aportes(
    inplay: BasketInPlayResult,
    snapshot: SuperbetEventSnapshot,
    bankroll: float,
) -> list[BasketAporteAdvice]:
    out: list[BasketAporteAdvice] = []
    period_markets = getattr(snapshot, "basket_period_markets", None) or {}
    if not period_markets or not inplay.period_probs:
        return out

    probs = inplay.period_probs
    names = _market_names(snapshot)
    minute = inplay.minute
    current_quarter = min(
        max(1, round(inplay.match_minutes / 10)),
        int(minute // 10) + 1,
    )

    for q_str, bucket in (period_markets.get("quarters") or {}).items():
        try:
            q_num = int(q_str)
        except ValueError:
            continue
        if q_num < current_quarter:
            continue

        market_total = resolve_basket_market_display(
            f"quarter_{q_num}_total", quarter=q_num, market_names=names
        )
        for line_str, sides in (bucket.get("total") or {}).items():
            try:
                line_val = float(str(line_str).replace(",", "."))
            except ValueError:
                continue
            lk = f"{line_val:g}".replace(".", "_")
            for outcome, odd in sides.items():
                prob_key = f"q{q_num}_{outcome}_{lk}"
                prob = probs.get(prob_key)
                if prob is None:
                    continue
                label = format_basket_selection_label(
                    f"quarter_{q_num}_total", outcome=outcome, line=line_val
                )
                opp = _aporte_from_eval(
                    f"quarter_{q_num}_total", prob_key, label, market_total, prob, odd, bankroll
                )
                if opp:
                    out.append(_format_stake_line(opp, bankroll))

        for side, lines in (bucket.get("team_total") or {}).items():
            team = inplay.home_team if side == "home" else inplay.away_team
            market_display = resolve_basket_market_display(
                f"quarter_{q_num}_team_total",
                quarter=q_num,
                team=team,
                side=side,
                market_names=names,
            )
            for line_str, sides in (lines or {}).items():
                try:
                    line_val = float(str(line_str).replace(",", "."))
                except ValueError:
                    continue
                lk = f"{line_val:g}".replace(".", "_")
                for outcome, odd in sides.items():
                    prob_key = f"q{q_num}_{side}_{outcome}_{lk}"
                    prob = probs.get(prob_key)
                    if prob is None:
                        continue
                    label = format_basket_selection_label(
                        f"quarter_{q_num}_team_total",
                        team=team,
                        outcome=outcome,
                        line=line_val,
                    )
                    opp = _aporte_from_eval(
                        f"quarter_{q_num}_team_total",
                        prob_key,
                        label,
                        market_display,
                        prob,
                        odd,
                        bankroll,
                    )
                    if opp:
                        out.append(_format_stake_line(opp, bankroll))

        market_ml = resolve_basket_market_display(
            f"quarter_{q_num}_moneyline", quarter=q_num, market_names=names
        )
        for key, odd in (bucket.get("moneyline") or {}).items():
            prob_key = f"q{q_num}_ml_{key}"
            prob = probs.get(prob_key)
            if prob is None:
                continue
            if key == "X":
                label = format_basket_selection_label(f"quarter_{q_num}_moneyline", outcome="X")
            else:
                team = inplay.home_team if key == "1" else inplay.away_team
                label = format_basket_selection_label(
                    f"quarter_{q_num}_moneyline", team=team, outcome=key
                )
            opp = _aporte_from_eval(
                f"quarter_{q_num}_moneyline", prob_key, label, market_ml, prob, odd, bankroll
            )
            if opp:
                out.append(_format_stake_line(opp, bankroll))

        market_spread = resolve_basket_market_display(
            f"quarter_{q_num}_spread", quarter=q_num, market_names=names
        )
        for line_key, sides in (bucket.get("spread") or {}).items():
            for side, odd in sides.items():
                prob_key = f"q{q_num}_{side}_{line_key}"
                prob = probs.get(prob_key)
                if prob is None:
                    continue
                team = inplay.home_team if side == "home" else inplay.away_team
                line_val = _parse_spread_line_key(line_key)
                if line_val is None:
                    label = team
                else:
                    label = format_basket_selection_label(
                        f"quarter_{q_num}_spread", team=team, line=line_val
                    )
                opp = _aporte_from_eval(
                    f"quarter_{q_num}_spread", prob_key, label, market_spread, prob, odd, bankroll
                )
                if opp:
                    out.append(_format_stake_line(opp, bankroll))

    return out


def _confidence_score(inplay: BasketInPlayResult, aportes: list[BasketAporteAdvice]) -> dict[str, Any]:
    max_edge = max((a.edge_pp for a in aportes), default=0.0)
    ml_diff = abs(inplay.prob_home_win - inplay.prob_away_win)
    score = min(0.95, 0.45 + max_edge / 100.0 + ml_diff * 0.15)
    label = "Alta" if score >= 0.70 else "Média" if score >= 0.55 else "Baixa"
    return {"score": round(score, 4), "label": label, "max_edge_pp": round(max_edge, 2)}


def build_basket_bet_advice_report(
    *,
    inplay: BasketInPlayResult,
    snapshot: SuperbetEventSnapshot,
    bankroll: float = 1000.0,
) -> dict[str, Any]:
    """Constrói relatório de aportes para basquete in-play."""
    aportes: list[BasketAporteAdvice] = []
    aportes.extend(_moneyline_aportes(inplay, snapshot, bankroll))
    aportes.extend(_spread_aportes(inplay, snapshot, bankroll))
    aportes.extend(_total_aportes(inplay, snapshot, bankroll))
    aportes.extend(_team_total_aportes(inplay, snapshot, bankroll))
    aportes.extend(_regulation_ml_aportes(inplay, snapshot, bankroll))
    aportes.extend(_odd_even_aportes(inplay, snapshot, bankroll))
    aportes.extend(_period_aportes(inplay, snapshot, bankroll))
    aportes.sort(key=lambda a: a.expected_value, reverse=True)
    confidence = _confidence_score(inplay, aportes)

    return {
        "aportes": [
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
        ],
        "confidence": confidence,
    }
