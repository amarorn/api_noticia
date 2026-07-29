"""Extração de mercados por período/entrada no feed Superbet (beisebol)."""
from __future__ import annotations

import re
from typing import Any

from ingest.superbet.parser import (
    _handicap_line_key,
    _is_active_odd,
    _parse_handicap_line_value,
)

_F5_TOTAL_RE = re.compile(r"^entradas?\s+1\s+a\s+5\s*-\s*total", re.I)
_F5_ML_RE = re.compile(r"^entradas?\s+1\s+a\s+5\s*-\s*1\s*x?\s*2", re.I)
_F5_SPREAD_RE = re.compile(r"^entradas?\s+1\s+a\s+5\s*-\s*handicap", re.I)
_INNING_TOTAL_RE = re.compile(r"^entrada\s+(\d+)\s*-\s*total de corridas", re.I)
_INNING_1X2_RE = re.compile(r"^entrada\s+(\d+)\s*-\s*1\s*x?\s*2", re.I)
_HIGHEST_INNING_RE = re.compile(r"entrada com a maior pontua", re.I)
_RUN_N_RE = re.compile(r"^corrida\s+(\d+)\s*(?:\(|$)", re.I)


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


def _extract_highest_inning(market: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for odd in market.get("odds") or []:
        if not isinstance(odd, dict) or not _is_active_odd(odd):
            continue
        md = odd.get("metadata") or {}
        label = str(md.get("name") or md.get("info") or "")
        match = re.search(r"(\d+)", label)
        if not match:
            continue
        out[match.group(1)] = float(odd["price"])
    return out


def _extract_run_n(market: dict, run_num: int) -> dict[str, float]:
    out: dict[str, float] = {}
    for odd in market.get("odds") or []:
        if not isinstance(odd, dict) or not _is_active_odd(odd):
            continue
        md = odd.get("metadata") or {}
        label = str(md.get("name") or md.get("info") or "").lower()
        code = str(md.get("code") or "").upper()
        if code in {"YES", "SIM", "+"} or label.startswith(("sim", "yes")):
            out["yes"] = float(odd["price"])
        elif code in {"NO", "NAO", "NÃO", "-"} or label.startswith(("não", "nao", "no")):
            out["no"] = float(odd["price"])
    if not out:
        # fallback: primeira odd = sim, segunda = não
        active = [o for o in market.get("odds") or [] if isinstance(o, dict) and _is_active_odd(o)]
        if len(active) >= 2:
            out["yes"] = float(active[0]["price"])
            out["no"] = float(active[1]["price"])
    _ = run_num
    return out


def extract_baseball_period_markets(
    markets: list[dict],
    home_team: str,
    away_team: str,
) -> dict[str, Any]:
    """Agrupa mercados por entrada / F5 com odds e nomes de exibição."""
    result: dict[str, Any] = {
        "f5": {"total": {}, "moneyline": {}, "spread": {}},
        "innings": {},
        "highest_inning": {},
        "run_n": {},
        "display_names": {},
    }

    for market in markets:
        raw = str(market.get("name") or "").strip()
        if not raw:
            continue

        if _F5_TOTAL_RE.match(raw):
            result["f5"]["total"] = _extract_over_under(market)
            result["display_names"]["f5_total"] = raw
        elif _F5_ML_RE.match(raw):
            result["f5"]["moneyline"] = _extract_moneyline(market, home_team, away_team)
            result["display_names"]["f5_moneyline"] = raw
        elif _F5_SPREAD_RE.match(raw):
            result["f5"]["spread"] = _extract_spread(market, home_team, away_team)
            result["display_names"]["f5_spread"] = raw
        elif match := _INNING_TOTAL_RE.match(raw):
            inn = match.group(1)
            bucket = result["innings"].setdefault(inn, {"total": {}, "1x2": {}})
            bucket["total"] = _extract_over_under(market)
            result["display_names"][f"inning_{inn}_total"] = raw
        elif match := _INNING_1X2_RE.match(raw):
            inn = match.group(1)
            bucket = result["innings"].setdefault(inn, {"total": {}, "1x2": {}})
            bucket["1x2"] = _extract_moneyline(market, home_team, away_team)
            result["display_names"][f"inning_{inn}_1x2"] = raw
        elif _HIGHEST_INNING_RE.search(raw):
            result["highest_inning"] = _extract_highest_inning(market)
            result["display_names"]["highest_inning"] = raw
        elif match := _RUN_N_RE.match(raw):
            run_num = int(match.group(1))
            result["run_n"][str(run_num)] = _extract_run_n(market, run_num)
            result["display_names"][f"run_{run_num}"] = raw

    return result
