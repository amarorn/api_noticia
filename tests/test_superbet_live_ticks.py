
import pandas as pd

from ingest.superbet.live_ticks import append_live_tick


def test_append_live_tick_creates_parquet(tmp_path, monkeypatch):
    parquet = tmp_path / "superbet" / "live_ticks.parquet"
    monkeypatch.setattr("ingest.superbet.live_ticks.live_ticks_path", lambda: parquet)

    snapshot = {
        "home_team": "Brasil",
        "away_team": "Egito",
        "betradar_id": "69548860",
        "h2h_odds": {"1": 1.85, "X": 3.5, "2": 4.2},
        "h2h_implied": {"1": 0.52, "X": 0.28, "2": 0.20},
        "raw_market_count": 96,
        "captured_at": "2026-06-06T22:17:00Z",
        "inplay": {
            "minute": 17,
            "home_score": 1,
            "away_score": 1,
            "period_label": "1H",
            "status": "STARTED",
        },
    }
    inplay = {
        "minute": 17,
        "prob_final_home": 0.55,
        "prob_final_draw": 0.30,
        "prob_final_away": 0.15,
        "final_line_probs": {"over_2_5": 0.45},
        "btts_final": 0.62,
    }
    advice = {
        "cashout": {"action": "manter", "remaining_ev": 0.08},
        "aportes": [
            {"market": "over_2_5", "outcome": "yes", "expected_value": 0.06},
        ],
    }

    path = append_live_tick(event_id=13247229, snapshot=snapshot, inplay=inplay, advice=advice)
    assert path == parquet
    assert parquet.exists()

    df = pd.read_parquet(path)
    assert len(df) == 1
    assert df.iloc[0]["event_id"] == 13247229
    assert df.iloc[0]["minute"] == 17
    assert df.iloc[0]["cashout_action"] == "manter"
    assert df.iloc[0]["top_aporte_ev"] == 0.06

    append_live_tick(event_id=13247229, snapshot=snapshot, inplay=inplay, advice=advice)
    df2 = pd.read_parquet(path)
    assert len(df2) == 2


def test_append_live_tick_recovers_corrupt_parquet(tmp_path, monkeypatch):
    parquet = tmp_path / "superbet" / "live_ticks.parquet"
    parquet.parent.mkdir(parents=True)
    parquet.write_bytes(b"not-a-valid-parquet")
    monkeypatch.setattr("ingest.superbet.live_ticks.live_ticks_path", lambda: parquet)

    snapshot = {"home_team": "A", "away_team": "B", "h2h_odds": {}, "inplay": {"minute": 1}}
    inplay = {"minute": 1, "prob_final_home": 0.5}
    advice = {"aportes": []}

    append_live_tick(event_id=1, snapshot=snapshot, inplay=inplay, advice=advice)
    df = pd.read_parquet(parquet)
    assert len(df) == 1
    corrupt_backups = list(parquet.parent.glob("live_ticks.corrupt.*.parquet"))
    assert len(corrupt_backups) == 1
