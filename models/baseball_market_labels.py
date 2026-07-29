"""Rótulos de mercado beisebol alinhados à nomenclatura Superbet BR."""
from __future__ import annotations

# Mercados FT modelados hoje
BASEBALL_FT_MARKET_DEFAULTS: dict[str, str] = {
    "moneyline": "Vencedor (incl. entradas extras)",
    "run_line": "Handicap (incl. entradas extras)",
    "total_runs": "Total de Corridas (incl. entradas extras)",
    "team_total_runs": "Pontuação Total da Equipe (incl. entradas extras)",
}

# Mercados visíveis na Superbet mas ainda sem modelo in-play
BASEBALL_KNOWN_MARKETS: tuple[str, ...] = (
    "Vencedor (incl. entradas extras)",
    "Total de Corridas (incl. entradas extras)",
    "Handicap (incl. entradas extras)",
    "Entrada X - Total de Corridas",
    "Pontuação Total da Equipe (incl. entradas extras)",
    "Entrada Com a Maior Pontuação",
    "Entrada X - 1X2",
    "Entradas 1 a 5 - 1x2",
    "Entradas 1 a 5 - Total",
    "Entradas 1 a 5 - handicap",
    "Corrida X (incl. entradas extras)",
)


BASEBALL_PERIOD_MARKET_DEFAULTS: dict[str, str] = {
    "f5_total": "Entradas 1 a 5 - Total",
    "f5_moneyline": "Entradas 1 a 5 - 1x2",
    "f5_spread": "Entradas 1 a 5 - handicap",
    "inning_total": "Entrada {n} - Total de Corridas",
    "inning_1x2": "Entrada {n} - 1X2",
    "highest_inning": "Entrada Com a Maior Pontuação",
    "run_n": "Corrida {n} (incl. entradas extras)",
}


def resolve_baseball_market_display(
    market_key: str,
    *,
    team: str | None = None,
    side: str | None = None,
    inning: int | None = None,
    run_number: int | None = None,
    market_names: dict[str, str] | None = None,
) -> str:
    """Nome do mercado na Superbet (prioriza nome capturado do feed)."""
    names = market_names or {}
    if market_key == "moneyline":
        return names.get("moneyline") or BASEBALL_FT_MARKET_DEFAULTS["moneyline"]
    if market_key == "run_line":
        return names.get("run_line") or BASEBALL_FT_MARKET_DEFAULTS["run_line"]
    if market_key == "total_runs":
        return names.get("total_runs") or BASEBALL_FT_MARKET_DEFAULTS["total_runs"]
    if market_key == "team_total_runs":
        if side in ("home", "away"):
            captured = names.get(f"team_total_runs_{side}")
            if captured:
                return captured
        if team:
            return f"{team} - Total de Corridas (incl. entradas extras)"
        return BASEBALL_FT_MARKET_DEFAULTS["team_total_runs"]
    if market_key == "f5_total":
        return names.get("f5_total") or BASEBALL_PERIOD_MARKET_DEFAULTS["f5_total"]
    if market_key == "f5_moneyline":
        return names.get("f5_moneyline") or BASEBALL_PERIOD_MARKET_DEFAULTS["f5_moneyline"]
    if market_key == "f5_spread":
        return names.get("f5_spread") or BASEBALL_PERIOD_MARKET_DEFAULTS["f5_spread"]
    if market_key == "inning_total" and inning is not None:
        return names.get(f"inning_{inning}_total") or BASEBALL_PERIOD_MARKET_DEFAULTS[
            "inning_total"
        ].format(n=inning)
    if market_key == "inning_1x2" and inning is not None:
        return names.get(f"inning_{inning}_1x2") or BASEBALL_PERIOD_MARKET_DEFAULTS["inning_1x2"].format(
            n=inning
        )
    if market_key == "highest_inning":
        return names.get("highest_inning") or BASEBALL_PERIOD_MARKET_DEFAULTS["highest_inning"]
    if market_key == "run_n" and run_number is not None:
        return names.get(f"run_{run_number}") or BASEBALL_PERIOD_MARKET_DEFAULTS["run_n"].format(
            n=run_number
        )
    return market_key


def format_baseball_selection_label(
    market_key: str,
    *,
    team: str | None = None,
    outcome: str | None = None,
    line: float | None = None,
    inning: int | None = None,
    run_number: int | None = None,
) -> str:
    """Descrição da seleção (perna da aposta) em português."""
    if market_key == "moneyline" and team:
        return f"{team} vence"
    if market_key == "run_line" and team and line is not None:
        sign = "+" if line > 0 else ""
        return f"{team} {sign}{line:g}"
    if market_key in {"total_runs", "f5_total", "inning_total"} and outcome and line is not None:
        prefix = "Mais de" if outcome == "over" else "Menos de"
        base = f"{prefix} {line:g}"
        if market_key == "inning_total" and inning is not None:
            return f"{base} (Entrada {inning})"
        return base
    if market_key == "team_total_runs" and team and outcome and line is not None:
        prefix = "Mais de" if outcome == "over" else "Menos de"
        return f"{prefix} {line:g} — {team}"
    if market_key in {"f5_moneyline", "inning_1x2"} and team and outcome:
        if outcome == "X":
            return f"Empate — Entrada {inning}" if inning else "Empate (Entradas 1–5)"
        return f"{team} vence — Entrada {inning}" if inning else f"{team} vence (Entradas 1–5)"
    if market_key == "f5_spread" and team and line is not None:
        sign = "+" if line > 0 else ""
        return f"{team} {sign}{line:g} (Entradas 1–5)"
    if market_key == "highest_inning" and inning is not None:
        return f"Entrada {inning} com maior pontuação"
    if market_key == "run_n" and run_number is not None and outcome:
        if outcome == "yes":
            return f"Haverá corrida {run_number} ou mais"
        return f"Menos de {run_number} corridas no jogo"
    return team or outcome or market_key
