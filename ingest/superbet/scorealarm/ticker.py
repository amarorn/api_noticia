"""Timeline de eventos a partir do overview ScoreAlarm."""
from __future__ import annotations

from typing import Any

# Tipos de evento observados em live_events (overview).
EVENT_TYPE_LABELS: dict[int, str] = {
    1: "cartao",
    4: "gol",
    9: "chute_fora",
    10: "chute_no_alvo",
    14: "escanteio",
}

LOCALIZATION_FALLBACK: dict[str, str] = {
    "stats.football.match.shot_on_target": "Chute no alvo",
    "stats.football.match.shot_off_target": "Chute fora",
    "stats.football.match.corner_event": "Escanteio",
    "stats.football.match.goal_kicks": "Tiro de meta",
    "stats.football.match.yellow_cards": "Cartão amarelo",
    "stats.football.match.red_cards": "Cartão vermelho",
    "stats.football.match.substitution": "Substituição",
    "stats.football.match.fouls": "Falta",
}


def _localization_key(node: dict[str, Any] | None) -> str | None:
    if not node:
        return None
    text = node.get("text") or {}
    args = text.get("args") or []
    if args and isinstance(args[0], str):
        return args[0]
    return None


def _event_label(event: dict[str, Any]) -> str:
    for key in ("primary", "main", "secondary"):
        loc = _localization_key(event.get(key))
        if loc:
            return LOCALIZATION_FALLBACK.get(loc, loc.split(".")[-1].replace("_", " "))
    event_type = int(event.get("type") or 0)
    if event_type == 4:
        return "Gol"
    if event_type == 1:
        subtype = int(event.get("subtype") or 0)
        if subtype == 2:
            return "Cartão amarelo"
        if subtype in (3, 4):
            return "Cartão vermelho"
        return "Cartão"
    return EVENT_TYPE_LABELS.get(event_type, "Evento")


def _event_icon(event_type: int, subtype: int) -> str:
    if event_type == 4:
        return "⚽"
    if event_type == 1:
        return "🟥" if subtype in (3, 4) else "🟨"
    if event_type == 14:
        return "🚩"
    if event_type == 10:
        return "🎯"
    if event_type == 9:
        return "↗️"
    return "•"


def parse_timeline_events(
    live_events: list[dict[str, Any]],
    *,
    home_team: str,
    away_team: str,
) -> list[dict[str, Any]]:
    """Converte ``live_events`` do overview em lista ordenada (mais recente primeiro)."""
    rows: list[dict[str, Any]] = []
    for event in live_events:
        minute_node = event.get("minute") or {}
        minute = minute_node.get("value")
        if minute is None:
            continue
        side = int(event.get("side") or 0)
        team = home_team if side == 1 else away_team if side == 2 else ""
        event_type = int(event.get("type") or 0)
        subtype = int(event.get("subtype") or 0)
        score_text = None
        main = event.get("main") or {}
        main_text = (main.get("text") or {}).get("args") or []
        if main_text and isinstance(main_text[0], str) and ":" in main_text[0]:
            score_text = main_text[0]
        rows.append({
            "minute": int(minute),
            "added_time": event.get("added_time"),
            "team": team,
            "side": side,
            "type": event_type,
            "subtype": subtype,
            "label": _event_label(event),
            "icon": _event_icon(event_type, subtype),
            "score": score_text,
        })
    rows.sort(key=lambda r: (r["minute"], r.get("added_time") or 0), reverse=True)
    return rows


__all__ = ["parse_timeline_events"]
