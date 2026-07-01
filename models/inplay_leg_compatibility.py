"""Regras de compatibilidade entre pernas in-play (Criar Aposta / múltiplas)."""

from __future__ import annotations

import re

from models.wc_bet_advice import parse_period_handicap_market

_HCAP_MARKET_RE = re.compile(r"^(?:ft|1h|2h)_(hcap|ah)_(home|away)_")


def period_of_market(market: str) -> str:
    if market.startswith("1h_"):
        return "1h"
    if market.startswith("2h_"):
        return "2h"
    return "ft"


def h2h_period(market: str) -> str:
    if market == "h2h" or market.endswith("_h2h"):
        return period_of_market(market) if market != "h2h" else "ft"
    return period_of_market(market)


def leg_family(market: str) -> str:
    if market.endswith("_h2h") or market == "h2h":
        return "h2h"
    if "cs_" in market or "exact" in market or "over_" in market:
        return "goals"
    if "hcap" in market or "_ah_" in market:
        return "handicap"
    return "other"


def is_h2h_market(market: str) -> bool:
    return market == "h2h" or market.endswith("_h2h")


def h2h_outcome_side(outcome: str) -> str | None:
    o = outcome.lower()
    if o in {"1", "home"}:
        return "home"
    if o in {"2", "away"}:
        return "away"
    if o in {"x", "draw"}:
        return "draw"
    return None


def totals_bucket(market: str) -> tuple[str, str] | None:
    period = period_of_market(market)
    body = market[3:] if market.startswith(("1h_", "2h_")) else market
    if body.startswith("home_over_"):
        return period, "home"
    if body.startswith("away_over_"):
        return period, "away"
    if body.startswith("corners_over_"):
        return period, "corners"
    if body.startswith("cards_over_"):
        return period, "cards"
    if body.startswith("over_"):
        return period, "goals"
    return None


def parse_handicap(market: str) -> tuple[str, str, float] | None:
    if "_ah_" in market:
        return None
    return parse_period_handicap_market(market)


def handicaps_conflict(a_market: str, b_market: str) -> bool:
    ha = parse_handicap(a_market)
    hb = parse_handicap(b_market)
    if not ha or not hb:
        return False
    pa, sa, la = ha
    pb, sb, lb = hb
    if pa != pb:
        return False
    # Superbet Criar Aposta: no máximo um handicap por período (espelhos ex.: -1.5 vs +1.5)
    if sa == sb and la != lb:
        return True
    if sa != sb and abs(la + lb) < 0.01:
        return True
    if sa != sb and la <= -0.5 and lb <= -0.5:
        return True
    return True


def h2h_conflicts_handicap(h2h_market: str, h2h_outcome: str, hcap_market: str) -> bool:
    h = parse_handicap(hcap_market)
    if not h:
        return False
    if h2h_period(h2h_market) != h[0]:
        return False
    side = h2h_outcome_side(h2h_outcome)
    if side is None:
        return False
    _, team, line = h
    if side == "draw":
        return line <= -0.5
    # Superbet Criar Aposta: 1X2 no mesmo time do handicap anula/rejeita a outra perna
    if side == team:
        return True
    if side == "home" and team == "away" and line <= -0.5:
        return True
    if side == "away" and team == "home" and line <= -0.5:
        return True
    return False


def is_correct_score_market(market: str) -> bool:
    return "_cs_" in market


def correct_scores_conflict(a_market: str, b_market: str) -> bool:
    """Dois placares exatos no mesmo período são mutuamente exclusivos (ex.: 2T 0x0 + 2T 1x0)."""
    if not is_correct_score_market(a_market) or not is_correct_score_market(b_market):
        return False
    return period_of_market(a_market) == period_of_market(b_market)


def combo_correct_score_count(markets: list[str]) -> int:
    return sum(1 for m in markets if is_correct_score_market(m))


def is_btts_market(market: str) -> bool:
    return market == "btts"


def btts_conflicts_correct_score(btts_market: str, cs_market: str) -> bool:
    """Superbet rejeita BTTS + Resultado Correto no Criar Aposta (ex.: Ambos marcam + 2T RC 1x0)."""
    return is_btts_market(btts_market) and is_correct_score_market(cs_market)


def handicap_requires_win(market: str) -> tuple[str, str] | None:
    """Handicap com linha ≤ −0,5 exige vitória do time (ex.: visitante −0,5)."""
    parsed = parse_handicap(market)
    if not parsed or parsed[2] > -0.5:
        return None
    return parsed[0], parsed[1]


def _market_body(market: str) -> tuple[str, str]:
    """Retorna (periodo, corpo sem prefixo ft/1h/2h)."""
    if market.startswith("1h_"):
        return "1h", market[3:]
    if market.startswith("2h_"):
        return "2h", market[3:]
    if market.startswith("ft_"):
        return "ft", market[3:]
    return period_of_market(market), market


def _parse_team_over_line(market: str) -> tuple[str, str, float] | None:
    """Retorna (periodo, lado, linha) para home_over_3_5 / away_over_1_5 (FT ou prefixo de período)."""
    period, body = _market_body(market)
    for side in ("home", "away"):
        prefix = f"{side}_over_"
        if not body.startswith(prefix):
            continue
        raw = body[len(prefix) :].replace("_", ".")
        try:
            line = float(raw)
        except ValueError:
            return None
        return period, side, line
    return None


def _parse_exact_team_goals(market: str) -> tuple[str, str, int] | None:
    """Retorna (periodo, lado, gols exatos) para ft_exact_home_4 etc."""
    period, body = _market_body(market)
    for side in ("home", "away"):
        prefix = f"exact_{side}_"
        if not body.startswith(prefix):
            continue
        raw = body[len(prefix) :].replace("_", ".")
        try:
            goals = int(float(raw))
        except ValueError:
            return None
        return period, side, goals
    return None


def _offense_side(market: str, outcome: str) -> str | None:
    """Lado ofensivo favorecido pela perna (mandante ou visitante)."""
    if market == "next_goal":
        return h2h_outcome_side(outcome)
    if market.startswith("combo_home"):
        return "home"
    if market.startswith("combo_away"):
        return "away"
    if is_h2h_market(market):
        return h2h_outcome_side(outcome)
    team_over = _parse_team_over_line(market)
    if team_over and outcome.lower() in {"yes", "sim"}:
        return team_over[1]
    exact = _parse_exact_team_goals(market)
    if exact and outcome.lower() in {"yes", "sim"}:
        return exact[1]
    return None


# Gols do adversário a partir desta linha anulam handicap “precisa vencer” (ex.: 4×1 mata visitante −0,5).
_OPPONENT_GOALS_ANNUL_WIN_HCAP = 4


def handicap_conflicts_opposite_offense(
    hcap_market: str,
    other_market: str,
    other_outcome: str,
) -> bool:
    """Handicap que exige vitória vs perna que empurra o adversário a marcar demais (anula o bilhete cedo)."""
    win_req = handicap_requires_win(hcap_market)
    if not win_req:
        return False

    hcap_period, win_side = win_req
    opp = "away" if win_side == "home" else "home"
    other_period = period_of_market(other_market)
    if hcap_period != other_period and not (hcap_period == "ft" and other_period == "ft"):
        return False

    offense = _offense_side(other_market, other_outcome)
    if offense != opp:
        return False

    if other_market == "next_goal":
        return True

    team_over = _parse_team_over_line(other_market)
    if team_over and team_over[1] == opp and other_outcome.lower() in {"yes", "sim"}:
        # home_over_3_5 ⇒ 4+ gols do mandante — visitante −0,5 só vira com 5+ gols
        if team_over[2] >= _OPPONENT_GOALS_ANNUL_WIN_HCAP - 0.5:
            return True

    exact = _parse_exact_team_goals(other_market)
    if exact and exact[1] == opp and other_outcome.lower() in {"yes", "sim"}:
        if exact[2] >= _OPPONENT_GOALS_ANNUL_WIN_HCAP:
            return True

    if win_side == "away" and other_market == "combo_home_btts" and other_outcome.lower() in {"yes", "sim"}:
        return True
    if win_side == "home" and other_market == "combo_away_btts" and other_outcome.lower() in {"yes", "sim"}:
        return True

    return False


def _same_period(a: str, b: str) -> bool:
    return a == b or (a == "ft" and b == "ft")


def handicap_conflicts_same_team_offense(
    hcap_market: str,
    other_market: str,
    other_outcome: str,
) -> bool:
    """Handicap + gols do mesmo time no Criar Aposta (Superbet descarta uma perna)."""
    parsed = parse_handicap(hcap_market)
    if not parsed:
        return False
    hcap_period, hcap_side, _line = parsed
    if other_outcome.lower() not in {"yes", "sim"}:
        return False

    team_over = _parse_team_over_line(other_market)
    if team_over:
        period, side, _line = team_over
        if side == hcap_side and _same_period(hcap_period, period):
            return True

    exact = _parse_exact_team_goals(other_market)
    if exact:
        period, side, _goals = exact
        if side == hcap_side and _same_period(hcap_period, period):
            return True

    return False


def legs_compatible(a_market: str, a_outcome: str, b_market: str, b_outcome: str) -> bool:
    """True se as duas pernas podem ir juntas no Criar Aposta Superbet."""
    if a_market == b_market:
        return a_outcome == b_outcome

    if btts_conflicts_correct_score(a_market, b_market) or btts_conflicts_correct_score(b_market, a_market):
        return False

    pa, pb = period_of_market(a_market), period_of_market(b_market)

    if is_h2h_market(a_market) and is_h2h_market(b_market) and pa == pb:
        return False

    if pa == pb:
        fa, fb = leg_family(a_market), leg_family(b_market)
        if fa == "h2h" and fb == "goals":
            return False
        if fa == "goals" and fb == "h2h":
            return False

        ta, tb = totals_bucket(a_market), totals_bucket(b_market)
        if ta and tb and ta == tb:
            return False

        if fa == "goals" and fb == "goals":
            if "over_" in a_market and "over_" in b_market:
                return False
            if correct_scores_conflict(a_market, b_market):
                return False
            if "cs_" in a_market and ("over_" in b_market or "exact" in b_market):
                return False
            if "cs_" in b_market and ("over_" in a_market or "exact" in a_market):
                return False

        if handicaps_conflict(a_market, b_market):
            return False

        if is_h2h_market(a_market) and leg_family(b_market) == "handicap":
            if h2h_conflicts_handicap(a_market, a_outcome, b_market):
                return False
        if is_h2h_market(b_market) and leg_family(a_market) == "handicap":
            if h2h_conflicts_handicap(b_market, b_outcome, a_market):
                return False

    if leg_family(a_market) == "handicap" and handicap_conflicts_opposite_offense(
        a_market, b_market, b_outcome
    ):
        return False
    if leg_family(b_market) == "handicap" and handicap_conflicts_opposite_offense(
        b_market, a_market, a_outcome
    ):
        return False

    if leg_family(a_market) == "handicap" and handicap_conflicts_same_team_offense(
        a_market, b_market, b_outcome
    ):
        return False
    if leg_family(b_market) == "handicap" and handicap_conflicts_same_team_offense(
        b_market, a_market, a_outcome
    ):
        return False

    return True


def is_superbet_bet_builder_market(market: str) -> bool:
    """Mercados aceitos no Criar Aposta Superbet (múltipla na mesma partida)."""
    if "_ah_" in market:
        return False
    if market.startswith(("2h_hcap_", "2h_ah_", "1h_hcap_", "1h_ah_")):
        return False
    if "hcap" in market and not market.startswith("ft_hcap_"):
        return False
    return True


def combo_handicap_count(markets: list[str]) -> int:
    return sum(
        1
        for m in markets
        if leg_family(m) == "handicap" or "_ah_" in m
    )


def combo_legs_compatible(legs: list[tuple[str, str]]) -> bool:
    """Valida múltipla inteira para Criar Aposta."""
    markets = [m for m, _ in legs]
    if combo_handicap_count(markets) > 1:
        return False
    if combo_correct_score_count(markets) > 1:
        return False
    for i in range(len(legs)):
        for j in range(i + 1, len(legs)):
            a_m, a_o = legs[i]
            b_m, b_o = legs[j]
            if not legs_compatible(a_m, a_o, b_m, b_o):
                return False
    return True


__all__ = [
    "legs_compatible",
    "handicaps_conflict",
    "handicap_requires_win",
    "handicap_conflicts_opposite_offense",
    "handicap_conflicts_same_team_offense",
    "h2h_conflicts_handicap",
    "is_superbet_bet_builder_market",
    "combo_legs_compatible",
    "correct_scores_conflict",
    "btts_conflicts_correct_score",
]
