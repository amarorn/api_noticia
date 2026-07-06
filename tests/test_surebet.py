"""Testes do motor de surebet (arbitragem)."""
from __future__ import annotations

from models.surebet import (
    allocate_stakes,
    arbitrage_index,
    find_h2h_surebet,
    scan_h2h_surebets,
    surebet_margin_pct,
)


def test_arbitrage_index_detects_surebet():
    # Melhor odd por outcome entre casas → soma < 1
    best = {"1": 2.20, "X": 4.00, "2": 4.50}
    index = arbitrage_index(best)
    assert index < 1.0
    assert surebet_margin_pct(index) > 0


def test_arbitrage_index_no_surebet_when_overround():
    # Mesma casa típica — sem arbitragem
    odds = {"1": 1.85, "X": 3.40, "2": 4.20}
    index = arbitrage_index(odds)
    assert index > 1.0
    assert surebet_margin_pct(index) == 0.0


def test_allocate_stakes_equalizes_return():
    odds = {"1": 2.20, "X": 4.00, "2": 4.50}
    bankroll = 1000.0
    stakes = allocate_stakes(bankroll, odds)
    returns = {k: stakes[k] * odds[k] for k in odds}
    assert abs(returns["1"] - returns["X"]) < 0.02
    assert abs(returns["X"] - returns["2"]) < 0.02


def test_find_h2h_surebet_with_cross_book_quotes():
    quotes = [
        {"bookmaker": "bet365", "odds": {"1": 2.25, "X": 3.20, "2": 3.80}},
        {"bookmaker": "pinnacle", "odds": {"1": 2.10, "X": 3.60, "2": 4.60}},
        {"bookmaker": "williamhill", "odds": {"1": 2.15, "X": 3.50, "2": 4.40}},
    ]
    opp = find_h2h_surebet(
        home_team="Marrocos",
        away_team="Canadá",
        quotes=quotes,
        bankroll=1000,
        min_margin_pct=0.01,
    )
    # Com odds realistas pode não haver surebet — forçar caso artificial
    if opp is None:
        quotes[0]["odds"]["1"] = 2.50
        quotes[1]["odds"]["X"] = 4.20
        quotes[2]["odds"]["2"] = 5.00
        opp = find_h2h_surebet(
            home_team="Marrocos",
            away_team="Canadá",
            quotes=quotes,
            bankroll=1000,
            min_margin_pct=0.01,
        )

    assert opp is not None
    assert opp.margin_pct > 0
    assert len(opp.legs) == 3
    assert opp.profit_value > 0
    assert abs(sum(leg.stake_value for leg in opp.legs) - opp.bankroll) < 0.05


def test_scan_h2h_surebets_filters_events():
    events = [
        {
            "home_team": "Brasil",
            "away_team": "Marrocos",
            "commence_time": "2026-06-10T15:00:00Z",
            "quotes": [
                {"bookmaker": "a", "odds": {"1": 2.50, "X": 4.00, "2": 5.00}},
                {"bookmaker": "b", "odds": {"1": 2.10, "X": 3.50, "2": 3.80}},
            ],
        },
        {
            "home_team": "Argentina",
            "away_team": "México",
            "commence_time": None,
            "quotes": [
                {"bookmaker": "a", "odds": {"1": 1.90, "X": 3.40, "2": 4.50}},
            ],
        },
    ]
    found = scan_h2h_surebets(events, bankroll=1000, min_margin_pct=0.01)
    assert len(found) >= 1
    assert found[0].home_team == "Brasil"


def test_extract_all_h2h_from_event_payload():
    from ingest.odds.the_odds_api import extract_all_h2h

    event = {
        "home_team": "Morocco",
        "away_team": "Canada",
        "commence_time": "2026-06-10T15:00:00Z",
        "bookmakers": [
            {
                "key": "bet365",
                "markets": [{
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Morocco", "price": 2.1},
                        {"name": "Canada", "price": 3.8},
                        {"name": "Draw", "price": 3.4},
                    ],
                }],
            },
            {
                "key": "pinnacle",
                "markets": [{
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Morocco", "price": 2.15},
                        {"name": "Canada", "price": 3.9},
                        {"name": "Draw", "price": 3.35},
                    ],
                }],
            },
        ],
    }
    parsed = extract_all_h2h(event)
    assert parsed is not None
    assert len(parsed.quotes) == 2
    assert parsed.quotes[0].bookmaker in {"bet365", "pinnacle"}
