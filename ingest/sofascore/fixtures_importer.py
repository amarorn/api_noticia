from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from config import settings
from ingest.sofascore.client import SofascoreClient
from ingest.sofascore.event_helpers import canonical_from_event_team, match_date_from_event
from ingest.sofascore.teams import load_team_map, resolve_team_id
from schemas.models import MatchResult
from schemas.national_teams import normalize_national_team

logger = structlog.get_logger()


def _build_label(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "1"
    elif home_score < away_score:
        return "2"
    return "X"


def _build_match_id(
    season: int,
    competition: str,
    home_team: str,
    away_team: str,
    match_date: str,
) -> str:
    base = f"sofa|{season}|{competition}|{home_team}|{away_team}|{match_date}"
    return hashlib.sha256(base.encode()).hexdigest()[:16]


def _infer_phase(competition: str) -> str:
    s = competition.lower()
    if "friendly" in s or "amistoso" in s:
        return "friendly"
    if "qualif" in s or "eliminatoria" in s or "prel" in s:
        return "qualifier"
    if "nations league" in s:
        return "nations_league"
    if "play-off" in s or "playoff" in s:
        return "playoff"
    if "group" in s or "grupo" in s:
        return "group"
    if "round" in s or "quarter" in s or "semi" in s or "final" in s:
        return "knockout"
    if "cup" in s or "copa" in s or "championship" in s:
        return "cup"
    return "other"


def _event_score(event: dict[str, Any], side: str) -> int | None:
    payload = event.get(f"{side}Score") or {}
    current = payload.get("current")
    if current is None:
        return None
    try:
        return int(current)
    except (TypeError, ValueError):
        return None


def _parse_sofascore_event(event: dict[str, Any], team_map: dict[str, dict]) -> MatchResult | None:
    """Converte um evento Sofascore em MatchResult."""
    status = event.get("status") or {}
    status_type = str(status.get("type") or "").lower()
    if status_type not in {"finished", "100"}:
        return None

    home = canonical_from_event_team(event.get("homeTeam") or {}, team_map)
    away = canonical_from_event_team(event.get("awayTeam") or {}, team_map)
    if not home or not away:
        return None

    home_score = _event_score(event, "home")
    away_score = _event_score(event, "away")
    if home_score is None or away_score is None:
        return None

    match_date = match_date_from_event(event)
    if not match_date:
        return None

    tournament = event.get("tournament") or event.get("uniqueTournament") or {}
    competition = tournament.get("name") or "Sofascore"
    season = int(match_date[:4]) if match_date else datetime.now(timezone.utc).year

    home_team = normalize_national_team(home)
    away_team = normalize_national_team(away)

    match_id = _build_match_id(season, competition, home_team, away_team, match_date)

    return MatchResult(
        match_id=match_id,
        season=season,
        competition=competition,
        round_number=0,
        match_date=match_date,
        home_team=home_team,
        away_team=away_team,
        home_team_raw=home,
        away_team_raw=away,
        home_score=home_score,
        away_score=away_score,
        label=_build_label(home_score, away_score),
        imported_at=datetime.now(timezone.utc),
        phase=_infer_phase(competition),
        group_name=None,
        is_neutral=True,
    )


def import_sofascore_team_matches(
    team: str,
    *,
    pages: int = 3,
    client: SofascoreClient | None = None,
    team_map: dict[str, dict] | None = None,
) -> list[MatchResult]:
    """Busca jogos recentes de uma seleção via Sofascore e converte para MatchResult."""
    team_map = team_map if team_map is not None else load_team_map()
    sofascore = client or SofascoreClient()
    canonical = normalize_national_team(team)
    team_id, _ = resolve_team_id(canonical, team_map=team_map, client=sofascore)

    results: list[MatchResult] = []
    seen: set[int] = set()

    for page in range(pages):
        events = sofascore.team_recent_events(team_id, page=page)
        if not events:
            break
        for event in events:
            event_id = int(event["id"])
            if event_id in seen:
                continue
            seen.add(event_id)
            parsed = _parse_sofascore_event(event, team_map)
            if parsed is not None:
                results.append(parsed)

    return results


def import_all_sofascore_matches(
    *,
    teams: list[str] | None = None,
    pages: int = 3,
    output_path: Path | None = None,
    skip_existing: bool = True,
) -> pd.DataFrame:
    """Importa jogos recentes de todas as seleções do mapa Sofascore.

    Args:
        teams: lista de nomes de times. Se None, usa todas do team_map.
        pages: páginas de eventos recentes por time.
        output_path: caminho do Parquet. Padrão: fixtures_path/sofascore_matches.parquet
        skip_existing: se True, não sobrescreve arquivo existente.

    Returns:
        DataFrame com todos os jogos importados (deduplicados).
    """
    out_path = output_path or (settings.fixtures_path / "sofascore_matches.parquet")

    if skip_existing and out_path.exists():
        logger.info("sofascore_fixtures_import_skipped_existing", path=str(out_path))
        return pd.read_parquet(out_path)

    team_map = load_team_map()
    target_teams = teams if teams is not None else list(team_map.keys())
    sofascore = SofascoreClient()

    all_matches: dict[str, MatchResult] = {}

    for team in target_teams:
        try:
            matches = import_sofascore_team_matches(
                team, pages=pages, client=sofascore, team_map=team_map
            )
            for m in matches:
                # Deduplica por match_id
                all_matches[m.match_id] = m
            logger.info(
                "sofascore_team_matches_imported",
                team=team,
                count=len(matches),
            )
        except Exception as exc:
            logger.warning(
                "sofascore_team_matches_failed",
                team=team,
                error=str(exc),
            )

    if not all_matches:
        logger.warning("sofascore_fixtures_import_empty")
        return pd.DataFrame()

    records = [m.model_dump(mode="json") for m in all_matches.values()]
    df = pd.DataFrame(records)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    logger.info(
        "sofascore_fixtures_import_done",
        total=len(records),
        teams=len(target_teams),
        path=str(out_path),
    )
    return df


def load_sofascore_fixtures() -> pd.DataFrame:
    """Carrega jogos Sofascore importados do Parquet local."""
    path = settings.fixtures_path / "sofascore_matches.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)
