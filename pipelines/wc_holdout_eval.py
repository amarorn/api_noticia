"""Avaliação hold-out do ensemble WC (matriz de confusão para MLflow)."""
from __future__ import annotations

from dataclasses import asdict, dataclass


def _label_from_score(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "1"
    if home_score == away_score:
        return "X"
    return "2"


@dataclass
class WcHoldoutEval:
    validation_season: int
    n_samples: int
    accuracy: float
    labels: list[str]
    confusion_matrix: list[list[int]]

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_wc_holdout(
    predictor,
    *,
    validation_season: int = 2022,
) -> WcHoldoutEval | None:
    """Palpite final (ensemble calibrado) vs resultado real no holdout."""
    from pipelines.wc_holdout import wc_holdout_test_df

    holdout_df = wc_holdout_test_df(predictor.fixtures, validation_season)
    if holdout_df.empty:
        return None

    labels_order = ["1", "X", "2"]
    index = {label: i for i, label in enumerate(labels_order)}
    matrix = [[0 for _ in labels_order] for _ in labels_order]
    correct = 0
    total = 0

    for _, row in holdout_df.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        match_date = row["match_date"]
        phase = row.get("phase", "group")
        season = int(row["season"]) if row.get("season") is not None else None
        group_name = row.get("group")

        actual = _label_from_score(int(row["home_score"]), int(row["away_score"]))
        try:
            pred = predictor.predict(
                home,
                away,
                phase=phase,
                is_neutral=True,
                before_date=match_date,
                season=season,
                group_name=group_name,
            ).prediction
        except Exception:
            continue

        total += 1
        if pred == actual:
            correct += 1
        matrix[index[actual]][index[pred]] += 1

    if total == 0:
        return None

    return WcHoldoutEval(
        validation_season=validation_season,
        n_samples=total,
        accuracy=round(correct / total, 6),
        labels=labels_order,
        confusion_matrix=matrix,
    )
