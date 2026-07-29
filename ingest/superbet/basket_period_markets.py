"""Extração de mercados por quarto e props de basquete no feed Superbet."""
from __future__ import annotations

import re
from typing import Any

from ingest.superbet.parser import (
    _handicap_line_key,
    _is_active_odd,
    _parse_handicap_line_value,
)

_QUARTER_TOTAL_RE = re.compile(
    r"^(\d+)[º°o]?\s*quarto\s*-\s*total de pontos(?:\s+de\s+(.+))?$",
    re.I,
)
_QUARTER_ML_RE = re.compile(r"^(\d+)[º°o]?\s*quarto\s*-\s*1\s*x?\s*2\s*$", re.I)
_QUARTER_SPREAD_RE = re.compile(r"^(\d+)[º°o]?\s*quarto\s*-\s*handicap\s*$", re.I)
_ODD_EVEN_RE = re.compile(r"^ímpar\s*/\s*par|^impar\s*/\s*par", re.I)


def _extract_over_under(market: dict) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for odd in market.get("odds") or []:
        if not isinstance(odd, dict) or not _is_active_odd(odd):
            continue
        md = odd.get("metadata") or {}
        line = _parse_handicap_line_value(
            str(md.get("special_bet_value") or md.get("info") or md.get("name") or "")
        )
        if line is None:
            continue
        label = str(md.get("name") or "").lower()
        code = str(md.get("code") or "").strip()
        outcome: str | None = None
        if code == "+" or label.startswith(("over", "mais", "acima")):
            outcome = "over"
        elif code == "-" or label.startswith(("under", "menos", "abaixo")):
            outcome = "under"
        if outcome is None:
            continue
        out.setdefault(f"{line:g}", {})[outcome] = float(odd["price"])
    return out


def _extract_moneyline(
    market: dict,
    home_team: str,
    away_team: str,
) -> dict[str, float]:
    out: dict[str, float] = {}
    home_l = home_team.lower()
    away_l = away_team.lower()
    for odd in market.get("odds") or []:
        if not isinstance(odd, dict) or not _is_active_odd(odd):
            continue
        md = odd.get("metadata") or {}
        code = str(md.get("code") or md.get("name") or "").upper()
        label = str(md.get("name") or md.get("info") or "").lower()
        price = float(odd["price"])
        if code in {"X", "0", "DRAW", "EMPATE"} or "empate" in label:
            out["X"] = price
        elif code == "1" or code == "HOME" or (home_l and home_l in label):
            out["1"] = price
        elif code == "2" or code == "AWAY" or (away_l and away_l in label):
            out["2"] = price
    return out


def _extract_spread(
    market: dict,
    home_team: str,
    away_team: str,
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    home_l = home_team.lower()
    away_l = away_team.lower()
    for odd in market.get("odds") or []:
        if not isinstance(odd, dict) or not _is_active_odd(odd):
            continue
        md = odd.get("metadata") or {}
        line_raw = str(md.get("special_bet_value") or md.get("info") or md.get("name") or "")
        line = _parse_handicap_line_value(line_raw)
        if line is None:
            continue
        label = str(md.get("name") or md.get("info") or "").lower()
        code = str(md.get("code") or "").upper()
        side: str | None = None
        if code == "1" or code == "HOME" or (home_l and home_l in label):
            side = "home"
        elif code == "2" or code == "AWAY" or (away_l and away_l in label):
            side = "away"
        if side is None:
            continue
        lk = _handicap_line_key(line)
        out.setdefault(lk, {})[side] = float(odd["price"])
    return out


def _extract_odd_even(market: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for odd in market.get("odds") or []:
        if not isinstance(odd, dict) or not _is_active_odd(odd):
            continue
        md = odd.get("metadata") or {}
        label = str(md.get("name") or md.get("info") or "").lower()
        code = str(md.get("code") or "").upper()
        if "ímpar" in label or "impar" in label or code in {"ODD", "IMPAR"}:
            out["odd"] = float(odd["price"])
        elif "par" in label or code in {"EVEN", "PAR"}:
            out["even"] = float(odd["price"])
    return out


def _team_side_from_label(label: str, home_team: str, away_team: str) -> str | None:
    low = label.lower()
    home_l = home_team.lower()
    away_l = away_team.lower()
    if home_l and home_l in low:
        return "home"
    if away_l and away_l in low:
        return "away"
    return None


def extract_basket_period_markets(
    markets: list[dict],
    home_team: str,
    away_team: str,
) -> dict[str, Any]:
    """Agrupa mercados por quarto (total, spread, 1X2, total por time)."""
    result: dict[str, Any] = {
        "quarters": {},
        "odd_even": {},
        "display_names": {},
    }

    for market in markets:
        raw = str(market.get("name") or "").strip()
        low = raw.lower()

        odd_even = _ODD_EVEN_RE.match(low)
        if odd_even and "prorroga" in low:
            extracted = _extract_odd_even(market)
            if extracted:
                result["odd_even"] = extracted
                result["display_names"]["odd_even"] = raw
            continue

        match_total = _QUARTER_TOTAL_RE.match(raw)
        if match_total:
            q_num = int(match_total.group(1))
            team_label = (match_total.group(2) or "").strip()
            q_key = str(q_num)
            bucket = result["quarters"].setdefault(
                q_key,
                {"total": {}, "team_total": {"home": {}, "away": {}}, "moneyline": {}, "spread": {}},
            )
            lines = _extract_over_under(market)
            if team_label:
                side = _team_side_from_label(team_label, home_team, away_team)
                if side:
                    bucket["team_total"][side] = lines
                    result["display_names"][f"q{q_num}_team_total_{side}"] = raw
            elif lines:
                bucket["total"] = lines
                result["display_names"][f"q{q_num}_total"] = raw
            continue

        match_ml = _QUARTER_ML_RE.match(raw)
        if match_ml:
            q_num = int(match_ml.group(1))
            q_key = str(q_num)
            bucket = result["quarters"].setdefault(
                q_key,
                {"total": {}, "team_total": {"home": {}, "away": {}}, "moneyline": {}, "spread": {}},
            )
            ml = _extract_moneyline(market, home_team, away_team)
            if ml:
                bucket["moneyline"] = ml
                result["display_names"][f"q{q_num}_moneyline"] = raw
            continue

        match_spread = _QUARTER_SPREAD_RE.match(raw)
        if match_spread:
            q_num = int(match_spread.group(1))
            q_key = str(q_num)
            bucket = result["quarters"].setdefault(
                q_key,
                {"total": {}, "team_total": {"home": {}, "away": {}}, "moneyline": {}, "spread": {}},
            )
            spread = _extract_spread(market, home_team, away_team)
            if spread:
                bucket["spread"] = spread
                result["display_names"][f"q{q_num}_spread"] = raw

    return result


def _is_basket_team_total_market(name: str, team: str) -> bool:
    low = name.strip().lower()
    if not team or team.lower() not in low:
        return False
    if "total" not in low and "pontua" not in low:
        return False
    if re.match(r"^\d+[º°o]?\s*quarto", low):
        return False
    return True


def extract_basket_team_totals(
    markets: list[dict],
    home_team: str,
    away_team: str,
) -> dict[str, dict[str, dict[str, float]]]:
    """Total de pontos por time (jogo completo, incl. OT no rótulo Superbet)."""
    out: dict[str, dict[str, dict[str, float]]] = {"home": {}, "away": {}}
    for market in markets:
        raw = str(market.get("name") or "").strip()
        lines = _extract_over_under(market)
        if not lines:
            continue
        if _is_basket_team_total_market(raw, home_team):
            out["home"].update(lines)
        elif _is_basket_team_total_market(raw, away_team):
            out["away"].update(lines)
    return out


__all__ = ["extract_basket_period_markets", "extract_basket_team_totals"]
