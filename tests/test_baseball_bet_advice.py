"""Testes do advice de beisebol in-play."""
from __future__ import annotations

from models.baseball_bet_advice import build_baseball_bet_advice_report
from models.baseball_inplay import simulate_baseball_inplay
from ingest.superbet.parser import SuperbetEventSnapshot


def _make_snapshot(
    *,
    moneyline: dict[str, float] | None = None,
    spread: dict[str, dict[str, float]] | None = None,
    total: dict[str, dict[str, float]] | None = None,
    team_totals: dict[str, dict[str, dict[str, float]]] | None = None,
    baseball_market_names: dict[str, str] | None = None,
    baseball_period_markets: dict | None = None,
) -> SuperbetEventSnapshot:
    return SuperbetEventSnapshot(
        event_id=1,
        home_team="Hanwha Eagles",
        away_team="Kiwoom Heroes",
        event_name="Hanwha Eagles·Kiwoom Heroes",
        utc_date=None,
        betradar_id=None,
        is_live=True,
        inplay=None,
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
        team_totals=team_totals or {"home": {}, "away": {}},
        first_half_totals={},
        second_half_totals={},
        yellow_cards={},
        first_half_yellow_cards={},
        team_shots={"home": {}, "away": {}},
        team_shots_on_target={"home": {}, "away": {}},
        half_markets={},
        handicap_odds={},
        handicap_implied={},
        moneyline_odds=moneyline or {},
        moneyline_implied={},
        spread_odds=spread or {},
        spread_implied={},
        total_points_odds=total or {},
        total_points_implied={},
        baseball_market_names=baseball_market_names or {},
        baseball_period_markets=baseball_period_markets or {},
    )


class TestBaseballBetAdvice:
    def test_team_total_aporte_when_strong_edge(self):
        team_totals = {
            "home": {"1.5": {"over": 10.0, "under": 1.01}},
            "away": {"8.5": {"over": 1.01, "under": 10.0}},
        }
        inplay = simulate_baseball_inplay(
            home_team="Hanwha Eagles",
            away_team="Kiwoom Heroes",
            home_score=0,
            away_score=5,
            inning=5,
            moneyline_odds={"1": 8.5, "2": 1.04},
            team_totals=team_totals,
            n_simulations=2000,
            random_seed=5,
        )
        snapshot = _make_snapshot(team_totals=team_totals)
        report = build_baseball_bet_advice_report(inplay=inplay, snapshot=snapshot, bankroll=1000)
        markets = {a["market"] for a in report["aportes"]}
        assert "team_total_runs" in markets
        assert len(report["aportes"]) > 0

    def test_spread_prob_key_matches_parser_format(self):
        inplay = simulate_baseball_inplay(
            home_team="Hanwha Eagles",
            away_team="Kiwoom Heroes",
            home_score=2,
            away_score=3,
            inning=5,
            spread_odds={"p4_5": {"home": 1.78}, "m4_5": {"away": 1.92}},
            n_simulations=2000,
            random_seed=11,
        )
        assert "home_p4_5" in inplay.spread_probs
        assert "away_m4_5" in inplay.spread_probs
        assert inplay.spread_probs["away_m4_5"] < 1.0

    def test_no_aporte_without_edge(self, monkeypatch):
        monkeypatch.setattr("models.baseball_bet_advice.settings.baseball_live_min_edge_pp", 99.0)
        inplay = simulate_baseball_inplay(
            home_team="A",
            away_team="B",
            home_score=2,
            away_score=2,
            inning=4,
            total_runs_odds={"8.5": {"over": 1.90, "under": 1.90}},
        )
        snapshot = _make_snapshot(total={"8.5": {"over": 1.90, "under": 1.90}})
        report = build_baseball_bet_advice_report(inplay=inplay, snapshot=snapshot, bankroll=1000)
        assert len(report["aportes"]) == 0

    def test_uses_baseball_edge_threshold_not_global(self, monkeypatch):
        """Com edge entre 5pp e 10pp, beisebol gera aporte mesmo se LIVE_MIN_EDGE_PP global for 10."""
        monkeypatch.setattr("models.baseball_bet_advice.settings.live_min_edge_pp", 10.0)
        monkeypatch.setattr("models.baseball_bet_advice.settings.baseball_live_min_edge_pp", 5.0)
        inplay = simulate_baseball_inplay(
            home_team="A",
            away_team="B",
            home_score=2,
            away_score=2,
            inning=4,
            total_runs_odds={"8.5": {"over": 1.90, "under": 1.90}},
            n_simulations=3000,
            random_seed=2,
        )
        snapshot = _make_snapshot(total={"8.5": {"over": 1.90, "under": 1.90}})
        report = build_baseball_bet_advice_report(inplay=inplay, snapshot=snapshot, bankroll=1000)
        if report["aportes"]:
            assert any(a["edge_pp"] >= 5.0 for a in report["aportes"])
            assert all(a["edge_pp"] < 10.0 or a["edge_pp"] >= 5.0 for a in report["aportes"])
