"""Testes do advice de basquete in-play."""
from __future__ import annotations

from models.basket_bet_advice import build_basket_bet_advice_report
from models.basket_inplay import simulate_basket_inplay
from ingest.superbet.parser import SuperbetEventSnapshot


def _make_snapshot(
    moneyline: dict[str, float] | None = None,
    spread: dict[str, dict[str, float]] | None = None,
    total: dict[str, dict[str, float]] | None = None,
) -> SuperbetEventSnapshot:
    return SuperbetEventSnapshot(
        event_id=1,
        home_team="LAL",
        away_team="GSW",
        event_name="LAL·GSW",
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
        moneyline_odds=moneyline or {},
        moneyline_implied={},
        spread_odds=spread or {},
        spread_implied={},
        total_points_odds=total or {},
        total_points_implied={},
    )


class TestBasketBetAdvice:
    def test_aporte_when_strong_edge(self):
        inplay = simulate_basket_inplay(
            home_team="LAL",
            away_team="GSW",
            home_score=50,
            away_score=45,
            minute=24,
            total_points_odds={"220.5": {"over": 1.90, "under": 1.90}},
            spread_odds={"m5_5": {"home": 1.90, "away": 1.90}},
        )
        # Cria uma odd de mercado desalinhada: modelo vai achar edge
        snapshot = _make_snapshot(
            moneyline={"1": 10.0, "2": 1.01},  # modelo diz home favorito, mercado diz zebra
            total={"220.5": {"over": 10.0, "under": 1.01}},  # edge no under
        )
        report = build_basket_bet_advice_report(inplay=inplay, snapshot=snapshot, bankroll=1000)
        assert report["confidence"]["score"] > 0.5
        assert len(report["aportes"]) > 0
        first = report["aportes"][0]
        assert first["action"] == "apostar"
        assert first["expected_value"] > 0
        assert first["suggested_stake_value"] is not None

    def test_no_aporte_without_edge(self):
        inplay = simulate_basket_inplay(
            home_team="LAL",
            away_team="GSW",
            home_score=50,
            away_score=45,
            minute=24,
            total_points_odds={"220.5": {"over": 1.90, "under": 1.90}},
        )
        # Odds simétricas alinhadas com mercado (~50/50 over/under)
        snapshot = _make_snapshot(total={"300.5": {"over": 1.90, "under": 1.90}})
        report = build_basket_bet_advice_report(inplay=inplay, snapshot=snapshot, bankroll=1000)
        # Não deve haver aportes porque não há edge
        assert len(report["aportes"]) == 0
