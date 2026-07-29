"""Rótulos de mercado basquete alinhados à nomenclatura Superbet BR."""
from __future__ import annotations

BASKET_FT_MARKET_DEFAULTS: dict[str, str] = {
    "moneyline": "Vencedor da Partida",
    "spread": "Handicap",
    "total": "Total de Pontos",
    "team_total_points": "Total de Pontos por Time",
    "regulation_ml": "Resultado Final",
    "odd_even": "Ímpar/Par (Inc. prorrogação)",
}

BASKET_QUARTER_MARKET_DEFAULTS: dict[str, str] = {
    "quarter_total": "{n}º Quarto - Total de Pontos",
    "quarter_spread": "{n}º Quarto - Handicap",
    "quarter_moneyline": "{n}º Quarto - 1 x 2",
    "quarter_team_total": "{n}º Quarto - Total de Pontos",
}


def _quarter_ordinal(n: int) -> str:
    return f"{n}º"


def resolve_basket_market_display(
    market_key: str,
    *,
    quarter: int | None = None,
    team: str | None = None,
    side: str | None = None,
    market_names: dict[str, str] | None = None,
) -> str:
    """Nome do mercado na Superbet (prioriza nome capturado do feed)."""
    names = market_names or {}
    if market_key == "moneyline":
        return names.get("moneyline") or BASKET_FT_MARKET_DEFAULTS["moneyline"]
    if market_key == "spread":
        return names.get("spread") or BASKET_FT_MARKET_DEFAULTS["spread"]
    if market_key == "total":
        return names.get("total") or BASKET_FT_MARKET_DEFAULTS["total"]
    if market_key == "team_total_points":
        if side in ("home", "away"):
            captured = names.get(f"team_total_ft_{side}")
            if captured:
                return captured
        if team:
            return f"{team} - Total de Pontos (Inc. prorrogação)"
        return BASKET_FT_MARKET_DEFAULTS["team_total_points"]
    if market_key == "regulation_ml":
        return names.get("regulation_ml") or BASKET_FT_MARKET_DEFAULTS["regulation_ml"]
    if market_key == "odd_even":
        return names.get("odd_even") or BASKET_FT_MARKET_DEFAULTS["odd_even"]

    if quarter is not None:
        q = quarter
        if market_key == f"quarter_{q}_total" or market_key == "quarter_total":
            return names.get(f"q{q}_total") or BASKET_QUARTER_MARKET_DEFAULTS["quarter_total"].format(
                n=_quarter_ordinal(q)
            )
        if market_key == f"quarter_{q}_spread" or market_key == "quarter_spread":
            return names.get(f"q{q}_spread") or BASKET_QUARTER_MARKET_DEFAULTS[
                "quarter_spread"
            ].format(n=_quarter_ordinal(q))
        if market_key == f"quarter_{q}_moneyline" or market_key == "quarter_moneyline":
            return names.get(f"q{q}_moneyline") or BASKET_QUARTER_MARKET_DEFAULTS[
                "quarter_moneyline"
            ].format(n=_quarter_ordinal(q))
        if market_key == f"quarter_{q}_team_total" or market_key == "quarter_team_total":
            captured = names.get(f"q{q}_team_total_{side}") if side else None
            if captured:
                return captured
            base = BASKET_QUARTER_MARKET_DEFAULTS["quarter_team_total"].format(n=_quarter_ordinal(q))
            if team:
                return f"{base} de {team}"
            return base

    return market_key


def format_basket_selection_label(
    market_key: str,
    *,
    team: str | None = None,
    outcome: str | None = None,
    line: float | None = None,
    quarter: int | None = None,
) -> str:
    """Descrição da seleção (perna) em português, como aparece no botão Superbet."""
    if market_key == "moneyline" and team:
        return f"{team} vence"
    if market_key == "regulation_ml" and team and outcome:
        if outcome == "X":
            return "Empate"
        return f"{team} vence"
    if market_key == "regulation_ml" and outcome == "X":
        return "Empate"
    if market_key in {"spread", "quarter_spread"} and team and line is not None:
        sign = "+" if line > 0 else ""
        return f"{team} {sign}{line:g}"
    if market_key.startswith("quarter_") and market_key.endswith("_spread") and team and line is not None:
        sign = "+" if line > 0 else ""
        return f"{team} {sign}{line:g}"
    if market_key in {"total", "quarter_total", "team_total_points", "quarter_team_total"}:
        if outcome and line is not None:
            prefix = "Mais de" if outcome == "over" else "Menos de"
            if market_key == "team_total_points" and team:
                return f"{prefix} {line:g} — {team}"
            return f"{prefix} {line:g}"
    if market_key.startswith("quarter_") and "_total" in market_key and outcome and line is not None:
        prefix = "Mais de" if outcome == "over" else "Menos de"
        if team:
            return f"{prefix} {line:g} — {team}"
        return f"{prefix} {line:g}"
    if market_key.startswith("quarter_") and "_moneyline" in market_key:
        if outcome == "X":
            return "Empate"
        if team:
            return f"{team} vence"
    if market_key == "odd_even" and outcome:
        return "Ímpar" if outcome == "odd" else "Par"
    return team or outcome or market_key
