"""Mercados in-play já decididos pelo placar (não recomendar/apostar)."""
from __future__ import annotations

import re


_OVER_LINE_RE = re.compile(r"^(?:2h_|1h_)?over_(\d+)_(\d+)$")
_BTTS_MARKETS = frozenset({"btts", "combo_btts_over_2_5", "combo_btts_over_3_5", "combo_home_btts", "combo_away_btts"})


def _parse_total_line(market: str) -> float | None:
    m = _OVER_LINE_RE.match(market)
    if not m:
        return None
    return float(f"{m.group(1)}.{m.group(2)}")


def is_dead_inplay_market(
    market: str,
    outcome: str,
    *,
    home_score: int,
    away_score: int,
) -> tuple[bool, str | None]:
    """True quando o resultado do mercado já está garantido pelo placar."""
    total = int(home_score) + int(away_score)
    side = (outcome or "").strip().lower()
    yes = side in {"yes", "sim", "1", "home", "away"}

    if market in _BTTS_MARKETS or market == "btts":
        both_scored = home_score > 0 and away_score > 0
        if market == "btts":
            if yes and both_scored:
                return True, "BTTS Sim já garantido"
            if not yes and both_scored:
                return True, "BTTS Não morto (ambos já marcaram)"
        if yes and both_scored and market.startswith("combo_btts"):
            return True, "Combo BTTS já garantido"
        if not yes and both_scored and market == "combo_btts_over_2_5":
            return True, "Combo BTTS+Over morto"
        return False, None

    line = _parse_total_line(market)
    if line is not None:
        if yes and total > line:
            return True, f"Over {line:g} já batido ({total} gols)"
        if not yes and total > line:
            return True, f"Under {line:g} morto ({total} gols)"
        return False, None

    if market.startswith("home_over_") or market.startswith("away_over_"):
        parts = market.split("_over_")
        if len(parts) != 2:
            return False, None
        team_side = parts[0]
        try:
            line = float(parts[1].replace("_", "."))
        except ValueError:
            return False, None
        team_goals = home_score if team_side == "home" else away_score
        if yes and team_goals > line:
            return True, f"Over time {line:g} já batido"
        if not yes and team_goals > line:
            return True, f"Under time {line:g} morto"
        return False, None

    return False, None


__all__ = ["is_dead_inplay_market"]
