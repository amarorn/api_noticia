import math

import pytest

from ingest.fixtures.world_cup import load_wc_fixtures
from models.math_utils import sigmoid, softmax
from models.poisson_wc import goal_model_factors, score_outcome_probs


@pytest.fixture
def fixtures_df():
    return load_wc_fixtures()


def test_sigmoid_bounds():
    assert 0.0 < sigmoid(-10) < 0.001
    assert 0.999 < sigmoid(10) < 1.0
    assert math.isclose(sigmoid(0), 0.5, rel_tol=1e-9)


def test_sigmoid_matches_elo_form():
    rating_a, rating_b = 1600.0, 1500.0
    classic = 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))
    assert math.isclose(sigmoid((rating_a - rating_b) / 400.0 * math.log(10)), classic, rel_tol=1e-9)


def test_softmax_sums_to_one():
    probs = softmax([1.0, 2.0, 0.5])
    assert math.isclose(sum(probs), 1.0, rel_tol=1e-9)


def test_goal_model_factors(fixtures_df):
    if fixtures_df.empty:
        return
    row = fixtures_df.iloc[0]
    factors = goal_model_factors(
        fixtures_df,
        row["home_team"],
        row["away_team"],
        before_date=row["match_date"],
        rho=-0.1,
    )
    d = factors.as_dict()
    assert d["lambda_home"] > 0
    assert d["lambda_away"] > 0
    assert d["home_attack"] > 0
    assert d["rho"] == -0.1


def test_rho_changes_draw_rate():
    lam_h, lam_a = 1.1, 1.0
    indep = score_outcome_probs(lam_h, lam_a, rho=0.0)
    corrected = score_outcome_probs(lam_h, lam_a, rho=-0.1)
    assert corrected.prob_draw != indep.prob_draw
