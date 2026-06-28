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


def _contradiction_warnings(legs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detecta contradições lógicas entre pernas (ex.: handicap time A + próximo gol time B)."""
    warnings: list[dict[str, Any]] = []
    
    # Indexa pernas por tipo
    handicaps: list[dict[str, Any]] = []
    next_goals: list[dict[str, Any]] = []
    team_overs: list[dict[str, Any]] = []
    
    for leg in legs:
        market = str(leg.get("market") or "")
        outcome = str(leg.get("outcome") or "yes")
        label = str(leg.get("label") or market)
        
        if "handicap" in market.lower() or "handicap" in label.lower():
            handicaps.append(leg)
        elif "next_goal" in market.lower() or "próximo gol" in label.lower() or "º gol" in label.lower():
            next_goals.append(leg)
        elif "team_total" in market.lower() or ("total de gols" in label.lower() and any(team in label.lower() for team in ["ferroviário", "central", "mandante", "visitante", "casa", "home", "away"])):
            team_overs.append(leg)
        elif "over" in market.lower() and any(team in label.lower() for team in ["ferroviário", "central", "mandante", "visitante", "casa", "home", "away"]):
            # Over com nome do time no label (ex: "Mais de 1.5 - Ferroviário CE")
            team_overs.append(leg)
    
    # 1. Handicap time A + Próximo gol time B = contradição
    for h in handicaps:
        h_outcome = str(h.get("outcome") or "")
        h_label = str(h.get("label") or "")
        # Determina qual time está no handicap
        h_team = None
        if "home" in h_outcome.lower() or "casa" in h_label.lower() or "mandante" in h_label.lower():
            h_team = "home"
        elif "away" in h_outcome.lower() or "visitante" in h_label.lower():
            h_team = "away"
        else:
            # Tenta extrair do label
            h_team = _extract_team_from_label(h_label)
        
        if not h_team:
            continue
            
        for ng in next_goals:
            ng_outcome = str(ng.get("outcome") or "")
            ng_label = str(ng.get("label") or "")
            ng_team = _extract_team_from_label(ng_label) or ng_outcome.lower()
            
            # Se o próximo gol é do time OPOSITO ao handicap, é contradição
            if ng_team and ng_team != h_team:
                warnings.append({
                    "severity": "critical",
                    "code": "contradiction_handicap_next_goal",
                    "title": "Contradição: Handicap + Próximo gol adversário",
                    "reason": (
                        f"«{h_label}» aposta na vitória de um time, mas «{ng_label}» aposta que o adversário marca o próximo gol. "
                        f"Se o adversário marca, o handicap perde. São cenários mutuamente exclusivos."
                    ),
                    "legs": [
                        {"market": h.get("market"), "outcome": h.get("outcome"), "label": h.get("label")},
                        {"market": ng.get("market"), "outcome": ng.get("outcome"), "label": ng.get("label")},
                    ],
                })
    
    # 2. Handicap time A + Over gols time B = contradição (se B faz muitos gols, A não vence)
    for h in handicaps:
        h_outcome = str(h.get("outcome") or "")
        h_label = str(h.get("label") or "")
        h_team = _extract_team_from_label(h_label)
        if not h_team:
            if "home" in h_outcome.lower():
                h_team = "home"
            elif "away" in h_outcome.lower():
                h_team = "away"
        
        if not h_team:
            continue
            
        for to in team_overs:
            to_label = str(to.get("label") or "")
            to_team = _extract_team_from_label(to_label)
            to_line = to.get("line", 0)
            
            # Se o over é do time OPOSITO ao handicap e linha é alta (≥1.5), é contradição
            if to_team and to_team != h_team and to_line >= 1.5:
                warnings.append({
                    "severity": "critical",
                    "code": "contradiction_handicap_over",
                    "title": "Contradição: Handicap + Over adversário",
                    "reason": (
                        f"«{h_label}» aposta na vitória de um time, mas «{to_label}» aposta que o adversário faz {to_line}+ gols. "
                        f"Se o adversário marca {to_line}+ gols, é improvável que o handicap vença. "
                        f"São cenários mutuamente exclusivos."
                    ),
                    "legs": [
                        {"market": h.get("market"), "outcome": h.get("outcome"), "label": h.get("label")},
                        {"market": to.get("market"), "outcome": to.get("outcome"), "label": to.get("label")},
                    ],
                })
    
    # 3. Próximo gol time + Over gols mesmo time = correlação alta (não contradição, mas alerta)
    for ng in next_goals:
        ng_label = str(ng.get("label") or "")
        ng_team = _extract_team_from_label(ng_label)
        
        for to in team_overs:
            to_label = str(to.get("label") or "")
            to_team = _extract_team_from_label(to_label)
            to_line = to.get("line", 0)
            
            if ng_team and to_team and ng_team == to_team and to_line >= 1.5:
                warnings.append({
                    "severity": "high",
                    "code": "correlation_next_goal_over",
                    "title": "Correlação alta: Próximo gol + Over mesmo time",
                    "reason": (
                        f"«{ng_label}» e «{to_label}» contam a mesma história. "
                        f"Se {ng_team} marca o próximo gol, já contribui para o over. "
                        f"A Superbet pode rejeitar por correlação."
                    ),
                    "legs": [
                        {"market": ng.get("market"), "outcome": ng.get("outcome"), "label": ng.get("label")},
                        {"market": to.get("market"), "outcome": to.get("outcome"), "label": to.get("label")},
                    ],
                })
    
    return warnings


def _extract_team_from_label(label: str) -> str | None:
    """Extrai 'home' ou 'away' de um label Superbet."""
    text = label.lower()
    # Time mandante
    if any(w in text for w in ["casa", "mandante", "home", "central pe"]):
        return "home"
    # Time visitante
    if any(w in text for w in ["visitante", "away", "ferroviário ce"]):
        return "away"
    # Tenta extrair nome do time após " - " (ex: "Mais de 1.5 - Ferroviário CE")
    if " - " in label:
        team_name = label.split(" - ", 1)[1].strip().lower()
        if team_name:
            # Se conhecemos o mapeamento, retorna
            if "ferroviário" in team_name or "ce" in team_name:
                return "away"
            if "central" in team_name or "pe" in team_name:
                return "home"
            # Retorna o nome do time como identificador
            return team_name
    return None


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
            "line": leg.get("line"),
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
    warnings.extend(_contradiction_warnings(normalized))
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
