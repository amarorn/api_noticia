"""Classificação de palpites Superbet (extensão / clipboard) → mercado canônico."""
from __future__ import annotations

import re

_PERIOD_1H = re.compile(
    r"1\s*[º°o]?\s*tempo|primeiro\s*tempo|\b1\s*t\b|1st\s*half|total de gols\s*\(\s*1",
    re.IGNORECASE,
)
_PERIOD_2H = re.compile(
    r"2\s*[º°o]?\s*tempo|segundo\s*tempo|\b2\s*t\b|2nd\s*half|total de gols\s*\(\s*2",
    re.IGNORECASE,
)
_LINE_RE = re.compile(r"([+\-−]?\s*\d+[.,]\d+|[+\-−]?\s*\d+)")


def detect_period(*texts: str) -> str:
    """Retorna ``ft``, ``1h`` ou ``2h`` a partir de rótulos Superbet."""
    combined = " ".join(t for t in texts if t).strip()
    if not combined:
        return "ft"
    if _PERIOD_2H.search(combined):
        return "2h"
    if _PERIOD_1H.search(combined):
        return "1h"
    return "ft"


def handicap_line_key(line: float) -> str:
    """Chave estável de linha (ex.: -1.5 → ``m1_5``, +0.5 → ``p0_5``)."""
    if abs(line) < 1e-9:
        return "0"
    if line < 0:
        return "m" + f"{abs(line):g}".replace(".", "_")
    return "p" + f"{line:g}".replace(".", "_")


def _parse_line_value(text: str) -> float | None:
    match = _LINE_RE.search(text or "")
    if not match:
        return None
    raw = match.group(1).replace("−", "-").replace(",", ".").replace(" ", "")
    try:
        return float(raw)
    except ValueError:
        return None



def _detect_side(text: str, home_team: str, away_team: str) -> str | None:
    lower = (text or "").lower()
    home_l = (home_team or "").lower().strip()
    away_l = (away_team or "").lower().strip()
    if home_l and home_l in lower:
        return "home"
    if away_l and away_l in lower:
        return "away"
    if home_l:
        token = home_l.split()[0]
        if len(token) >= 4 and token in lower:
            return "home"
    if away_l:
        token = away_l.split()[0]
        if len(token) >= 4 and token in lower:
            return "away"
    if re.search(r"\b(casa|mandante|home)\b", lower):
        return "home"
    if re.search(r"\b(fora|visitante|away)\b", lower):
        return "away"
    return None


def _classify_h2h(
    market_raw: str,
    pick_raw: str,
    period: str,
) -> tuple[str, str] | None:
    combined = f"{market_raw} {pick_raw}"
    if not re.search(
        r"resultado final|match result|1x2|vencedor|winner|moneyline|resultado\s*\(?1x2\)?",
        combined,
        re.IGNORECASE,
    ):
        return None

    market = f"{period}_h2h" if period in {"1h", "2h"} else "h2h"
    pick = pick_raw.strip()
    if re.match(r"^1$", pick):
        return market, "home"
    if re.match(r"^2$", pick):
        return market, "away"
    if re.match(r"^X$", pick, re.IGNORECASE) or re.search(r"empate", pick, re.IGNORECASE):
        return market, "draw"
    if re.match(r"^1X$", pick, re.IGNORECASE):
        return market, "home_or_draw"
    if re.match(r"^X2$", pick, re.IGNORECASE):
        return market, "draw_or_away"
    if re.match(r"^12$", pick, re.IGNORECASE):
        return market, "home_or_away"
    return market, pick


def _classify_totals(
    market_raw: str,
    pick_raw: str,
    period: str,
) -> tuple[str, str, str | None] | None:
    combined = f"{market_raw} {pick_raw}"
    if not re.search(r"total de gols|over.*under|total goals|\bgols\b", combined, re.IGNORECASE):
        return None
    if re.search(r"escanteio|corner|cart[aã]o|chute", combined, re.IGNORECASE):
        return None

    is_over = bool(re.search(r"mais|over|acima|\+", pick_raw, re.IGNORECASE))
    line = _parse_line_value(pick_raw) or _parse_line_value(market_raw)
    line_str = f"{line:g}" if line is not None else "2.5"

    if period in {"1h", "2h"}:
        line_key = line_str.replace(".", "_")
        return f"{period}_over_{line_key}", "yes" if is_over else "no", line_str

    return f"totals_{line_str}", "over" if is_over else "under", line_str


def _classify_handicap(
    market_raw: str,
    pick_raw: str,
    period: str,
    home_team: str,
    away_team: str,
) -> tuple[str, str, str | None] | None:
    combined = f"{market_raw} {pick_raw}"
    if not re.search(r"handicap", combined, re.IGNORECASE):
        return None

    is_asian = bool(re.search(r"asi[aá]tico|asian", combined, re.IGNORECASE))
    line = _parse_line_value(pick_raw) or _parse_line_value(market_raw)
    side = _detect_side(pick_raw, home_team, away_team) or _detect_side(market_raw, home_team, away_team)

    hcap_kind = "ah" if is_asian else "hcap"
    line_str = f"{line:g}" if line is not None else None

    if side and line is not None:
        market = f"{period}_{hcap_kind}_{side}_{handicap_line_key(line)}"
        return market, "yes", line_str

    if line is not None:
        return "handicap", "yes", line_str

    return "handicap", pick_raw.strip(), None


def classify_superbet_pick(
    market_raw: str,
    pick_raw: str,
    *,
    home_team: str = "",
    away_team: str = "",
) -> dict[str, str | None]:
    """Mapeia rótulos Superbet para mercado/outcome canônicos."""
    period = detect_period(market_raw, pick_raw)
    market_raw = (market_raw or "").strip()
    pick_raw = (pick_raw or "").strip()

    h2h = _classify_h2h(market_raw, pick_raw, period)
    if h2h:
        market, outcome = h2h
        return {"market": market, "outcome": outcome, "target_value": None}

    totals = _classify_totals(market_raw, pick_raw, period)
    if totals:
        market, outcome, target = totals
        return {"market": market, "outcome": outcome, "target_value": target}

    combined = f"{market_raw} {pick_raw}"
    if re.search(r"ambas.*marcam|both.*score|btts", combined, re.IGNORECASE):
        yes = bool(re.search(r"sim|yes", pick_raw, re.IGNORECASE))
        market = (
            "btts_any_half"
            if re.search(r"algum dos tempos|any half", combined, re.IGNORECASE)
            else "btts"
        )
        return {"market": market, "outcome": "yes" if yes else "no", "target_value": None}

    if re.search(r"pr[oó]ximo gol|next goal|2\s*[º°o]?\s*gol", combined, re.IGNORECASE):
        side = _detect_side(pick_raw, home_team, away_team)
        return {"market": "next_goal", "outcome": side or pick_raw, "target_value": None}

    handicap = _classify_handicap(market_raw, pick_raw, period, home_team, away_team)
    if handicap:
        market, outcome, target = handicap
        return {"market": market, "outcome": outcome, "target_value": target}

    if re.search(r"dupla\s*chance|double chance", combined, re.IGNORECASE):
        return {"market": "double_chance", "outcome": pick_raw, "target_value": None}

    if re.search(r"escanteio|corner", combined, re.IGNORECASE):
        is_over = bool(re.search(r"mais|over|acima|\+", pick_raw, re.IGNORECASE))
        line = _parse_line_value(pick_raw) or _parse_line_value(market_raw)
        target = f"{line:g}" if line is not None else None
        return {
            "market": "corners_total",
            "outcome": "over" if is_over else "under",
            "target_value": target,
        }

    return {"market": "other", "outcome": pick_raw, "target_value": None}


__all__ = [
    "classify_superbet_pick",
    "detect_period",
    "handicap_line_key",
]
