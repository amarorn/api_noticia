"""Testes: mercados in-play mortos pelo placar."""
from __future__ import annotations

from models.inplay_dead_market import is_dead_inplay_market


def test_btts_yes_dead_when_both_scored():
    dead, reason = is_dead_inplay_market("btts", "yes", home_score=1, away_score=1)
    assert dead
    assert "BTTS" in (reason or "")


def test_over_dead_when_line_beaten():
    dead, _ = is_dead_inplay_market("over_2_5", "yes", home_score=2, away_score=1)
    assert dead


def test_under_dead_when_over_hit():
    dead, _ = is_dead_inplay_market("over_2_5", "no", home_score=2, away_score=1)
    assert dead


def test_live_market_still_open():
    dead, _ = is_dead_inplay_market("over_2_5", "yes", home_score=1, away_score=0)
    assert not dead
