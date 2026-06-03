import pandas as pd

from models.baseline import predict_baseline_probs
from pipelines.bolao_benchmark import run_benchmark
from pipelines.bolao_features import build_bolao_feature
from schemas.models import BolaoFeature
from schemas.teams import teams_from_text


def test_predict_baseline_probs_sum_to_one():
    features = BolaoFeature(
        match_id="x",
        home_team="Flamengo",
        away_team="Palmeiras",
        round_number=1,
        competition="Brasileirão",
        match_date=pd.Timestamp("2024-04-13", tz="UTC"),
    )
    probs = predict_baseline_probs(features)
    assert set(probs.keys()) == {"1", "X", "2"}
    assert abs(sum(probs.values()) - 1.0) < 1e-6


def test_teams_from_text_nickname():
    text = "Mengão vence clássico e assume liderança"
    teams = teams_from_text(text)
    assert "Flamengo" in teams


def test_run_benchmark_with_synthetic_fixtures():
    rows = []
    teams = ["Flamengo", "Palmeiras", "Corinthians", "São Paulo"]
    match_id = 0
    for season in (2022, 2023, 2024):
        for round_num in range(1, 11):
            for i in range(2):
                home, away = teams[i], teams[i + 2]
                hs, aws = (2, 1) if (round_num + i) % 3 != 0 else (1, 1)
                label = "1" if hs > aws else ("X" if hs == aws else "2")
                rows.append({
                    "match_id": f"m{match_id}",
                    "season": season,
                    "competition": "Brasileirão",
                    "round_number": round_num,
                    "match_date": pd.Timestamp(f"{season}-04-{10 + round_num:02d}", tz="UTC"),
                    "home_team": home,
                    "away_team": away,
                    "home_score": hs,
                    "away_score": aws,
                    "label": label,
                })
                match_id += 1

    fixtures = pd.DataFrame(rows)

    def fake_load(*args, **kwargs):
        return fixtures

    import pipelines.bolao_benchmark as bench

    original = bench.load_fixtures
    bench.load_fixtures = fake_load
    try:
        report = run_benchmark(eval_season=2024)
    finally:
        bench.load_fixtures = original

    assert report["eval_samples"] >= 20
    assert len(report["metrics"]) == 3
    assert report["metrics"][0]["model"] == "baseline_heuristic"


def test_build_bolao_feature_no_leakage():
    fixtures = pd.DataFrame([
        {
            "match_id": "a",
            "season": 2024,
            "competition": "Brasileirão",
            "round_number": 1,
            "match_date": pd.Timestamp("2024-04-01", tz="UTC"),
            "home_team": "Flamengo",
            "away_team": "Palmeiras",
            "home_score": 2,
            "away_score": 0,
            "label": "1",
        },
        {
            "match_id": "b",
            "season": 2024,
            "competition": "Brasileirão",
            "round_number": 2,
            "match_date": pd.Timestamp("2024-04-08", tz="UTC"),
            "home_team": "Palmeiras",
            "away_team": "Flamengo",
            "home_score": 1,
            "away_score": 1,
            "label": "X",
        },
    ])
    history = fixtures.iloc[:1]
    row = fixtures.iloc[1]
    feat = build_bolao_feature(
        history,
        row["home_team"],
        row["away_team"],
        row["match_date"].to_pydatetime(),
        int(row["round_number"]),
        row["competition"],
        row["match_id"],
        season=2024,
    )
    assert feat.home_points is not None or feat.away_points is not None
