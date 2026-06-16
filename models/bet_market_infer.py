"""Inferência de mercado a partir de capturas legadas ``other`` da extensão."""
from __future__ import annotations

import re

_CORNERS_LINE_RE = re.compile(
    r"(?P<dir>mais|menos|over|under|acima|abaixo|\+|\-)\s*(?:de\s*)?(?P<line>\d+[.,]?\d*)",
    re.IGNORECASE,
)
_ODD_EVEN_RE = re.compile(r"\b(ímpar|impar|odd|par|even)\b", re.IGNORECASE)


def infer_other_market(
    outcome: str,
    target_value: str | None = None,
    *,
    market_raw: str = "",
) -> tuple[str, str, str | None] | None:
    """Tenta mapear palpite ``other`` → mercado estruturado.

    Retorna ``(market, outcome, target_value)`` ou ``None`` se não reconhecer.
    """
    text = f"{market_raw} {outcome} {target_value or ''}".strip()
    lower = text.lower()

    if "escanteio" in lower or "corner" in lower:
        parsed = _parse_line_direction(outcome or market_raw, default_market="corners_total")
        if parsed:
            return parsed

    if _CORNERS_LINE_RE.search(lower):
        parsed = _parse_line_direction(text)
        if parsed:
            market, direction, line = parsed
            try:
                if float(line) >= 7.5:
                    return ("corners_total", direction, line)
            except ValueError:
                pass
            return (f"totals_{line}", direction, line)

    if "par" in lower and ("ímpar" in lower or "impar" in lower or "odd" in lower or "even" in lower):
        oe = _parse_odd_even(text)
        if oe:
            kind = "odd_even_corners" if ("escanteio" in lower or "corner" in lower) else "odd_even_goals"
            return (kind, oe, None)

    m = _ODD_EVEN_RE.search(lower)
    if m:
        token = m.group(1).lower()
        oe = "odd" if token in {"ímpar", "impar", "odd"} else "even"
        kind = "odd_even_corners" if ("escanteio" in lower or "corner" in lower) else "odd_even_goals"
        return (kind, oe, None)

    return None


def _parse_line_direction(text: str, *, default_market: str = "corners_total") -> tuple[str, str, str] | None:
    m = _CORNERS_LINE_RE.search(text)
    if not m:
        return None
    direction_raw = m.group("dir").lower()
    line = m.group("line").replace(",", ".")
    if direction_raw in {"mais", "over", "acima", "+"}:
        direction = "over"
    else:
        direction = "under"
    market = default_market if default_market.startswith("corners") else f"totals_{line}"
    if float(line) >= 7.5:
        market = "corners_total"
    else:
        market = f"totals_{line}"
    return market, direction, line


def _parse_odd_even(text: str) -> str | None:
    lower = text.lower()
    if re.search(r"\b(ímpar|impar|odd)\b", lower):
        return "odd"
    if re.search(r"\b(par|even)\b", lower):
        return "even"
    return None


__all__ = ["infer_other_market"]
