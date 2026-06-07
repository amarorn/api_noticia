import json
from pathlib import Path

from ingest.superbet.client import _parse_sse_array_payload
from ingest.superbet.parser import parse_live_event_summary

FIXTURE = Path(__file__).parent / "fixtures" / "superbet_live_football.json"


def test_parse_live_event_summary_fixture():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    summary = parse_live_event_summary(raw)
    assert summary is not None
    assert summary.event_id == 13281779
    assert summary.home_team == "Ca San Juan Fc"
    assert summary.away_team == "Academica SC"
    assert summary.minute == 19
    assert summary.home_score == 0
    assert summary.away_score == 1
    assert summary.sport_id == 5
    assert summary.period_label == "1H"


def test_parse_sse_array_payload_extracts_all_events():
    payload = (
        'data:[{"event_id":1,"fixture":{"sport_id":5,"event_name":"A·B"}},'
        '{"event_id":2,"fixture":{"sport_id":5,"event_name":"C·D"}}]\n'
    )
    events = _parse_sse_array_payload(payload)
    assert len(events) == 2
    assert events[0]["event_id"] == 1
    assert events[1]["event_id"] == 2
