from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import structlog

from ingest.sofascore.client import SofascoreClient, SofascoreClientError, SofascoreWafBlockedError
from ingest.sofascore.stats_dataset import load_match_stats_history, stats_training_summary
from ingest.sofascore.stats_ingest import ingest_match_stats
from ingest.sofascore.teams import load_team_map, resolve_team_id
from schemas.national_teams import normalize_national_team

logger = structlog.get_logger()


@dataclass(frozen=True)
class HistoryIngestReport:
    teams_processed: int
    events_attempted: int
    events_ingested: int
    events_skipped: int
    events_failed: int
    parquet_matches: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "teams_processed": self.teams_processed,
            "events_attempted": self.events_attempted,
            "events_skipped": self.events_skipped,
            "events_ingested": self.events_ingested,
            "events_failed": self.events_failed,
            "parquet_matches": self.parquet_matches,
        }


def _event_finished(event: dict[str, Any]) -> bool:
    status = event.get("status") or {}
    code = status.get("code")
    if code == 100:
        return True
    return str(status.get("type") or "").lower() == "finished"


def _existing_event_ids() -> set[int]:
    df = load_match_stats_history()
    if df.empty or "event_id" not in df.columns:
        return set()
    return {int(x) for x in df["event_id"].dropna().unique()}


def ingest_team_history(
    team: str,
    *,
    max_events: int = 25,
    client: SofascoreClient | None = None,
    team_map: dict[str, dict] | None = None,
    save: bool = True,
    skip_existing: bool = True,
) -> tuple[int, int, int]:
    """Ingere estatísticas dos últimos jogos de uma seleção. Retorna (ok, skip, fail)."""
    team_map = team_map if team_map is not None else load_team_map()
    sofascore = client or SofascoreClient()
    canonical = normalize_national_team(team)
    team_id, _ = resolve_team_id(canonical, team_map=team_map, client=sofascore)

    existing = _existing_event_ids() if skip_existing else set()
    events = sofascore.team_recent_events(team_id, page=0)

    ok = skip = fail = 0
    for event in events[:max_events]:
        if not _event_finished(event):
            skip += 1
            continue
        event_id = int(event["id"])
        if event_id in existing:
            skip += 1
            continue
        try:
            ingest_match_stats(event_id=event_id, save=save)
            existing.add(event_id)
            ok += 1
        except SofascoreWafBlockedError as exc:
            fail += 1
            logger.error(
                "sofascore_history_waf_abort",
                team=canonical,
                event_id=event_id,
                error=str(exc),
            )
            break
        except (LookupError, SofascoreClientError, ValueError) as exc:
            fail += 1
            logger.warning(
                "sofascore_history_event_failed",
                team=canonical,
                event_id=event_id,
                error=str(exc),
            )
            if sofascore.waf_blocked:
                logger.error("sofascore_history_waf_abort", team=canonical)
                break
    return ok, skip, fail


def ingest_all_teams_history(
    *,
    max_per_team: int = 25,
    teams: list[str] | None = None,
    client: SofascoreClient | None = None,
    save: bool = True,
) -> HistoryIngestReport:
    from contextlib import nullcontext

    from ingest.gcp.lake_store import cloud_lake_enabled
    from ingest.sofascore.stats_dataset import match_stats_batch_write

    team_map = load_team_map()
    roster = teams or sorted(team_map.keys())
    sofascore = client or SofascoreClient()
    batch = match_stats_batch_write() if save and cloud_lake_enabled() else nullcontext()

    attempted = ingested = skipped = failed = 0
    with batch:
        for team in roster:
            ok, skip, fail = ingest_team_history(
                team,
                max_events=max_per_team,
                client=sofascore,
                team_map=team_map,
                save=save,
            )
            attempted += ok + skip + fail
            ingested += ok
            skipped += skip
            failed += fail
            if sofascore.waf_blocked:
                logger.error("sofascore_history_waf_abort", team=team)
                break

    summary = stats_training_summary(load_match_stats_history())
    report = HistoryIngestReport(
        teams_processed=len(roster),
        events_attempted=attempted,
        events_ingested=ingested,
        events_skipped=skipped,
        events_failed=failed,
        parquet_matches=summary["matches"],
    )
    logger.info("sofascore_history_complete", **report.to_dict())
    return report


def ingest_fixtures_history(
    *,
    since_year: int = 2018,
    limit: int | None = None,
    client: SofascoreClient | None = None,
    save: bool = True,
) -> HistoryIngestReport:
    from contextlib import nullcontext

    from ingest.fixtures.world_cup import load_wc_fixtures
    from ingest.gcp.lake_store import cloud_lake_enabled
    from ingest.sofascore.stats_dataset import match_stats_batch_write

    sofascore = client or SofascoreClient()
    fixtures = load_wc_fixtures()
    if fixtures.empty:
        raise ValueError("Nenhum fixture WC carregado")

    subset = fixtures[fixtures["season"] >= since_year].sort_values("match_date")
    if limit is not None:
        subset = subset.head(limit)

    existing = _existing_event_ids()
    ingested = skipped = failed = 0
    batch = match_stats_batch_write() if save and cloud_lake_enabled() else nullcontext()
    with batch:
        for _, row in subset.iterrows():
            match_date = pd.to_datetime(row["match_date"], utc=True).date()
            home = normalize_national_team(row["home_team"])
            away = normalize_national_team(row["away_team"])
            try:
                result = ingest_match_stats(
                    home_team=home,
                    away_team=away,
                    match_date=match_date,
                    client=sofascore,
                    save=save,
                )
                if int(result.event_id) in existing:
                    skipped += 1
                else:
                    existing.add(int(result.event_id))
                    ingested += 1
            except SofascoreWafBlockedError as exc:
                failed += 1
                logger.error(
                    "sofascore_fixture_history_waf_abort",
                    home=home,
                    away=away,
                    date=match_date.isoformat(),
                    error=str(exc),
                    processed=ingested + skipped + failed,
                    total=len(subset),
                )
                break
            except (LookupError, SofascoreClientError, ValueError) as exc:
                failed += 1
                logger.debug(
                    "sofascore_fixture_history_miss",
                    home=home,
                    away=away,
                    date=match_date.isoformat(),
                    error=str(exc),
                )
                if sofascore.waf_blocked:
                    logger.error(
                        "sofascore_fixture_history_waf_abort",
                        processed=ingested + skipped + failed,
                        total=len(subset),
                    )
                    break

    summary = stats_training_summary(load_match_stats_history())
    report = HistoryIngestReport(
        teams_processed=0,
        events_attempted=len(subset),
        events_ingested=ingested,
        events_skipped=skipped,
        events_failed=failed,
        parquet_matches=summary["matches"],
    )
    logger.info("sofascore_fixtures_history_complete", **report.to_dict())
    return report
