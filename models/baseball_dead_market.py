"""Mercados de beisebol já decididos ou encerrados pelo placar/entrada."""
from __future__ import annotations

import re
from typing import Any

_OVER_KEY_RE = re.compile(r"^(?:f5_|inning_\d+_)?over_(\d+)_(\d+)$")
_UNDER_KEY_RE = re.compile(r"^(?:f5_|inning_\d+_)?under_(\d+)_(\d+)$")
_TEAM_OVER_RE = re.compile(r"^(home|away)_over_(\d+)_(\d+)$")
_TEAM_UNDER_RE = re.compile(r"^(home|away)_under_(\d+)_(\d+)$")
_INNING_NUM_RE = re.compile(r"^inning_(\d+)_")


def _line_from_groups(g1: str, g2: str) -> float:
    return float(f"{g1}.{g2}")


def _f5_runs(baseball_innings: list[dict[str, int]] | None) -> tuple[int, int] | None:
    if not baseball_innings:
        return None
    h = sum(int(r.get("home") or 0) for r in baseball_innings if int(r.get("num") or 0) <= 5)
    a = sum(int(r.get("away") or 0) for r in baseball_innings if int(r.get("num") or 0) <= 5)
    return h, a


def is_dead_baseball_market(
    market: str,
    outcome: str,
    *,
    home_score: int,
    away_score: int,
    inning: int,
    baseball_innings: list[dict[str, int]] | None = None,
) -> tuple[bool, str | None]:
    """True quando o mercado não deve gerar aporte (linha morta ou período encerrado)."""
    total = int(home_score) + int(away_score)
    side = (outcome or "").lower()

    if market == "f5_total" and inning > 5:
        return True, "Mercado F5 encerrado após a 5ª entrada"

    if market == "f5_moneyline" and inning > 5:
        return True, "1X2 F5 encerrado após a 5ª entrada"

    if market == "f5_spread" and inning > 5:
        return True, "Handicap F5 encerrado após a 5ª entrada"

    if market in {"inning_total", "inning_1x2"}:
        m = _INNING_NUM_RE.search(outcome)
        if m and inning > int(m.group(1)):
            return True, f"Entrada {m.group(1)} já encerrada"

    if market == "total_runs":
        if side.startswith("over_"):
            m = _OVER_KEY_RE.match(side) or re.match(r"^over_(\d+)_(\d+)$", side)
            if m and total > _line_from_groups(m.group(1), m.group(2)):
                return True, f"Over {_line_from_groups(m.group(1), m.group(2)):g} já batido ({total} runs)"
        if side.startswith("under_"):
            m = _UNDER_KEY_RE.match(side) or re.match(r"^under_(\d+)_(\d+)$", side)
            if m and total > _line_from_groups(m.group(1), m.group(2)):
                return True, f"Under {_line_from_groups(m.group(1), m.group(2)):g} morto ({total} runs)"

    if market == "team_total_runs":
        m = _TEAM_OVER_RE.match(side) or _TEAM_UNDER_RE.match(side)
        if m:
            team_runs = home_score if m.group(1) == "home" else away_score
            line = _line_from_groups(m.group(2), m.group(3))
            if "over" in side and team_runs > line:
                return True, f"Over time {line:g} já batido"
            if "under" in side and team_runs > line:
                return True, f"Under time {line:g} morto"

    if market == "f5_total" and inning <= 5 and baseball_innings:
        f5 = _f5_runs(baseball_innings)
        if f5 and side.startswith(("over_", "under_")):
            f5_total = f5[0] + f5[1]
            m = re.match(r"^(over|under)_(\d+)_(\d+)$", side)
            if m:
                line = _line_from_groups(m.group(2), m.group(3))
                if m.group(1) == "over" and f5_total > line and inning > 5:
                    pass  # handled above
                if m.group(1) == "under" and f5_total > line:
                    return True, f"Under F5 {line:g} morto ({f5_total} runs em 1–5)"

    if market == "run_n" and side.endswith("_no"):
        m = re.match(r"^run_(\d+)_no$", side)
        if m and total >= int(m.group(1)):
            return True, f"Corrida {m.group(1)} já ocorreu — Não morto"

    if market == "run_n" and side.endswith("_yes"):
        m = re.match(r"^run_(\d+)_yes$", side)
        if m and total >= int(m.group(1)):
            return True, f"Corrida {m.group(1)} já garantida — Sim morto para novo aporte"

    return False, None


def list_dead_market_flags(
    aportes: list[dict[str, Any]],
    *,
    home_score: int,
    away_score: int,
    inning: int,
    baseball_innings: list[dict[str, int]] | None = None,
) -> list[str]:
    flags: list[str] = []
    seen: set[str] = set()
    for a in aportes:
        dead, reason = is_dead_baseball_market(
            a.get("market", ""),
            a.get("outcome", ""),
            home_score=home_score,
            away_score=away_score,
            inning=inning,
            baseball_innings=baseball_innings,
        )
        if dead and reason and reason not in seen:
            seen.add(reason)
            flags.append(reason)
    return flags

