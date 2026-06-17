"""Armadilhas de over no 1T e validação de Criar Aposta Superbet."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any

from config import settings
from models.inplay_leg_compatibility import (
    _offense_side,
    combo_legs_compatible,
    legs_compatible,
    period_of_market,
)

_YES_OUTCOMES = frozenset({"yes", "sim", "over"})


def _is_yes_outcome(outcome: str) -> bool:
    return (outcome or "").strip().lower() in _YES_OUTCOMES


def _parse_over_line(market: str) -> tuple[str, str, float] | None:
    """Retorna (periodo, escopo, linha) para mercados over.

    escopo: ``total`` | ``home`` | ``away``
    """
    period = period_of_market(market)
    body = market[3:] if market.startswith(("1h_", "2h_", "ft_")) else market

    for scope, prefix in (("home", "home_over_"), ("away", "away_over_"), ("total", "over_")):
        if not body.startswith(prefix):
            continue
        raw = body[len(prefix) :].replace("_", ".")
        try:
            line = float(raw)
        except ValueError:
            return None
        return period, scope, line
    return None


def _ht_scores(
    minute: int,
    home_score: int,
    away_score: int,
    ht_home: int | None,
    ht_away: int | None,
) -> tuple[int, int, int]:
    """Gols no 1T: (total, mandante, visitante)."""
    if minute > 45 and ht_home is not None and ht_away is not None:
        return ht_home + ht_away, ht_home, ht_away
    return home_score + away_score, home_score, away_score


def _goals_needed_for_over(line: float, current_goals: int) -> int:
    target = math.floor(line) + 1 if abs(line % 1 - 0.5) < 0.01 else math.ceil(line + 0.001)
    return max(0, target - current_goals)


def assess_ht_over_trap(
    market: str,
    outcome: str,
    *,
    minute: int,
    home_score: int,
    away_score: int,
    ht_home: int | None = None,
    ht_away: int | None = None,
    label: str | None = None,
) -> dict[str, Any] | None:
    """Detecta over de 1T inviável ou já morto (ex.: over 1,5 com 1 gol no 45')."""
    if not _is_yes_outcome(outcome):
        return None

    parsed = _parse_over_line(market)
    if parsed is None:
        return None
    period, scope, line = parsed
    if period != "1h":
        return None

    ht_total, ht_home_goals, ht_away_goals = _ht_scores(
        minute, home_score, away_score, ht_home, ht_away
    )
    if scope == "home":
        current = ht_home_goals
    elif scope == "away":
        current = ht_away_goals
    else:
        current = ht_total

    needed = _goals_needed_for_over(line, current)
    if needed <= 0:
        return None

    scope_label = {"total": "total 1T", "home": "mandante 1T", "away": "visitante 1T"}[scope]
    display = label or f"Mais de {line:g} — {scope_label}"

    if minute >= settings.live_block_minute or (minute > 45 and ht_home is not None):
        return {
            "severity": "critical",
            "code": "ht_over_dead",
            "market": market,
            "outcome": outcome,
            "label": display,
            "minute": minute,
            "current_goals": current,
            "line": line,
            "goals_needed": needed,
            "title": "Over 1T já perdido",
            "reason": (
                f"{display}: {current} gol(is) no 1T — precisava de "
                f"{math.floor(line) + 1 if line % 1 else int(line)}+ no intervalo. "
                f"Não entre (odd alta = armadilha)."
            ),
        }

    if minute >= settings.live_ht_over_trap_minute:
        return {
            "severity": "high",
            "code": "ht_over_trap",
            "market": market,
            "outcome": outcome,
            "label": display,
            "minute": minute,
            "current_goals": current,
            "line": line,
            "goals_needed": needed,
            "title": f"Over 1T improvável ({minute}')",
            "reason": (
                f"{display} com {current} gol(is) aos {minute}' — "
                f"faltam {needed} gol(is) em poucos minutos. "
                f"Evite correr odd alta (ex.: 4,75+)."
            ),
        }

    return None


def scan_ht_over_traps(
    rows: list[dict[str, Any]],
    *,
    minute: int,
    home_score: int,
    away_score: int,
    ht_home: int | None = None,
    ht_away: int | None = None,
) -> list[dict[str, Any]]:
    """Varre market_scan / oportunidades e retorna armadilhas de over 1T."""
    traps: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        market = str(row.get("market") or "")
        outcome = str(row.get("outcome") or "yes")
        trap = assess_ht_over_trap(
            market,
            outcome,
            minute=minute,
            home_score=home_score,
            away_score=away_score,
            ht_home=ht_home,
            ht_away=ht_away,
            label=row.get("label"),
        )
        if trap is None:
            continue
        key = f"{market}:{outcome}"
        if key in seen:
            continue
        seen.add(key)
        traps.append(trap)
    return traps


def _narrative_correlation_warnings(
    legs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pernas que contam a mesma história (ex.: −1,5 + over Argentina 1T + 2×0 1T)."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for leg in legs:
        market = str(leg.get("market") or "")
        outcome = str(leg.get("outcome") or "yes")
        side = _offense_side(market, outcome)
        if not side:
            continue
        period = period_of_market(market)
        groups[(period, side)].append(leg)

    warnings: list[dict[str, Any]] = []
    for (period, side), items in groups.items():
        if len(items) < 2:
            continue
        labels = [str(x.get("label") or x.get("market")) for x in items]
        period_pt = {"1h": "1º tempo", "2h": "2º tempo", "ft": "jogo"}.get(period, period)
        side_pt = "mandante" if side == "home" else "visitante"
        warnings.append({
            "severity": "high",
            "code": "narrative_correlation",
            "title": "Pernas correlacionadas no Criar Aposta",
            "reason": (
                f"{len(items)} palpites no {period_pt} empilham o mesmo cenário ({side_pt}): "
                f"{', '.join(labels[:4])}. "
                "Se o 1T termina 1×0, várias pernas morrem juntas — prefira 1 palpite ou eixos decorrelacionados."
            ),
            "legs": [{"market": x.get("market"), "outcome": x.get("outcome"), "label": x.get("label")} for x in items],
        })
    return warnings


def _incompatible_pair_reason(a: dict[str, Any], b: dict[str, Any]) -> str | None:
    am, ao = str(a.get("market") or ""), str(a.get("outcome") or "yes")
    bm, bo = str(b.get("market") or ""), str(b.get("outcome") or "yes")
    if legs_compatible(am, ao, bm, bo):
        return None
    la = a.get("label") or am
    lb = b.get("label") or bm
    return f"Superbet rejeita ou anula: «{la}» + «{lb}»."


def _stake_warnings(legs: list[dict[str, Any]], combined_odd: float | None) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    if combined_odd is not None and combined_odd >= 6.0:
        warnings.append({
            "severity": "medium",
            "code": "high_combo_odd",
            "title": "Odd combinada alta",
            "reason": (
                f"Odd {combined_odd:.2f} — stake sugerida ≤1% da banca. "
                "Combos 6+ raramente compensam o risco empilhado."
            ),
        })
    return warnings


def validate_bet_builder(
    legs: list[dict[str, Any]],
    *,
    minute: int | None = None,
    home_score: int = 0,
    away_score: int = 0,
    ht_home: int | None = None,
    ht_away: int | None = None,
    combined_odd: float | None = None,
) -> dict[str, Any]:
    """Valida pernas do Criar Aposta antes de montar na Superbet."""
    normalized = [
        {
            "market": str(leg.get("market") or ""),
            "outcome": str(leg.get("outcome") or "yes"),
            "label": leg.get("label"),
        }
        for leg in legs
        if leg.get("market")
    ]

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if len(normalized) < 2:
        return {
            "valid": True,
            "errors": [],
            "warnings": [{
                "severity": "medium",
                "code": "single_leg",
                "title": "Aposta simples",
                "reason": "Validação de combo exige 2+ pernas.",
            }],
            "legs_count": len(normalized),
            "bet_builder_rules": _bet_builder_rules_text(),
        }

    pairs: list[tuple[str, str]] = [(x["market"], x["outcome"]) for x in normalized]
    if not combo_legs_compatible(pairs):
        for i in range(len(normalized)):
            for j in range(i + 1, len(normalized)):
                reason = _incompatible_pair_reason(normalized[i], normalized[j])
                if reason:
                    errors.append({
                        "severity": "critical",
                        "code": "legs_incompatible",
                        "title": "Pernas incompatíveis",
                        "reason": reason,
                    })
                    break
            if errors:
                break
        if not errors:
            errors.append({
                "severity": "critical",
                "code": "combo_invalid",
                "title": "Combo inválido",
                "reason": "Combinação rejeitada pelas regras Superbet (handicap duplo, placares conflitantes, etc.).",
            })

    warnings.extend(_narrative_correlation_warnings(normalized))
    warnings.extend(_stake_warnings(normalized, combined_odd))

    if minute is not None:
        for leg in normalized:
            trap = assess_ht_over_trap(
                leg["market"],
                leg["outcome"],
                minute=minute,
                home_score=home_score,
                away_score=away_score,
                ht_home=ht_home,
                ht_away=ht_away,
                label=leg.get("label"),
            )
            if trap:
                bucket = errors if trap["severity"] == "critical" else warnings
                bucket.append({
                    "severity": trap["severity"],
                    "code": trap["code"],
                    "title": trap["title"],
                    "reason": trap["reason"],
                    "market": trap["market"],
                    "outcome": trap["outcome"],
                })

    dedup_errors: list[dict[str, Any]] = []
    seen_err: set[str] = set()
    for item in errors:
        key = item.get("code", "") + str(item.get("reason", ""))
        if key in seen_err:
            continue
        seen_err.add(key)
        dedup_errors.append(item)

    dedup_warn: list[dict[str, Any]] = []
    seen_w: set[str] = set()
    for item in warnings:
        key = item.get("code", "") + str(item.get("reason", ""))
        if key in seen_w:
            continue
        seen_w.add(key)
        dedup_warn.append(item)

    return {
        "valid": len(dedup_errors) == 0,
        "errors": dedup_errors,
        "warnings": dedup_warn,
        "legs_count": len(normalized),
        "bet_builder_rules": _bet_builder_rules_text(),
    }


def _bet_builder_rules_text() -> list[str]:
    return [
        "No Criar Aposta: no máximo 1 narrativa por bilhete (evite 3+ palpites no mesmo time/período).",
        f"Over 1,5 no 1T com 1 gol e minuto ≥{settings.live_ht_over_trap_minute}': não correr odd alta.",
        f"Após {settings.live_block_minute}' mercados de 1T estão mortos — não monte combo de intervalo.",
        "Odd combinada ≥6: stake ≤1% da banca.",
        "Prefira eixos decorrelacionados (ex.: cartões 1T + escanteios 1T), não domínio + over + placar exato.",
    ]


def traps_to_strategy_shields(traps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Converte armadilhas HT em shields do painel de estratégia."""
    shields: list[dict[str, Any]] = []
    for trap in traps:
        shields.append({
            "action": "evitar" if trap.get("severity") == "critical" else "reduzir_exposicao",
            "priority": "alta" if trap.get("severity") == "critical" else "media",
            "title": trap.get("title", "Armadilha over 1T"),
            "reason": trap.get("reason", ""),
        })
    return shields


def infer_market_from_label(label: str) -> tuple[str, str] | None:
    """Heurística para labels Superbet (extensão / manual)."""
    text = (label or "").strip().lower()
    if not text:
        return None
    period = "1h" if re.search(r"1\s*[º°]?\s*tempo|primeiro\s*tempo|1\s*t\b", text) else "ft"
    if re.search(r"mais de|over", text):
        m = re.search(r"(\d+[,.]\d+|\d+)", text)
        if m:
            line = m.group(1).replace(",", ".")
            line_key = line.replace(".", "_")
            if re.search(r"arg[eé]lia|visitante|away", text):
                return f"{period}_away_over_{line_key}", "yes"
            if re.search(r"argentina|mandante|home|casa", text) and period == "1h":
                return f"1h_home_over_{line_key}", "yes"
            return f"{period}_over_{line_key}", "yes"
    if "1º gol" in text or "primeiro gol" in text:
        if re.search(r"arg[eé]lia|visitante", text):
            return "next_goal", "away"
        if re.search(r"argentina|mandante|casa", text):
            return "next_goal", "home"
    if re.search(r"resultado final|^1\s*[-–]|vitória.*mandante", text):
        return "h2h", "1"
    return None


__all__ = [
    "assess_ht_over_trap",
    "infer_market_from_label",
    "scan_ht_over_traps",
    "traps_to_strategy_shields",
    "validate_bet_builder",
]
