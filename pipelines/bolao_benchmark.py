from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from config import settings
from ingest.fixtures.store import load_fixtures
from models.baseline import predict_baseline_probs
from models.eval_metrics import LABELS, classification_metrics
from pipelines.bolao_features import FEATURE_NAMES, build_bolao_feature, features_to_array

BRASILEIRAO = "Brasileirão"


def _filter_brasileirao(fixtures: pd.DataFrame) -> pd.DataFrame:
    if fixtures.empty:
        return fixtures
    if "competition" in fixtures.columns:
        return fixtures[fixtures["competition"] == BRASILEIRAO].copy()
    return fixtures


def _row_to_feature(
    fixtures: pd.DataFrame,
    row: pd.Series,
    history: pd.DataFrame,
) -> BolaoFeature:
    match_date = pd.to_datetime(row["match_date"], utc=True).to_pydatetime()
    return build_bolao_feature(
        history,
        row["home_team"],
        row["away_team"],
        match_date,
        int(row["round_number"]),
        row.get("competition", BRASILEIRAO),
        str(row["match_id"]),
        season=int(row["season"]) if pd.notna(row.get("season")) else None,
    )


def run_benchmark(eval_season: int = 2024, enable_mlflow: bool = False) -> dict:
    fixtures = _filter_brasileirao(load_fixtures())
    if fixtures.empty:
        raise ValueError("Sem fixtures do Brasileirão. Execute: import-fixtures --competition brasileirao")

    df = fixtures.sort_values("match_date").copy()
    df["match_date"] = pd.to_datetime(df["match_date"], utc=True)
    eval_df = df[df["season"] == eval_season]
    if len(eval_df) < 20:
        raise ValueError(f"Poucos jogos na temporada {eval_season}: {len(eval_df)}")

    eval_features: list = []
    y_eval: list[str] = []

    for _, row in eval_df.iterrows():
        history = df[df["match_date"] < row["match_date"]]
        if len(history) < 10:
            continue
        feat = _row_to_feature(df, row, history)
        eval_features.append(feat)
        y_eval.append(str(row["label"]))

    if len(y_eval) < 20:
        raise ValueError(f"Poucas amostras com histórico para {eval_season}: {len(y_eval)}")

    train_features: list = []
    y_train: list[str] = []
    train_df = df[df["season"] < eval_season]
    for _, row in train_df.iterrows():
        history = df[df["match_date"] < row["match_date"]]
        if len(history) < 10:
            continue
        train_features.append(_row_to_feature(df, row, history))
        y_train.append(str(row["label"]))

    probs_baseline = np.array(
        [[predict_baseline_probs(f)[c] for c in LABELS] for f in eval_features]
    )
    m_baseline = classification_metrics(y_eval, probs_baseline)
    m_baseline["model"] = "baseline_heuristic"

    x_train = features_to_array(train_features)
    x_eval = features_to_array(eval_features)
    scaler = StandardScaler()
    x_train_sc = scaler.fit_transform(x_train)
    x_eval_sc = scaler.transform(x_eval)

    def _align_proba(model, x: np.ndarray) -> np.ndarray:
        raw = model.predict_proba(x)
        aligned = np.zeros((len(x), len(LABELS)))
        for j, cls in enumerate(model.classes_):
            aligned[:, list(LABELS).index(cls)] = raw[:, j]
        return aligned

    log_model = LogisticRegression(max_iter=2000, solver="lbfgs", random_state=42)
    log_model.fit(x_train_sc, y_train)
    probs_log = _align_proba(log_model, x_eval_sc)
    m_log = classification_metrics(y_eval, probs_log)
    m_log["model"] = "logistic_stats"

    gb = GradientBoostingClassifier(random_state=42)
    gb.fit(x_train, y_train)
    gb_cal = CalibratedClassifierCV(gb, cv=3, method="isotonic")
    gb_cal.fit(x_train, y_train)
    probs_gb_cal = _align_proba(gb_cal, x_eval)
    m_gb = classification_metrics(y_eval, probs_gb_cal)
    m_gb["model"] = "gradient_boosting_calibrated"

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "competition": BRASILEIRAO,
        "eval_season": eval_season,
        "train_samples": len(y_train),
        "eval_samples": len(y_eval),
        "feature_names": FEATURE_NAMES,
        "metrics": [m_baseline, m_log, m_gb],
    }

    if enable_mlflow:
        try:
            import mlflow

            with mlflow.start_run(run_name=f"brasileirao-benchmark-{eval_season}"):
                mlflow.log_param("eval_season", eval_season)
                for m in report["metrics"]:
                    prefix = m["model"]
                    mlflow.log_metric(f"{prefix}_accuracy", m["accuracy"])
                    mlflow.log_metric(f"{prefix}_brier", m["brier"])
                    mlflow.log_metric(f"{prefix}_log_loss", m["log_loss"])
        except Exception as exc:
            report["mlflow_warning"] = str(exc)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark temporal Brasileirão (sem vazamento)")
    parser.add_argument("--eval-season", type=int, default=2024)
    parser.add_argument("--mlflow", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=settings.lake_root / "reports" / "brasileirao_benchmark_report.json",
    )
    args = parser.parse_args()

    report = run_benchmark(eval_season=args.eval_season, enable_mlflow=args.mlflow)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    best = min(report["metrics"], key=lambda m: m["brier"])
    print(f"Relatório: {args.output}")
    print(
        f"Melhor (brier): {best['model']} | acc={best['accuracy']:.3f} "
        f"brier={best['brier']:.4f} logloss={best['log_loss']:.4f}"
    )


if __name__ == "__main__":
    main()
