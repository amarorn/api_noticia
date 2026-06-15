"""Testes do payload live_stats (posse proxy + Superbet)."""
from ingest.superbet.live_stats_payload import build_live_stats_payload, possession_from_corners
from ingest.superbet.parser import SuperbetInPlayState, SuperbetEventSnapshot


def _minimal_snapshot(**overrides) -> SuperbetEventSnapshot:
    base = dict(
        event_id=1,
        home_team="Guarani SP",
        away_team="SER Caxias",
        event_name="Guarani·Caxias",
        utc_date="2026-06-13T14:00:00Z",
        betradar_id="1",
        is_live=True,
        inplay=SuperbetInPlayState(
            home_score=1,
            away_score=0,
            minute=45,
            stoppage_time=None,
            home_corners=7,
            away_corners=0,
            home_yellow_cards=1,
            away_yellow_cards=0,
            ht_home_score=1,
            ht_away_score=0,
            period_label="HT",
            status="STARTED",
        ),
        h2h_odds={},
        h2h_implied={},
        totals={},
        totals_implied={},
        corners={},
        corners_implied={},
        combo_markets={},
        btts_odds={},
        next_goal_odds={},
        generosity_probs={},
        team_totals={},
        first_half_totals={},
        second_half_totals={},
        yellow_cards={},
        first_half_yellow_cards={},
        team_shots={"home": {}, "away": {}},
        team_shots_on_target={"home": {}, "away": {}},
        half_markets={},
        raw_market_count=0,
        captured_at="2026-06-13T15:00:00Z",
    )
    base.update(overrides)
    return SuperbetEventSnapshot(**base)


def test_possession_from_corners_balanced():
    assert possession_from_corners(5, 5) == (50.0, 50.0)


def test_possession_from_corners_dominance():
    home, away = possession_from_corners(7, 0)
    assert home == 65.0
    assert away == 35.0


def test_build_live_stats_uses_corners_proxy_when_sofascore_missing():
    payload = build_live_stats_payload(
        snapshot=_minimal_snapshot(),
        live_stats={},
        tick_extra={"home_corners": 7, "away_corners": 0},
        sofascore_event_id=None,
        sofascore_skipped="Sofascore indisponível",
    )
    assert payload["possession_source"] == "corners_proxy"
    assert payload["home_possession_pct"] == 65.0
    assert payload["home_corners"] == 7
    assert payload["home_yellow_cards"] == 1
    assert payload["warnings"]


def test_build_live_stats_momentum_proxy_when_no_corners():
    payload = build_live_stats_payload(
        snapshot=_minimal_snapshot(inplay=SuperbetInPlayState(
            home_score=0,
            away_score=0,
            minute=20,
            stoppage_time=None,
            home_corners=0,
            away_corners=0,
            home_yellow_cards=0,
            away_yellow_cards=0,
            ht_home_score=None,
            ht_away_score=None,
            period_label="1H",
            status="STARTED",
        )),
        live_stats={},
        tick_extra={"home_corners": 0, "away_corners": 0},
        sofascore_event_id=None,
        prob_next_goal_home=0.6,
        prob_next_goal_away=0.2,
    )
    assert payload["possession_source"] == "momentum_proxy"
    assert payload["home_possession_pct"] == 57.5
    assert payload["away_possession_pct"] == 42.5
