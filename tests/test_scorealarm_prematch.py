from tests.fixtures.scorealarm_samples import H2H_PREMATCH, OVERVIEW_PREMATCH
from ingest.superbet.scorealarm.prematch import (
    apply_prematch_confidence_boost,
    build_prematch_context,
    parse_manager,
    parse_team_form_from_events,
)


def test_parse_manager_prefers_display_name():
    assert parse_manager(OVERVIEW_PREMATCH["team1_manager"]) == "Lorenzo, Nestor"


def test_parse_team_form_team1_events():
    form = parse_team_form_from_events(
        H2H_PREMATCH["team1_events"],
        focal_team_name="Colômbia",
        limit=5,
    )
    assert form["form"] == "V-V-D-E-V"
    assert form["wins"] == 3
    assert form["draws"] == 1
    assert form["losses"] == 1
    assert form["goals_avg"] == 1.6
    assert form["last_matches"][0]["opponent"] == "Jordânia"


def test_parse_team_form_team2_events():
    form = parse_team_form_from_events(
        H2H_PREMATCH["team2_events"],
        focal_team_name="Jordânia",
        limit=5,
    )
    assert form["form"] == "D-D-D-E-V"
    assert form["wins"] == 1
    assert form["losses"] == 3
    assert form["goals_avg"] == 1.0


def test_build_prematch_context_includes_coach_and_h2h():
    ctx = build_prematch_context(
        OVERVIEW_PREMATCH,
        H2H_PREMATCH,
        home_team="Colômbia",
        away_team="Jordânia",
    )
    assert ctx is not None
    assert ctx["home"]["coach"] == "Lorenzo, Nestor"
    assert ctx["away"]["coach"] == "Patrice Carteron"
    assert len(ctx["h2h_matches"]) == 1
    assert ctx["h2h_matches"][0]["score"] == "2-0"


def test_apply_prematch_confidence_boost_raises_score():
    base = {
        "score": 0.38,
        "label": "baixa",
        "reason": "Confiança BAIXA: poucos dados.",
    }
    prematch = build_prematch_context(
        OVERVIEW_PREMATCH,
        H2H_PREMATCH,
        home_team="Colômbia",
        away_team="Jordânia",
    )
    boosted = apply_prematch_confidence_boost(base, prematch)
    assert boosted is not None
    assert boosted["score"] > 0.38
    assert boosted["prematch_boost"] > 0
    assert "ScoreAlarm" in boosted["reason"]
