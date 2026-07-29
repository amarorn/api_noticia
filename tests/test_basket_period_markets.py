"""Testes de mercados por quarto e props de basquete (P1)."""
from __future__ import annotations

from ingest.superbet.basket_period_markets import (
    extract_basket_period_markets,
    extract_basket_team_totals,
)
from ingest.superbet.parser import parse_superbet_event
from models.basket_bet_advice import build_basket_bet_advice_report
from models.basket_inplay import simulate_basket_inplay
from ingest.superbet.parser import SuperbetEventSnapshot


def _period_markets_payload(home: str = "LAL", away: str = "GSW") -> list[dict]:
    return [
        {
            "name": "2º Quarto - Total de Pontos",
            "odds": [
                {
                    "price": 1.85,
                    "status": 1,
                    "metadata": {"code": "+", "name": "Mais", "special_bet_value": "45.5"},
                },
                {
                    "price": 1.95,
                    "status": 1,
                    "metadata": {"code": "-", "name": "Menos", "special_bet_value": "45.5"},
                },
            ],
        },
        {
            "name": "2º Quarto - 1 x 2",
            "odds": [
                {"price": 2.10, "status": 1, "metadata": {"code": "1", "name": home}},
                {"price": 1.70, "status": 1, "metadata": {"code": "2", "name": away}},
                {"price": 12.0, "status": 1, "metadata": {"code": "X", "name": "Empate"}},
            ],
        },
        {
            "name": "2º Quarto - Handicap",
            "odds": [
                {
                    "price": 1.90,
                    "status": 1,
                    "metadata": {"code": "1", "name": home, "special_bet_value": "+1.5"},
                },
                {
                    "price": 1.90,
                    "status": 1,
                    "metadata": {"code": "2", "name": away, "special_bet_value": "-1.5"},
                },
            ],
        },
        {
            "name": "2º Quarto - Total de Pontos de LAL",
            "odds": [
                {
                    "price": 1.88,
                    "status": 1,
                    "metadata": {"code": "+", "name": "Mais", "special_bet_value": "22.5"},
                },
                {
                    "price": 1.92,
                    "status": 1,
                    "metadata": {"code": "-", "name": "Menos", "special_bet_value": "22.5"},
                },
            ],
        },
        {
            "name": "Ímpar/Par (Inc. prorrogação)",
            "odds": [
                {"price": 1.90, "status": 1, "metadata": {"code": "ODD", "name": "Ímpar"}},
                {"price": 1.90, "status": 1, "metadata": {"code": "EVEN", "name": "Par"}},
            ],
        },
        {
            "name": "LAL - Total de Pontos (Inc. prorrogação)",
            "odds": [
                {
                    "price": 1.87,
                    "status": 1,
                    "metadata": {"code": "+", "name": "Mais", "special_bet_value": "110.5"},
                },
                {
                    "price": 1.93,
                    "status": 1,
                    "metadata": {"code": "-", "name": "Menos", "special_bet_value": "110.5"},
                },
            ],
        },
        {
            "name": "Resultado Final",
            "odds": [
                {"price": 1.80, "status": 1, "metadata": {"code": "1", "name": "1"}},
                {"price": 10.0, "status": 1, "metadata": {"code": "X", "name": "X"}},
                {"price": 2.20, "status": 1, "metadata": {"code": "2", "name": "2"}},
            ],
        },
        {
            "name": "Vencedor da Partida",
            "odds": [
                {"price": 1.75, "status": 1, "metadata": {"code": "1", "name": "1"}},
                {"price": 2.10, "status": 1, "metadata": {"code": "2", "name": "2"}},
            ],
        },
    ]


def test_extract_basket_period_markets():
    markets = _period_markets_payload()
    parsed = extract_basket_period_markets(markets, "LAL", "GSW")
    assert parsed["quarters"]["2"]["total"]["45.5"]["over"] == 1.85
    assert parsed["quarters"]["2"]["moneyline"]["1"] == 2.10
    assert parsed["quarters"]["2"]["spread"]["p1_5"]["home"] == 1.90
    assert parsed["quarters"]["2"]["team_total"]["home"]["22.5"]["over"] == 1.88
    assert parsed["odd_even"]["odd"] == 1.90
    assert parsed["display_names"]["q2_total"] == "2º Quarto - Total de Pontos"


def test_extract_basket_team_totals():
    markets = _period_markets_payload()
    tt = extract_basket_team_totals(markets, "LAL", "GSW")
    assert tt["home"]["110.5"]["over"] == 1.87
    assert "away" in tt


def test_parse_superbet_event_includes_basket_period_markets():
    ev = {
        "event_id": 42,
        "fixture": {
            "event_id": 42,
            "event_name": "LAL·GSW",
            "sport_id": 7,
            "event_tags": "superLive",
        },
        "inplay_stats": {
            "home_team_score": 28,
            "away_team_score": 25,
            "minutes": 6,
            "periods": [{"num": 1, "home_team_score": 28, "away_team_score": 25}],
        },
        "markets": _period_markets_payload(),
    }
    snap = parse_superbet_event(ev)
    assert snap.basket_period_markets["quarters"]["2"]["total"]
    assert snap.odd_even_odds["odd"] == 1.90
    assert snap.regulation_ml_odds["X"] == 10.0
    assert snap.moneyline_odds["1"] == 1.75
    assert snap.basket_period_markets["team_totals_ft"]["home"]["110.5"]["over"] == 1.87


def test_simulate_period_and_props_probs():
    period_markets = extract_basket_period_markets(_period_markets_payload(), "LAL", "GSW")
    team_totals = extract_basket_team_totals(_period_markets_payload(), "LAL", "GSW")
    period_markets["team_totals_ft"] = team_totals

    inplay = simulate_basket_inplay(
        home_team="LAL",
        away_team="GSW",
        home_score=28,
        away_score=25,
        minute=10,
        moneyline_odds={"1": 1.75, "2": 2.10},
        total_points_odds={"220.5": {"over": 1.90, "under": 1.90}},
        team_totals=team_totals,
        period_markets=period_markets,
        basket_periods=[{"num": 1, "home": 28, "away": 25}],
        n_simulations=2000,
        random_seed=7,
    )
    assert inplay.period_probs.get("q2_over_45_5", 0) > 0
    assert inplay.period_probs.get("q2_ml_1", 0) > 0
    assert inplay.team_total_probs.get("home_over_110_5", 0) >= 0
    assert abs(sum(inplay.regulation_ml_probs.values()) - 1.0) < 0.02
    assert abs(inplay.odd_even_probs["odd"] + inplay.odd_even_probs["even"] - 1.0) < 1e-6


def test_basket_period_aportes_structure():
    period_markets = extract_basket_period_markets(_period_markets_payload(), "LAL", "GSW")
    team_totals = extract_basket_team_totals(_period_markets_payload(), "LAL", "GSW")
    period_markets["team_totals_ft"] = team_totals
    inplay = simulate_basket_inplay(
        home_team="LAL",
        away_team="GSW",
        home_score=28,
        away_score=25,
        minute=10,
        total_points_odds={"220.5": {"over": 1.90, "under": 1.90}},
        team_totals=team_totals,
        period_markets=period_markets,
        n_simulations=500,
        random_seed=3,
    )
    snapshot = SuperbetEventSnapshot(
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
        regulation_ml_odds={"1": 50.0, "2": 1.01},
        odd_even_odds={"odd": 50.0, "even": 1.01},
        basket_period_markets=period_markets,
        total_points_odds={"500.5": {"over": 50.0, "under": 1.01}},
    )
    report = build_basket_bet_advice_report(inplay=inplay, snapshot=snapshot, bankroll=1000)
    markets = {a["market"] for a in report["aportes"]}
    assert "quarter_2_total" in markets or "team_total_points" in markets or "odd_even" in markets
    for aporte in report["aportes"]:
        assert aporte.get("market_display")
        assert aporte["label"] != aporte.get("market_display") or aporte["market"] == "odd_even"
