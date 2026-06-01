from models.ev_value import evaluate_match


def test_selects_positive_ev_as_best() -> None:
    report = evaluate_match(
        home_team="Brasil",
        away_team="Marrocos",
        probabilities={"1": 0.58, "X": 0.27, "2": 0.15},
        odds={"1": 2.00, "X": 3.20, "2": 5.10},
        min_edge=0.03,
    )
    assert report.best is not None
    assert report.best.outcome == "1"
    assert report.best.expected_value > 0.03


def test_no_bet_when_all_edges_negative() -> None:
    report = evaluate_match(
        home_team="Brasil",
        away_team="Marrocos",
        probabilities={"1": 0.45, "X": 0.30, "2": 0.25},
        odds={"1": 1.80, "X": 2.90, "2": 3.30},
        min_edge=0.01,
    )
    assert report.best is None
