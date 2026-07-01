"""Feed de eventos ao vivo via Sofascore (P2.2).

Busca incidents (gols, cartões, substituições) de um evento em andamento
e converte para GameEvent do módulo de momentum.

Uso: integrar com poll-superbet-live ou endpoint /advice para alimentar
o MomentumContext com eventos reais do jogo.
"""
from __future__ import annotations

import structlog

from models.wc_live_momentum import GameEvent

logger = structlog.get_logger()


# Mapeamento de incidentType do Sofascore para nosso event_type
_INCIDENT_MAP = {
    "goal": "goal",
    "ownGoal": "goal",
    "card": "_card",  # resolvido pelo cardType
    "substitution": "_sub",  # resolvido pela posição do jogador
    "period": "period",
}


def fetch_live_events(event_id: int) -> list[GameEvent]:
    """Busca incidents de um evento Sofascore e retorna GameEvents para momentum.

    Falha silenciosa: retorna lista vazia se Sofascore estiver indisponível
    (não deve bloquear o fluxo de advice).
    """
    try:
        from ingest.sofascore.client import SofascoreClient

        client = SofascoreClient()
        data = client.event_incidents(event_id)
    except Exception as exc:
        logger.warning(
            "sofascore_live_events_falha",
            event_id=event_id,
            error=str(exc),
        )
        return []

    incidents = data.get("incidents", [])
    return _parse_incidents(incidents)


def _parse_incidents(incidents: list[dict]) -> list[GameEvent]:
    """Converte lista de incidents do Sofascore em GameEvents."""
    events: list[GameEvent] = []

    for inc in incidents:
        incident_type = inc.get("incidentType", "")
        minute = inc.get("time", 0)
        is_home = inc.get("isHome", True)
        team = "home" if is_home else "away"

        if incident_type == "goal" or incident_type == "ownGoal":
            events.append(GameEvent(
                event_type="goal",
                minute=minute,
                team=team,
                detail=inc.get("player", {}).get("shortName", ""),
            ))

        elif incident_type == "card":
            card_type = inc.get("incidentClass", "")
            if card_type in ("red", "secondYellow"):
                events.append(GameEvent(
                    event_type="red_card",
                    minute=minute,
                    team=team,
                    detail=inc.get("player", {}).get("shortName", ""),
                ))
            # Amarelos simples não afetam o momentum por ora

        elif incident_type == "substitution":
            player_in = inc.get("playerIn", {})
            player_out = inc.get("playerOut", {})
            incident_class = inc.get("incidentClass", "")

            # Substituição por lesão: jogador sai machucado
            if incident_class == "injury":
                events.append(GameEvent(
                    event_type="injury",
                    minute=minute,
                    team=team,
                    detail=player_out.get("shortName", ""),
                ))
                # Ainda registrar a sub para efeito tático
                position = player_in.get("position", "").lower()
                sub_type = "sub_offensive" if position in ("f", "forward", "a", "attacker") else "sub_defensive"
                events.append(GameEvent(
                    event_type=sub_type,
                    minute=minute,
                    team=team,
                    detail=player_in.get("shortName", ""),
                ))
            else:
                # Sub normal: detectar se ofensiva pelo jogador que entra
                position = player_in.get("position", "").lower()
                if position in ("f", "forward", "a", "attacker"):
                    events.append(GameEvent(
                        event_type="sub_offensive",
                        minute=minute,
                        team=team,
                        detail=player_in.get("shortName", ""),
                    ))
                else:
                    events.append(GameEvent(
                        event_type="sub_defensive",
                        minute=minute,
                        team=team,
                        detail=player_in.get("shortName", ""),
                    ))

    return events


def live_events_as_dicts(event_id: int) -> list[dict]:
    """Conveniência: retorna GameEvents como lista de dicts (para JSON / momentum_events)."""
    events = fetch_live_events(event_id)
    return [
        {
            "event_type": e.event_type,
            "minute": e.minute,
            "team": e.team,
            "detail": e.detail,
            "source": "sofascore",
        }
        for e in events
    ]
