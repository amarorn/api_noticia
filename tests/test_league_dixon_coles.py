"""Testes do modelo Dixon-Coles para campeonatos de clubes."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from models.league_dixon_coles import (
    LeagueDixonColesModel,
    league_expected_lambdas,
    predict_league_probs,
)


def _synthetic_fixtures(n_teams: int = 6, rounds: int = 8) -> pd.DataFrame:
    teams = [f"Time{i}" for i in range(1, n_teams + 1)]
    rows: list[dict] = []
    base = datetime(2022, 4, 1, tzinfo=UTC)
    idx = 0
    for rnd in range(1, rounds + 1):
        for i in range(0, n_teams - 1, 2):
            home, away = teams[i], teams[i + 1]
            hs = 2 if i == 0 else 1
            aws = 1 if i == 0 else 1
            rows.append(
                {
                    "match_id": f"m{idx}",
                    "season": 2022,
                    "competition": "Brasileirão",
                    "round_number": rnd,
                    "match_date": base + timedelta(days=idx * 3),
                    "home_team": home,
                    "away_team": away,
                    "home_score": hs,
                    "away_score": aws,
                    "label": "1" if hs > aws else ("X" if hs == aws else "2"),
                    "is_neutral": False,
                }
            )
            idx += 1
    return pd.DataFrame(rows)


@pytest.fixture
def fixtures_df() -> pd.DataFrame:
    return _synthetic_fixtures()


def test_league_probs_sum_to_one(fixtures_df: pd.DataFrame):
    model = LeagueDixonColesModel()
    model.fit(fixtures_df)
    probs = model.predict_probs(
        fixtures_df,
        "Time1",
        "Time2",
        before_date=datetime(2023, 1, 1, tzinfo=UTC),
    )
    assert abs(sum(probs.values()) - 1.0) < 1e-6
    assert set(probs.keys()) == {"1", "X", "2"}


def test_home_advantage_increases_home_lambda(fixtures_df: pd.DataFrame):
    before = datetime(2023, 1, 1, tzinfo=UTC)
    lam_home, lam_away = league_expected_lambdas(
        fixtures_df,
        "Time1",
        "Time2",
        before_date=before,
        is_neutral=False,
    )
    lam_home_n, lam_away_n = league_expected_lambdas(
        fixtures_df,
        "Time1",
        "Time2",
        before_date=before,
        is_neutral=True,
    )
    assert lam_home > lam_home_n
    assert lam_away == lam_away_n


def test_predict_league_probs_without_fixtures(monkeypatch):
    monkeypatch.setattr(
        "models.league_dixon_coles.load_league_fixtures",
        lambda _comp: pd.DataFrame(),
    )
    assert predict_league_probs("Flamengo", "Palmeiras", "Brasileirão") is None


def test_model_fits_rho(fixtures_df: pd.DataFrame):
    model = LeagueDixonColesModel()
    metrics = model.fit(fixtures_df)
    assert "rho" in metrics
    assert metrics["train_size"] >= 20
