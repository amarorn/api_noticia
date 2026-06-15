"""Classificação de mercados in-play por período (1T / 2T / jogo)."""

from __future__ import annotations

import re

from config import settings


def is_second_half_market(market: str) -> bool:
    return market.startswith("2h_")


def is_first_half_market(market: str) -> bool:
    return market.startswith("1h_")


def is_full_match_market(market: str) -> bool:
    return not is_second_half_market(market) and not is_first_half_market(market)


def market_live_block_minute(market: str) -> int:
    """Minuto a partir do qual novos aportes neste mercado são bloqueados."""
    if is_second_half_market(market):
        return settings.live_block_2h_minute
    return settings.live_block_minute


def is_market_blocked_by_minute(market: str, minute: int) -> bool:
    return minute >= market_live_block_minute(market)


def allow_2h_suggestions(minute: int) -> bool:
    """Sugestões de mercados do 2T (após intervalo, antes do corte tardio)."""
    return 45 < minute <= settings.live_block_2h_minute


_SECOND_HALF_TEXT = re.compile(
    r"2\s*[º°]?\s*tempo|segundo\s*tempo|2\s*t\b|2nd\s*half|second\s*half",
    re.IGNORECASE,
)
_FIRST_HALF_TEXT = re.compile(
    r"1\s*[º°]?\s*tempo|primeiro\s*tempo|1\s*t\b|1st\s*half|first\s*half",
    re.IGNORECASE,
)

def _pick_text(*parts: str | None) -> str:
    return " ".join(p for p in parts if p).strip()


def effective_guardrail_market(
    market: str,
    *,
    outcome: str = "",
    target_value: str | None = None,
) -> str:
    """Normaliza mercado desconhecido (other/combo/totals) para período de bloqueio."""
    m = (market or "").strip().lower()
    if is_second_half_market(m) or is_first_half_market(m):
        return m

    text = _pick_text(outcome, target_value)
    if _SECOND_HALF_TEXT.search(text):
        return "2h_other"
    if _FIRST_HALF_TEXT.search(text):
        return "1h_other"

    ambiguous = {
        "other",
        "combo",
        "handicap",
        "double_chance",
        "totals",
        "btts",
        "next_goal",
        "corners_total",
        "odd_even_goals",
        "odd_even_corners",
    }
    if m in ambiguous or m.startswith("totals"):
        return m
    return m


__all__ = [
    "effective_guardrail_market",
    "is_second_half_market",
    "is_first_half_market",
    "is_full_match_market",
    "market_live_block_minute",
    "is_market_blocked_by_minute",
    "allow_2h_suggestions",
]
