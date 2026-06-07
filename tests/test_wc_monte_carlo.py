import pandas as pd
import pytest

from models.wc_monte_carlo import simulate_match_mc


@pytest.fixture
def tiny_fixtures() -> pd.DataFrame:
    rows = []
    labels = ("1", "X", "2")
    for season in (2018, 2022):
        for i in range(12):
            label = labels[i % 3]
            hs, aws = (2, 1) if label == "1" else ((1, 1) if label == "X" else (0, 2))
            rows.append(
                {
                    "season": season,
                    "match_date": f"{season}-06-{(i % 12) + 1:02d}",
                    "home_team": "Brasil",
                    "away_team": "Argentina",
                    "home_score": hs,
                    "away_score": aws,
                    "label": label,
                    "phase": "group",
                    "is_neutral": True,
                }
            )
    return pd.DataFrame(rows)


def test_simulate_match_mc_returns_markets(tiny_fixtures):
    result = simulate_match_mc(
        tiny_fixtures,
        "Brasil",
        "Argentina",
        n_simulations=500,
        rho=-0.05,
        random_seed=1,
    )
    d = result.to_dict()
    assert 0 <= d["prob_home"] <= 1
    assert 0 <= d["over_2_5"] <= 1
    assert d["n_simulations"] == 500
    assert d["top_scores"]
    assert abs(d["prob_home"] + d["prob_draw"] + d["prob_away"] - 1.0) < 0.02
