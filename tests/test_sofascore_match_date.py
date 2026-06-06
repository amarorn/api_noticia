from datetime import date, datetime, timezone

from ingest.sofascore.event_helpers import match_date_from_event, resolve_match_date
from ingest.sofascore.stats_ingest import backfill_match_dates, build_match_stats_payload
from tests.test_sofascore_stats import FakeStatsClient


def test_match_date_from_event_start_timestamp():
    ts = int(datetime(2024, 6, 15, 20, 0, tzinfo=timezone.utc).timestamp())
    event = {"id": 99, "startTimestamp": ts}
    assert match_date_from_event(event) == "2024-06-15T20:00:00+00:00"


def test_resolve_match_date_prefers_explicit_date():
    event = {"startTimestamp": 1_700_000_000}
    resolved = resolve_match_date(event, date(2026, 6, 10))
    assert resolved == "2026-06-10"


def test_build_match_stats_payload_extracts_date_from_event():
    team_map = {
        "Brasil": {"sofascore_id": 4748},
        "Argentina": {"sofascore_id": 4819},
    }
    ts = int(datetime(2025, 3, 20, 18, 30, tzinfo=timezone.utc).timestamp())
    event = {
        "id": 42,
        "startTimestamp": ts,
        "homeTeam": {"id": 4748, "name": "Brazil"},
        "awayTeam": {"id": 4819, "name": "Argentina"},
    }
    client = FakeStatsClient(event, {"statistics": []}, {"incidents": []})
    result = build_match_stats_payload(event_id=42, client=client, team_map=team_map)
    assert result.match_date == "2025-03-20T18:30:00+00:00"
    assert result.stats["match_date"] == "2025-03-20T18:30:00+00:00"


def test_backfill_match_dates_updates_parquet(tmp_path):
    import pandas as pd

    from ingest.sofascore.paths import MATCH_STATS_PARQUET

    parquet = tmp_path / MATCH_STATS_PARQUET
    pd.DataFrame(
        [
            {"event_id": 10, "home_team": "Brasil", "away_team": "Argentina", "match_date": None},
            {"event_id": 11, "home_team": "França", "away_team": "Alemanha", "match_date": "2024-01-01"},
        ]
    ).to_parquet(parquet, index=False)

    ts = int(datetime(2023, 11, 16, 21, 0, tzinfo=timezone.utc).timestamp())

    class FakeClient:
        def event(self, event_id: int) -> dict:
            if event_id == 10:
                return {"id": 10, "startTimestamp": ts}
            return {"id": event_id}

    report = backfill_match_dates(
        client=FakeClient(),
        output_dir=tmp_path,
        update_json=False,
    )
    df = pd.read_parquet(parquet)

    assert report == {"total": 1, "updated": 1, "skipped": 0, "failed": 0}
    assert pd.notna(df.loc[df["event_id"] == 10, "match_date"].iloc[0])
