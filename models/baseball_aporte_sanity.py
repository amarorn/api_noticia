"""Filtros de sanidade para aportes beisebol (evita long shots e priors distorcidos)."""
from __future__ import annotations

import re
from typing import Any

from models.baseball_inplay import BaseballInPlayResult

_OVER_LINE_RE = re.compile(r"over_(\d+)_(\d+)$")
_HOME_OVER_RE = re.compile(r"^home_over_(\d+)_(\d+)$")
_AWAY_OVER_RE = re.compile(r"^away_over_(\d+)_(\d+)$")


def _line_from_groups(g1: str, g2: str) -> float:
    return float(f"{g1}.{g2}")


def _parse_over_line(outcome: str) -> float | None:
    m = _OVER_LINE_RE.match(outcome) or _HOME_OVER_RE.match(outcome) or _AWAY_OVER_RE.match(outcome)
    if not m:
        return None
    return _line_from_groups(m.group(1), m.group(2))


def block_baseball_aporte(
    aporte: dict[str, Any],
    *,
    inplay: BaseballInPlayResult,
) -> tuple[bool, str | None]:
    """True se o aporte não deve ser recomendado (apostar/monitorar)."""
    market = str(aporte.get("market") or "")
    outcome = str(aporte.get("outcome") or "")
    odd = float(aporte.get("market_odd") or 0)
    action = str(aporte.get("action") or "")

    # Mercados exóticos — calibração fraca; só monitorar se já passou filtros EV
    if market == "highest_inning":
        implied = 1.0 / odd if odd > 1.0 else 1.0
        model_p = float(aporte.get("model_prob") or 0)
        if model_p > implied * 1.35:
            return True, "Entrada com maior pontuação: modelo superestima vs mercado (long shot)"
        if odd >= 10.0:
            return True, "Odd muito alta — mercado exótico sem edge confiável"

    if market == "run_n" and odd >= 8.0:
        return True, "Corrida N com odd long shot — bloqueado"

    line = _parse_over_line(outcome)
    if line is not None and "over" in outcome:
        proj_ft = inplay.expected_total
        proj_home = inplay.expected_final_home
        proj_away = inplay.expected_final_away

        if market == "total_runs":
            if line > proj_ft + 3.0:
                return True, f"Over {line:g} distante da projeção FT ({proj_ft:.1f} runs)"
            if line >= 18.0:
                return True, f"Linha alternativa extrema (over {line:g})"

        if market == "team_total_runs":
            if outcome.startswith("home_over_"):
                proj = proj_home
            elif outcome.startswith("away_over_"):
                proj = proj_away
            else:
                proj = None
            if proj is not None:
                if line > proj + 2.5:
                    return True, f"Over time {line:g} acima da projeção ({proj:.1f})"
                if line >= 10.0 and line > proj + 1.0:
                    return True, f"Total por time {line:g} é linha alternativa agressiva"

        if odd >= 3.5 and market in {"team_total_runs", "total_runs"}:
            implied = 1.0 / odd
            model_p = float(aporte.get("model_prob") or 0)
            ref_proj = proj_ft if market == "total_runs" else (
                proj_home if outcome.startswith("home_over_") else proj_away
            )
            if model_p > implied * 1.5 and line > ref_proj + 1.5:
                return True, "Long shot: edge do modelo provavelmente artefato de prior"

    if action == "apostar" and odd >= 8.0 and market in {"highest_inning", "run_n"}:
        return True, f"Odd {odd:.2f} — mercado exótico, sem stake automática"

    return False, None


def dedupe_correlated_baseball_aportes(aportes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mantém só a melhor linha por família (ex.: um over por time, um total FT)."""
    best: dict[tuple[str, str], dict[str, Any]] = {}
    order: list[tuple[str, str]] = []

    for a in aportes:
        market = str(a.get("market") or "")
        outcome = str(a.get("outcome") or "")
        if market == "team_total_runs" and "over" in outcome:
            side = "home" if outcome.startswith("home_") else "away"
            key = (market, f"{side}_over")
        elif market == "total_runs" and outcome.startswith("over_"):
            key = (market, "game_over")
        elif market == "highest_inning":
            key = (market, "single")
        else:
            key = (market, outcome)
        prev = best.get(key)
        if prev is None:
            best[key] = a
            order.append(key)
        elif float(a.get("expected_value") or 0) > float(prev.get("expected_value") or 0):
            best[key] = a

    return [best[k] for k in order if k in best]


def filter_sane_baseball_aportes(
    aportes: list[dict[str, Any]],
    *,
    inplay: BaseballInPlayResult,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Aplica sanidade + dedupe; retorna aportes filtrados e avisos."""
    warnings: list[str] = []
    kept: list[dict[str, Any]] = []
    for a in aportes:
        blocked, reason = block_baseball_aporte(a, inplay=inplay)
        if blocked:
            if reason and reason not in warnings:
                warnings.append(reason)
            continue
        kept.append(a)
    deduped = dedupe_correlated_baseball_aportes(kept)
    return deduped, warnings


def classify_baseball_line_tier(
    aporte: dict[str, Any],
    *,
    inplay: BaseballInPlayResult,
) -> str | None:
    """Classifica linha como alternativa/extrema vs linha principal do mercado."""
    market = str(aporte.get("market") or "")
    outcome = str(aporte.get("outcome") or "")
    line = _parse_over_line(outcome)

    if market == "total_runs" and line is not None and "over" in outcome:
        primary = inplay.market_total_line
        if primary is not None and abs(line - primary) >= 0.5:
            if line >= primary + 2.0 or line >= 14.0:
                return "extreme"
            return "alternative"
        if line >= 14.0:
            return "extreme"

    if market == "team_total_runs" and line is not None and "over" in outcome:
        proj = (
            inplay.expected_final_home
            if outcome.startswith("home_over_")
            else inplay.expected_final_away
            if outcome.startswith("away_over_")
            else None
        )
        if proj is not None:
            if line >= proj + 2.0 or line >= 11.0:
                return "extreme"
            if line >= proj + 1.0:
                return "alternative"

    if market in {"highest_inning", "run_n"}:
        odd = float(aporte.get("market_odd") or 0)
        if odd >= 10.0:
            return "extreme"
        return "alternative"

    return None


def annotate_baseball_line_tiers(
    aportes: list[dict[str, Any]],
    *,
    inplay: BaseballInPlayResult,
) -> list[dict[str, Any]]:
    """Adiciona ``line_tier`` (alternative|extreme) quando aplicável."""
    out: list[dict[str, Any]] = []
    for a in aportes:
        row = dict(a)
        tier = classify_baseball_line_tier(row, inplay=inplay)
        if tier:
            row["line_tier"] = tier
        out.append(row)
    return out
