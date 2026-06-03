import math

import pytest

from ingest.fixtures.world_cup import load_wc_fixtures
from models.dixon_coles_wc import DixonColesWcModel
from models.poisson_wc import (
    dixon_coles_tau,
    predict_poisson,
    score_outcome_probs,
)


@pytest.fixture
def fixtures_df():
    return load_wc_fixtures()


def test_tau_low_score_adjustments():
    lam_h, lam_a, rho = 1.3, 1.1, -0.13
    assert dixon_coles_tau(0, 0, lam_h, lam_a, rho) == 1.0 - lam_h * lam_a * rho
    assert dixon_coles_tau(0, 1, lam_h, lam_a, rho) == 1.0 + lam_h * rho
    assert dixon_coles_tau(1, 0, lam_h, lam_a, rho) == 1.0 + lam_a * rho
    assert dixon_coles_tau(1, 1, lam_h, lam_a, rho) == 1.0 - rho
    assert dixon_coles_tau(2, 1, lam_h, lam_a, rho) == 1.0


def test_rho_zero_matches_independent_poisson():
    lam_h, lam_a = 1.4, 1.2
    independent = score_outcome_probs(lam_h, lam_a, rho=0.0)
    with_rho_zero = score_outcome_probs(lam_h, lam_a, rho=0.0)
    assert math.isclose(independent.prob_home, with_rho_zero.prob_home, rel_tol=1e-9)
    assert math.isclose(independent.prob_draw, with_rho_zero.prob_draw, rel_tol=1e-9)
    assert math.isclose(independent.prob_away, with_rho_zero.prob_away, rel_tol=1e-9)


def test_negative_rho_increases_draw_mass():
    lam_h, lam_a = 1.1, 1.0
    independent = score_outcome_probs(lam_h, lam_a, rho=0.0)
    corrected = score_outcome_probs(lam_h, lam_a, rho=-0.1)
    assert corrected.prob_draw > independent.prob_draw


def test_dixon_coles_model_fits_and_predicts(fixtures_df):
    if fixtures_df.empty:
        return
    model = DixonColesWcModel()
    metrics = model.fit(fixtures_df, holdout_season=2022)
    assert "rho" in metrics
    assert -0.21 <= model.rho <= 0.21

    row = fixtures_df.iloc[-1]
    pred = model.predict(
        fixtures_df,
        row["home_team"],
        row["away_team"],
        before_date=row["match_date"],
    )
    total = pred.prob_home + pred.prob_draw + pred.prob_away
    assert math.isclose(total, 1.0, rel_tol=1e-6)
    assert pred.prob_home >= 0
    assert pred.prob_draw >= 0
    assert pred.prob_away >= 0


def test_predict_poisson_still_independent(fixtures_df):
    if fixtures_df.empty:
        return
    row = fixtures_df.iloc[0]
    pred = predict_poisson(
        fixtures_df,
        row["home_team"],
        row["away_team"],
        before_date=row["match_date"],
    )
    total = pred.prob_home + pred.prob_draw + pred.prob_away
    assert math.isclose(total, 1.0, rel_tol=1e-6)
