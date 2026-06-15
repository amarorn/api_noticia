"""Handicap FT, asiático e parser Superbet estendido."""
from __future__ import annotations

import numpy as np

from ingest.superbet.parser import (
    _classify_ft_market,
    _extract_ft_markets,
    parse_superbet_event,
)
from models.wc_inplay import (
    _asian_effective_cover_prob,
    _asian_handicap_probs,
    _handicap_probs,
    simulate_inplay,
)


def test_classify_ft_handicap_markets():
    assert _classify_ft_market("Handicap") == "handicap"
    assert _classify_ft_market("Handicap Asiático") == "asian_handicap"
    assert _classify_ft_market("2º Tempo - Handicap") is None
    assert _classify_ft_market("Handicap 3-way") is None


def test_extract_ft_markets_from_payload():
    markets = [
        {
            "name": "Handicap",
            "odds": [
                {
                    "status": 1,
                    "price": 1.90,
                    "metadata": {"name": "Queanbeyan City", "special_bet_value": "-0.5"},
                },
                {
                    "status": 1,
                    "price": 1.95,
                    "metadata": {"name": "Monaro Panthers", "special_bet_value": "0.5"},
                },
            ],
        },
        {
            "name": "Handicap Asiático",
            "odds": [
                {
                    "status": 1,
                    "price": 1.85,
                    "metadata": {"name": "Queanbeyan City", "special_bet_value": "-0.25"},
                },
                {
                    "status": 1,
                    "price": 2.05,
                    "metadata": {"name": "Monaro Panthers", "special_bet_value": "0.25"},
                },
            ],
        },
    ]
    ft = _extract_ft_markets(markets, "Queanbeyan City", "Monaro Panthers")
    assert "m0_5" in ft["handicap"]
    assert ft["handicap"]["m0_5"]["home"] == 1.90
    assert "m0_25" in ft["asian_handicap"]
    assert ft["asian_handicap"]["m0_25"]["home"] == 1.85


def test_parse_superbet_event_includes_ft_handicap():
    raw = {
        "event_id": 999,
        "fixture": {"event_id": 999, "event_name": "Brasil·Egito"},
        "markets": [
            {
                "name": "Resultado Final",
                "odds": [
                    {"status": 1, "price": 2.0, "metadata": {"name": "1"}},
                    {"status": 1, "price": 3.2, "metadata": {"name": "X"}},
                    {"status": 1, "price": 3.5, "metadata": {"name": "2"}},
                ],
            },
            {
                "name": "Handicap Asiático",
                "odds": [
                    {
                        "status": 1,
                        "price": 1.92,
                        "metadata": {"name": "Brasil", "special_bet_value": "0"},
                    },
                    {
                        "status": 1,
                        "price": 1.92,
                        "metadata": {"name": "Egito", "special_bet_value": "0"},
                    },
                ],
            },
        ],
    }
    snap = parse_superbet_event(raw)
    assert "ft" in snap.half_markets
    assert snap.half_markets["ft"]["asian_handicap"]["0"]["home"] == 1.92


def test_asian_quarter_line_between_neighbors():
    diff = np.array([0.0, 0.0, 1.0, -1.0])
    n = len(diff)
    p025 = _asian_effective_cover_prob(diff, -0.25, "home", n)
    p0 = float(np.sum(diff > 0) / n)
    pm05 = float(np.sum(diff + (-0.5) > 0) / n)
    assert abs(p025 - (p0 + pm05) / 2) < 1e-9


def test_simulate_inplay_exposes_ft_and_asian_probs():
    r = simulate_inplay(
        home_team="A",
        away_team="B",
        home_score=1,
        away_score=0,
        minute=45,
        lambda_full_home=1.4,
        lambda_full_away=1.1,
        n_simulations=2000,
        random_seed=7,
    )
    assert r.ft_handicap_probs
    assert r.ft_asian_handicap_probs
    assert "home_m0_5" in r.ft_handicap_probs
    assert "home_m0_25" in r.ft_asian_handicap_probs
    assert r.ht_asian_handicap_probs
    assert r.sh_asian_handicap_probs


def test_handicap_probs_zero_line_excludes_draw():
    h = np.array([1, 0, 2, 1])
    a = np.array([0, 0, 1, 1])
    n = len(h)
    probs = _handicap_probs(h, a, n, lines=(0.0,))
    assert probs["home_0"] == 0.5
    assert probs["away_0"] == 0.0


def test_asian_handicap_probs_bounded():
    h = np.random.default_rng(1).poisson(1.2, 500)
    a = np.random.default_rng(2).poisson(1.0, 500)
    probs = _asian_handicap_probs(h, a, len(h))
    for v in probs.values():
        assert 0.0 <= v <= 1.0
