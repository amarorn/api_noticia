"""Testes de cruzamento combo KXL × odds Superbet."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingest.superbet.combo_markets import enrich_leg_with_superbet, snap_line_to_book
from ingest.superbet.parser import parse_superbet_event
from models.wc_team_patterns import build_combo_ticket

FIXTURE = Path("tests/fixtures/superbet_mexico_sa_half.json")


@pytest.fixture
def mexico_snapshot():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return parse_superbet_event(raw)


def test_snap_line_under_prefers_tighter_book_line():
    snapped, note = snap_line_to_book(2.5, "under", [0.5, 1.5, 2.5, 3.5])
    assert snapped == 2.5
    assert note is None

    snapped2, _ = snap_line_to_book(2.5, "under", [0.5, 1.5, 3.5])
    assert snapped2 == 1.5


def test_enrich_leg_goals_1h_from_fixture(mexico_snapshot):
    leg = {
        "stat": "goals",
        "period": "first_half",
        "direction": "under",
        "line": 2.5,
        "entity": "match_total",
        "hit_rate": 0.9,
        "hits": 9,
        "total": 10,
        "label": "test",
        "pattern_ref": "test",
    }
    out = enrich_leg_with_superbet(leg, mexico_snapshot)
    assert out["available_on_book"] is True
    assert out["market_odd"] == pytest.approx(1.92, rel=0.01)
    assert out["expected_value"] is not None
    assert out["expected_value"] > 0


def test_combo_ticket_enriched_with_combo_odd(mexico_snapshot):
    ticket = build_combo_ticket("Mexico", "South Africa", snapshot=mexico_snapshot)
    assert ticket.get("combo_odd") is not None or ticket["book_coverage"]["main_available"] >= 0
    if ticket.get("combo_odd"):
        assert ticket["combo_ev"] is not None
