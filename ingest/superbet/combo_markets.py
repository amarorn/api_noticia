"""Cruzamento de pernas KXL com odds Superbet e ajuste de linhas."""
from __future__ import annotations

import math
from typing import Any

from ingest.superbet.parser import SuperbetEventSnapshot
from models.ev_value import evaluate_outcome
from schemas.national_teams import normalize_national_team

_PERIOD_LABEL = {"first_half": "Primeiro Tempo", "full_time": "Partida"}
_STAT_LABEL = {
    "goals": "Total de Gols",
    "corners": "Total de Escanteios",
    "shots": "Total de Chutes",
    "shots_on_target": "Total de Chutes a Gol",
    "yellow_cards": "Total de Cartões Amarelos",
}
_DIRECTION_LABEL = {"over": "Mais de", "under": "Menos de"}

_OVER_LABELS = ("mais de", "over", "sim")
_UNDER_LABELS = ("menos de", "under", "não", "nao")


def _parse_available_lines(book: dict[str, dict[str, float]]) -> list[float]:
    lines: list[float] = []
    for raw in book:
        try:
            lines.append(float(str(raw).replace(",", ".")))
        except ValueError:
            continue
    return sorted(set(lines))


def snap_line_to_book(
    pattern_line: float | None,
    direction: str,
    available: list[float],
) -> tuple[float | None, str | None]:
    """Ajusta linha do padrão KXL para a linha disponível na Superbet."""
    if pattern_line is None or not available:
        return pattern_line, None
    if direction == "under":
        # Linha mais apertada ainda coberta pelo padrão (<= pattern_line).
        candidates = [ln for ln in available if ln <= pattern_line + 1e-9]
        if candidates:
            snapped = max(candidates)
            if abs(snapped - pattern_line) > 1e-9:
                return snapped, (
                    f"Linha ajustada de {pattern_line:g} → {snapped:g} (menor linha Under na Superbet "
                    f"compatível com o padrão {pattern_line:g})."
                )
            return snapped, None
        snapped = min(available)
        return snapped, (
            f"Linha ajustada de {pattern_line:g} → {snapped:g} (Superbet não oferece Under {pattern_line:g})."
        )
    if direction == "over":
        candidates = [ln for ln in available if ln >= pattern_line - 1e-9]
        if candidates:
            snapped = min(candidates)
            if abs(snapped - pattern_line) > 1e-9:
                return snapped, (
                    f"Linha ajustada de {pattern_line:g} → {snapped:g} (menor Over ≥ padrão na Superbet)."
                )
            return snapped, None
        snapped = max(available)
        return snapped, (
            f"Linha ajustada de {pattern_line:g} → {snapped:g} (Superbet não oferece Over {pattern_line:g})."
        )
    return pattern_line, None


def _pick_outcome_label(direction: str, line: float) -> str:
    if direction == "over":
        return f"Mais de {line:g}"
    if direction == "under":
        return f"Menos de {line:g}"
    return direction


def _match_outcome_price(outcomes: dict[str, float], direction: str, line: float) -> float | None:
    target = _pick_outcome_label(direction, line).lower()
    for label, price in outcomes.items():
        ll = label.lower()
        if ll == target:
            return price
        if direction == "over" and any(k in ll for k in _OVER_LABELS) and f"{line:g}" in ll:
            return price
        if direction == "under" and any(k in ll for k in _UNDER_LABELS) and f"{line:g}" in ll:
            return price
    return None


def _line_book_for_leg(
    leg: dict[str, Any],
    snapshot: SuperbetEventSnapshot,
) -> tuple[dict[str, dict[str, float]], str | None]:
    stat = leg["stat"]
    period = leg["period"]
    entity = leg.get("entity")
    team_side = leg.get("team_side")

    if stat == "goals":
        if period == "first_half":
            return snapshot.first_half_totals, "Total de Gols (1º Tempo)"
        return snapshot.totals, "Total de Gols"
    if stat == "yellow_cards":
        if period == "first_half":
            return snapshot.first_half_yellow_cards, "Total de Cartões Amarelos (1º Tempo)"
        return snapshot.yellow_cards, "Total de Cartões Amarelos"
    if stat == "corners":
        return snapshot.corners, "Total de Escanteios"
    if stat == "shots":
        side = "home" if entity == "team" and team_side == "home" else "away"
        if entity == "team":
            team_name = snapshot.home_team if side == "home" else snapshot.away_team
            return snapshot.team_shots.get(side, {}), f"{team_name} - Total de Chutes"
        if entity == "opponent":
            side = "away" if team_side == "home" else "home"
            team_name = snapshot.home_team if side == "home" else snapshot.away_team
            return snapshot.team_shots.get(side, {}), f"{team_name} - Total de Chutes"
    if stat == "goals" and entity == "team":
        side = "home" if team_side == "home" else "away"
        team_name = snapshot.home_team if side == "home" else snapshot.away_team
        return snapshot.team_totals.get(side, {}), f"{team_name} - Total de Gols"
    return {}, None


def enrich_leg_with_superbet(
    leg: dict[str, Any],
    snapshot: SuperbetEventSnapshot | None,
) -> dict[str, Any]:
    """Enriquece perna com odd Superbet, linha ajustada e EV (prob = taxa KXL)."""
    enriched = dict(leg)
    if snapshot is None:
        enriched.update({
            "available_on_book": False,
            "market_odd": None,
            "implied_prob": None,
            "expected_value": None,
            "edge_pp": None,
            "superbet_market": None,
            "superbet_pick": None,
            "line_adjustment": None,
        })
        return enriched

    book, market_name = _line_book_for_leg(leg, snapshot)
    available = _parse_available_lines(book)
    snapped_line, line_note = snap_line_to_book(leg.get("line"), leg["direction"], available)

    if snapped_line is not None and leg.get("line") != snapped_line:
        enriched["line"] = snapped_line
        enriched["label"] = _rebuild_label(enriched, snapshot)

    odd = None
    if snapped_line is not None and book:
        line_key = f"{snapped_line:g}".replace(",", ".")
        outcomes = book.get(line_key) or book.get(str(snapped_line)) or {}
        if not outcomes:
            for k, v in book.items():
                try:
                    if abs(float(k) - snapped_line) < 1e-9:
                        outcomes = v
                        break
                except ValueError:
                    continue
        odd = _match_outcome_price(outcomes, leg["direction"], snapped_line)

    prob = float(leg.get("hit_rate") or 0)
    ev_payload = None
    if odd and odd > 1:
        ev_payload = evaluate_outcome(leg["direction"], prob, odd)
        enriched.update({
            "available_on_book": True,
            "market_odd": round(odd, 3),
            "implied_prob": round(ev_payload.implied_prob, 4),
            "expected_value": round(ev_payload.expected_value, 4),
            "edge_pp": round((prob - ev_payload.implied_prob) * 100, 2),
            "superbet_market": market_name,
            "superbet_pick": _pick_outcome_label(leg["direction"], snapped_line or 0),
            "line_adjustment": line_note,
            "fair_odd": round(ev_payload.fair_odd, 2),
        })
    else:
        enriched.update({
            "available_on_book": False,
            "market_odd": None,
            "implied_prob": None,
            "expected_value": None,
            "edge_pp": None,
            "superbet_market": market_name,
            "superbet_pick": _pick_outcome_label(leg["direction"], snapped_line or leg.get("line") or 0)
            if snapped_line or leg.get("line")
            else None,
            "line_adjustment": line_note,
        })
    return enriched


def _rebuild_label(leg: dict[str, Any], snapshot: SuperbetEventSnapshot) -> str:
    team_name = None
    if leg.get("entity") == "team":
        team_name = normalize_national_team(
            snapshot.home_team if leg.get("team_side") == "home" else snapshot.away_team
        )
    elif leg.get("entity") == "opponent":
        team_name = normalize_national_team(
            snapshot.away_team if leg.get("team_side") == "home" else snapshot.home_team
        )
    period_pt = _PERIOD_LABEL.get(leg["period"], leg["period"])
    stat_pt = _STAT_LABEL.get(leg["stat"], leg["stat"])
    dir_pt = _DIRECTION_LABEL.get(leg["direction"], leg["direction"])
    line = leg.get("line")
    line_s = f" {line:g}" if line is not None else ""
    if leg.get("entity") == "match_total":
        return f"{period_pt} — {stat_pt} na Partida: {dir_pt}{line_s}"
    scope = team_name or "Partida"
    return f"{period_pt} — {stat_pt} ({scope}): {dir_pt}{line_s}"


def enrich_combo_ticket(
    ticket: dict[str, Any],
    snapshot: SuperbetEventSnapshot | None,
) -> dict[str, Any]:
    """Enriquece bilhete combo com odds/EV e métricas agregadas."""
    if not ticket.get("available"):
        return ticket

    main = [enrich_leg_with_superbet(b, snapshot) for b in ticket.get("main_bets", [])]
    reserves = [enrich_leg_with_superbet(b, snapshot) for b in ticket.get("reserve_bets", [])]

    combo_odd = None
    combo_ev = None
    book_legs = [b for b in main if b.get("available_on_book") and b.get("market_odd")]
    if len(book_legs) == len(main) and main:
        combo_odd = round(math.prod(float(b["market_odd"]) for b in main), 3)
        combo_prob = math.prod(float(b["hit_rate"]) for b in main)
        combo_ev = round(combo_prob * combo_odd - 1.0, 4)

    notes = list(ticket.get("strategy_notes") or [])
    if snapshot is None:
        notes.append("Odds Superbet não carregadas — informe superbet_event_id para cruzar EV.")
    elif book_legs:
        notes.append(
            f"Combo na Superbet: odd ~{combo_odd:.2f}, EV estimado {combo_ev * 100:+.1f}% "
            f"(prob. histórica KXL × odd combinada)."
            if combo_odd and combo_ev is not None
            else f"{len(book_legs)}/{len(main)} pernas com odd na Superbet."
        )
    else:
        notes.append("Mercados do combo não encontrados na captura Superbet — confira nomes na casa.")

    return {
        **ticket,
        "main_bets": main,
        "reserve_bets": reserves,
        "strategy_notes": notes,
        "combo_odd": combo_odd,
        "combo_ev": combo_ev,
        "superbet_captured_at": snapshot.captured_at if snapshot else None,
        "book_coverage": {
            "main_available": sum(1 for b in main if b.get("available_on_book")),
            "main_total": len(main),
            "reserve_available": sum(1 for b in reserves if b.get("available_on_book")),
            "reserve_total": len(reserves),
        },
    }


__all__ = [
    "enrich_combo_ticket",
    "enrich_leg_with_superbet",
    "snap_line_to_book",
]
