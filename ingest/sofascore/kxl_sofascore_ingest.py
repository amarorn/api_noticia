from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import structlog

from ingest.sofascore.client import SofascoreClient
from ingest.sofascore.fede_mapper import map_lineups_to_fede
from ingest.sofascore.feju_mapper import map_referee_to_feju
from ingest.sofascore.event_helpers import (
    canonical_from_event_team,
    count_fept_ratings,
    find_event_id,
    resolve_match_date,
)
from ingest.sofascore.fept_mapper import map_lineups_to_fept
from ingest.sofascore.teams import event_team_names, load_team_map, sides_for_event
from schemas.national_teams import normalize_national_team
from schemas.wc_kxl_dynamic import (
    FejuArbitro,
    FedeElenco,
    FeptEscalacao,
    WcKxlMatchInput,
    WcKxlPartida,
)

logger = structlog.get_logger()


@dataclass(frozen=True)
class KxlSofascoreIngestResult:
    home_team: str
    away_team: str
    event_id: int
    match_date: str | None
    fept: FeptEscalacao
    fede: FedeElenco
    feju: FejuArbitro | None
    ratings_found: int
    ratings_missing: int
    absences_home: int
    absences_away: int
    source: str = "sofascore"

    def to_payload(self) -> dict[str, Any]:
        from datetime import datetime, timezone

        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "event_id": self.event_id,
            "match_date": self.match_date,
            "source": self.source,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "meta": {
                "ratings_found": self.ratings_found,
                "ratings_missing": self.ratings_missing,
                "absences_home": self.absences_home,
                "absences_away": self.absences_away,
                "referee": self.feju.nome_arbitro if self.feju else None,
                "referee_profile": self.feju.perfil if self.feju else None,
            },
            "kxl_match": WcKxlMatchInput(
                partida=WcKxlPartida(
                    mandante=self.home_team,
                    visitante=self.away_team,
                ),
                fept=self.fept,
                fede=self.fede,
                feju=self.feju,
            ).model_dump(exclude_none=True),
        }

    def to_fept_result(self):
        from ingest.sofascore.fept_ingest import FeptIngestResult

        return FeptIngestResult(
            home_team=self.home_team,
            away_team=self.away_team,
            event_id=self.event_id,
            match_date=self.match_date,
            fept=self.fept,
            ratings_found=self.ratings_found,
            ratings_missing=self.ratings_missing,
        )


def build_kxl_sofascore_payload(
    *,
    home_team: str | None = None,
    away_team: str | None = None,
    event_id: int | None = None,
    match_date: date | None = None,
    client: SofascoreClient | None = None,
    team_map: dict[str, dict] | None = None,
) -> KxlSofascoreIngestResult:
    team_map = team_map if team_map is not None else load_team_map()
    sofascore = client or SofascoreClient()

    if event_id is not None:
        event = sofascore.event(event_id)
        lineups = sofascore.event_lineups(event_id)
        resolved_date = resolve_match_date(event, match_date)
    else:
        if match_date is None or not home_team or not away_team:
            raise ValueError("Informe --date com --home/--away ou use --event-id")
        home = normalize_national_team(home_team)
        away = normalize_national_team(away_team)
        event = find_event_id(
            sofascore,
            home_team=home,
            away_team=away,
            match_date=match_date,
            team_map=team_map,
        )
        event_id = int(event["id"])
        lineups = sofascore.event_lineups(event_id)
        resolved_date = resolve_match_date(event, match_date)

    if not lineups.get("home") and not lineups.get("away"):
        raise LookupError(f"Lineups indisponíveis para o evento {event_id}")

    if not home_team or not away_team:
        home = canonical_from_event_team(event.get("homeTeam") or {}, team_map)
        away = canonical_from_event_team(event.get("awayTeam") or {}, team_map)
    else:
        home = normalize_national_team(home_team)
        away = normalize_national_team(away_team)

    home_is_event_home, _, _ = sides_for_event(
        event,
        home_team=home,
        away_team=away,
        team_map=team_map,
    )

    rating_cache: dict[int, float | None] = {}

    def fetch_statistics(player_id: int) -> list[dict[str, Any]]:
        return sofascore.player_statistics(player_id)

    fept = map_lineups_to_fept(
        lineups,
        home_is_event_home=home_is_event_home,
        fetch_statistics=fetch_statistics,
        rating_cache=rating_cache,
    )
    fede = map_lineups_to_fede(
        lineups,
        home_is_event_home=home_is_event_home,
        fetch_statistics=fetch_statistics,
        rating_cache=rating_cache,
    )
    feju = map_referee_to_feju(event.get("referee"))

    found, missing = count_fept_ratings(fept)
    event_home_name, event_away_name = event_team_names(event)
    logger.info(
        "kxl_sofascore_ingested",
        event_id=event_id,
        home=home,
        away=away,
        sofascore=f"{event_home_name} x {event_away_name}".strip(),
        ratings_found=found,
        ratings_missing=missing,
        absences_home=len(fede.desfalques_mandante),
        absences_away=len(fede.desfalques_visitante),
        referee=feju.nome_arbitro if feju else None,
        referee_profile=feju.perfil if feju else None,
    )
    return KxlSofascoreIngestResult(
        home_team=home,
        away_team=away,
        event_id=event_id,
        match_date=resolved_date,
        fept=fept,
        fede=fede,
        feju=feju,
        ratings_found=found,
        ratings_missing=missing,
        absences_home=len(fede.desfalques_mandante),
        absences_away=len(fede.desfalques_visitante),
    )
