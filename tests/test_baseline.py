from datetime import datetime, timezone

from models.baseline import predict_baseline
from schemas.models import BolaoFeature


def test_baseline_favors_home_leader():
    features = BolaoFeature(
        match_id="x",
        home_team="Flamengo",
        away_team="Corinthians",
        round_number=1,
        competition="Brasileirão",
        match_date=datetime.now(timezone.utc),
        home_position=1,
        away_position=18,
        home_points=30,
        away_points=10,
        home_form="V-V-V-E-V",
        away_form="D-D-L-D-D",
        h2h_home_wins=3,
        h2h_draws=1,
        h2h_away_wins=0,
    )
    pred, conf, _ = predict_baseline(features)
    assert pred == "1"
    assert conf > 0.3


def test_baseline_returns_valid_label():
    features = BolaoFeature(
        match_id="x",
        home_team="A",
        away_team="B",
        round_number=1,
        competition="Brasileirão",
        match_date=datetime.now(timezone.utc),
    )
    pred, _, _ = predict_baseline(features)
    assert pred in ("1", "X", "2")
