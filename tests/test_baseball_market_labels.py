"""Testes dos rótulos de mercado beisebol."""
from __future__ import annotations

from models.baseball_bet_advice import build_baseball_bet_advice_report
from models.baseball_inplay import simulate_baseball_inplay
from models.baseball_market_labels import (
    format_baseball_selection_label,
    resolve_baseball_market_display,
)
from ingest.superbet.parser import SuperbetEventSnapshot


def _make_snapshot(**kwargs) -> SuperbetEventSnapshot:
    defaults = dict(
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
        team_totals={"home": {}, "away": {}},
        first_half_totals={},
        second_half_totals={},
        yellow_cards={},
        first_half_yellow_cards={},
        team_shots={"home": {}, "away": {}},
        team_shots_on_target={"home": {}, "away": {}},
        half_markets={},
        handicap_odds={},
        handicap_implied={},
        moneyline_odds={},
        moneyline_implied={},
        spread_odds={},
        spread_implied={},
        total_points_odds={},
        total_points_implied={},
        baseball_market_names={},
        baseball_period_markets={},
    )
    defaults.update(kwargs)
    return SuperbetEventSnapshot(**defaults)


class TestBaseballMarketLabels:
    def test_resolve_market_display_from_feed(self):
        names = {
            "moneyline": "Vencedor (incl. entradas extras)",
            "run_line": "Handicap (incl. entradas extras)",
            "total_runs": "Total de Corridas (incl. entradas extras)",
            "team_total_runs_home": "Hanwha Eagles - Total de Corridas (incl. entradas extras)",
        }
        assert resolve_baseball_market_display("moneyline", market_names=names) == names["moneyline"]
        assert resolve_baseball_market_display("run_line", market_names=names) == names["run_line"]
        assert resolve_baseball_market_display("total_runs", market_names=names) == names["total_runs"]
        assert (
            resolve_baseball_market_display(
                "team_total_runs",
                team="Hanwha Eagles",
                side="home",
                market_names=names,
            )
            == names["team_total_runs_home"]
        )

    def test_selection_labels_portuguese(self):
        assert format_baseball_selection_label("moneyline", team="Hanwha Eagles") == "Hanwha Eagles vence"
        assert format_baseball_selection_label("run_line", team="Kiwoom Heroes", line=-1.5) == "Kiwoom Heroes -1.5"
        assert format_baseball_selection_label("total_runs", outcome="over", line=8.5) == "Mais de 8.5"
        assert (
            format_baseball_selection_label("team_total_runs", team="Hanwha Eagles", outcome="under", line=3.5)
            == "Menos de 3.5 — Hanwha Eagles"
        )

    def test_advice_includes_market_display(self):
        team_totals = {
            "home": {"1.5": {"over": 10.0, "under": 1.01}},
            "away": {"8.5": {"over": 1.01, "under": 10.0}},
        }
        market_names = {
            "moneyline": "Vencedor (incl. entradas extras)",
            "team_total_runs_home": "Hanwha Eagles - Total de Corridas (incl. entradas extras)",
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
        snapshot = _make_snapshot(team_totals=team_totals, baseball_market_names=market_names)
        report = build_baseball_bet_advice_report(inplay=inplay, snapshot=snapshot, bankroll=1000)
        assert report["aportes"]
        home_aporte = next(a for a in report["aportes"] if a["market"] == "team_total_runs" and "home" in a["outcome"])
        assert home_aporte["market_display"] == market_names["team_total_runs_home"]
        assert home_aporte["label"].startswith("Mais de") or home_aporte["label"].startswith("Menos de")
