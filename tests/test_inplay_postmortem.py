"""Post-mortem automático de eventos Superbet."""
from __future__ import annotations

import json

from pipelines.inplay_postmortem import (
    build_inplay_postmortem,
    get_or_build_inplay_postmortem,
    load_inplay_postmortem,
    regenerate_inplay_postmortems,
    save_inplay_postmortem,
)


def test_build_postmortem_for_belgium_egypt():
    report = build_inplay_postmortem(
        11499882,
        home_score=1,
        away_score=1,
        ht_home=0,
        ht_away=1,
        home_team="Bélgica",
        away_team="Egito",
    )
    assert report["final_score"] == "1x1"
    assert report["n_ticks"] > 0
    assert report["tip_summary"]["unique_tips"] >= 1
    lost = [t for t in report["tips_by_market"] if t["result"] == "lost"]
    won = [t for t in report["tips_by_market"] if t["result"] == "won"]
    assert any(t["market"] == "2h_hcap_away_m0_5" for t in lost)
    assert report["issues"]
    assert any(i["code"] == "bad_2h_away_minus_half" for i in report["issues"])


def test_save_postmortem_writes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "pipelines.inplay_postmortem._gold_event_dir",
        lambda eid: tmp_path / "gold" / "superbet" / "events" / str(eid),
    )
    out = save_inplay_postmortem(
        999,
        home_score=0,
        away_score=0,
        ht_home=0,
        ht_away=0,
    )
    assert out.exists()
    assert out.name == "postmortem.json"


def test_get_or_build_from_final_json(tmp_path, monkeypatch):
    event_dir = tmp_path / "gold" / "superbet" / "events" / "888"
    event_dir.mkdir(parents=True)
    (event_dir / "final.json").write_text(
        json.dumps(
            {
                "event_id": 888,
                "home_team": "A",
                "away_team": "B",
                "home_score": 0,
                "away_score": 0,
                "ht_score": "0x0",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "pipelines.inplay_postmortem._gold_event_dir",
        lambda eid: tmp_path / "gold" / "superbet" / "events" / str(eid),
    )
    report = get_or_build_inplay_postmortem(888)
    assert report is not None
    assert report["event_id"] == 888
    assert load_inplay_postmortem(888) is not None


def test_regenerate_batch_skips_existing(tmp_path, monkeypatch):
    event_dir = tmp_path / "gold" / "superbet" / "events" / "777"
    event_dir.mkdir(parents=True)
    (event_dir / "final.json").write_text(
        json.dumps({"event_id": 777, "home_score": 1, "away_score": 0, "ht_score": "1x0"}),
        encoding="utf-8",
    )
    (event_dir / "postmortem.json").write_text('{"event_id":777}', encoding="utf-8")
    monkeypatch.setattr(
        "pipelines.inplay_postmortem._gold_event_dir",
        lambda eid: tmp_path / "gold" / "superbet" / "events" / str(eid),
    )
    results = regenerate_inplay_postmortems(event_ids=[777], only_missing=True)
    assert results == [{"event_id": 777, "status": "skipped", "reason": "postmortem_exists"}]
