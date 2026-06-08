import json
from pathlib import Path

from ingest.superbet.benchmark import h2h_overround, market_benchmark
from ingest.superbet.parser import parse_superbet_event
from ingest.superbet.store import merge_snapshot_into_odds_file
from pipelines.wc_market_features import load_match_odds_index, match_implied_probs

FIXTURE = Path(__file__).parent / "fixtures" / "superbet_brasil_egito.json"


def test_parse_superbet_event_fixture():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snap = parse_superbet_event(raw)
    assert snap.home_team == "Brasil"
    assert snap.away_team == "Egito"
    assert snap.inplay is not None
    assert snap.inplay.home_score == 1
    assert snap.inplay.minute == 17
    assert snap.h2h_odds["1"] == 1.85
    assert abs(sum(snap.h2h_implied.values()) - 1.0) < 0.01
    assert "2.5" in snap.totals_implied


def test_merge_superbet_odds_updates_market_features(tmp_path, monkeypatch):
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snap = parse_superbet_event(raw)
    out = tmp_path / "superbet_odds.json"
    merge_snapshot_into_odds_file(snap, out)

    load_match_odds_index.cache_clear()
    monkeypatch.setattr(
        "pipelines.wc_market_features.DEFAULT_SUPERBET_ODDS",
        out,
    )
    load_match_odds_index.cache_clear()
    probs = match_implied_probs("Brasil", "Egito")
    assert probs["1"] > probs["2"]


def test_h2h_overround():
    margin = h2h_overround({"1": 1.85, "X": 3.4, "2": 4.2})
    assert margin is not None
    assert 0.02 < margin < 0.15


def test_market_benchmark_edges():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snap = parse_superbet_event(raw)
    bench = market_benchmark(
        snap,
        model_h2h={"1": 0.55, "X": 0.30, "2": 0.15},
        model_totals={"over_2_5": 0.45},
    )
    assert "1" in bench["h2h"]
    assert "edge" in bench["h2h"]["1"]
