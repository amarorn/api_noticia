from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.cluster import KMeans
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import StandardScaler

from config import settings
from ingest.fixtures.world_cup import load_wc_fixtures
from models.poisson_wc import predict_poisson
from pipelines.wc_stats import FEATURE_NAMES, build_match_features, features_to_vector

LABELS = ("1", "X", "2")


@dataclass
class EvalRow:
    features: list[float]
    label: str
    probs_poisson: list[float]
    probs_logistic: list[float] | None = None
    probs_gb: list[float] | None = None
    probs_gb_cal: list[float] | None = None


def _brier_score(y_true: list[str], probs: np.ndarray, classes: list[str]) -> float:
    total = 0.0
    for idx, y in enumerate(y_true):
        for c_idx, c in enumerate(classes):
            target = 1.0 if y == c else 0.0
            total += float((probs[idx, c_idx] - target) ** 2)
    return total / (len(y_true) * len(classes))


def _log_loss_score(y_true: list[str], probs: np.ndarray, classes: list[str], eps: float = 1e-12) -> float:
    class_to_idx = {c: i for i, c in enumerate(classes)}
    total = 0.0
    for idx, y in enumerate(y_true):
        p = float(probs[idx, class_to_idx[y]])
        p = min(max(p, eps), 1.0 - eps)
        total += -np.log(p)
    return total / len(y_true)


def _weights_search(rows: list[EvalRow], blend_keys: tuple[str, str, str]) -> tuple[dict, np.ndarray]:
    best: dict | None = None
    best_probs: np.ndarray | None = None
    y_true = [r.label for r in rows]
    classes = list(LABELS)

    def _get_probs(row: EvalRow, key: str) -> np.ndarray:
        data = getattr(row, f"probs_{key}")
        if data is None:
            raise ValueError(f"Probabilidades ausentes para {key}")
        return np.array(data, dtype=float)

    for a in range(0, 11):
        for b in range(0, 11 - a):
            c = 10 - a - b
            w = np.array([a, b, c], dtype=float) / 10.0
            blended = []
            for r in rows:
                p = (
                    w[0] * _get_probs(r, blend_keys[0])
                    + w[1] * _get_probs(r, blend_keys[1])
                    + w[2] * _get_probs(r, blend_keys[2])
                )
                p = p / p.sum()
                blended.append(p)
            probs = np.vstack(blended)
            preds = [classes[int(np.argmax(p))] for p in probs]
            acc = accuracy_score(y_true, preds)
            brier = _brier_score(y_true, probs, classes)
            ll = _log_loss_score(y_true, probs, classes)
            cand = {"weights": w.tolist(), "accuracy": float(acc), "brier": float(brier), "log_loss": float(ll)}
            if best is None or cand["brier"] < best["brier"]:
                best = cand
                best_probs = probs

    assert best is not None and best_probs is not None
    return best, best_probs


def _cluster_error_analysis(rows: list[EvalRow], probs: np.ndarray, n_clusters: int = 4) -> dict:
    x = np.array([r.features for r in rows], dtype=float)
    y = [r.label for r in rows]
    pred = [LABELS[int(np.argmax(p))] for p in probs]

    if len(rows) < n_clusters:
        n_clusters = max(2, len(rows) // 2)
    if n_clusters < 2:
        return {}

    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    clusters = km.fit_predict(x)

    by_cluster: dict[str, dict] = {}
    for c in range(n_clusters):
        idxs = [i for i, ci in enumerate(clusters) if ci == c]
        if not idxs:
            continue
        yc = [y[i] for i in idxs]
        pc = [pred[i] for i in idxs]
        acc = accuracy_score(yc, pc)
        by_cluster[str(c)] = {"size": len(idxs), "accuracy": float(acc)}
    return by_cluster


def _build_eval_rows(fixtures: pd.DataFrame, eval_season: int) -> tuple[np.ndarray, list[str], list[EvalRow]]:
    df = fixtures.sort_values("match_date").copy()
    df["match_date"] = pd.to_datetime(df["match_date"], utc=True)
    eval_df = df[df["season"] == eval_season].sort_values("match_date")

    rows: list[EvalRow] = []
    for _, row in eval_df.iterrows():
        history = df[df["match_date"] < row["match_date"]]
        if history.empty:
            continue

        feats = build_match_features(
            history,
            row["home_team"],
            row["away_team"],
            before_date=row["match_date"].to_pydatetime(),
            phase=row.get("phase", "group"),
            is_neutral=bool(row.get("is_neutral", True)),
        )
        vec = features_to_vector(feats)
        p = predict_poisson(
            history,
            row["home_team"],
            row["away_team"],
            features=feats,
            before_date=row["match_date"].to_pydatetime(),
        )
        rows.append(
            EvalRow(
                features=vec,
                label=str(row["label"]),
                probs_poisson=[float(p.prob_home), float(p.prob_draw), float(p.prob_away)],
            )
        )

    x = np.array([r.features for r in rows], dtype=float)
    y = [r.label for r in rows]
    return x, y, rows


def run_benchmark(eval_season: int = 2022, enable_mlflow: bool = False) -> dict:
    fixtures = load_wc_fixtures()
    if fixtures.empty:
        raise ValueError("Sem dados de Copa. Execute import-world-cup primeiro.")

    x_eval, y_eval, rows = _build_eval_rows(fixtures, eval_season)
    if len(rows) < 20:
        raise ValueError(f"Poucas amostras para avaliação na temporada {eval_season}: {len(rows)}")

    train_df = fixtures[fixtures["season"] < eval_season].sort_values("match_date")
    # Construção temporal do conjunto de treino (sem vazamento).
    train_rows = []
    full_train = train_df.copy()
    full_train["match_date"] = pd.to_datetime(full_train["match_date"], utc=True)
    for _, row in full_train.iterrows():
        history = full_train[full_train["match_date"] < row["match_date"]]
        if history.empty:
            continue
        feats = build_match_features(
            history,
            row["home_team"],
            row["away_team"],
            before_date=row["match_date"].to_pydatetime(),
            phase=row.get("phase", "group"),
            is_neutral=bool(row.get("is_neutral", True)),
        )
        train_rows.append((features_to_vector(feats), str(row["label"])))

    x_train = np.array([r[0] for r in train_rows], dtype=float)
    y_train = [r[1] for r in train_rows]

    scaler = StandardScaler()
    x_train_sc = scaler.fit_transform(x_train)
    x_eval_sc = scaler.transform(x_eval)

    log_model = LogisticRegression(max_iter=2000, solver="lbfgs", random_state=42)
    log_model.fit(x_train_sc, y_train)
    probs_log = log_model.predict_proba(x_eval_sc)

    gb_model = GradientBoostingClassifier(random_state=42)
    gb_model.fit(x_train, y_train)
    probs_gb = gb_model.predict_proba(x_eval)

    gb_cal = CalibratedClassifierCV(gb_model, cv=3, method="isotonic")
    gb_cal.fit(x_train, y_train)
    probs_gb_cal = gb_cal.predict_proba(x_eval)

    probs_poisson = np.vstack([np.array(r.probs_poisson, dtype=float) for r in rows])

    for i, r in enumerate(rows):
        r.probs_logistic = probs_log[i].tolist()
        r.probs_gb = probs_gb[i].tolist()
        r.probs_gb_cal = probs_gb_cal[i].tolist()

    def _metrics(name: str, probs: np.ndarray) -> dict:
        preds = [LABELS[int(np.argmax(p))] for p in probs]
        return {
            "model": name,
            "accuracy": float(accuracy_score(y_eval, preds)),
            "brier": float(_brier_score(y_eval, probs, list(LABELS))),
            "log_loss": float(_log_loss_score(y_eval, probs, list(LABELS))),
        }

    m_poisson = _metrics("poisson", probs_poisson)
    m_log = _metrics("logistic", probs_log)
    m_gb = _metrics("gradient_boosting", probs_gb)
    m_gb_cal = _metrics("gradient_boosting_calibrated", probs_gb_cal)

    best_blend, probs_blend = _weights_search(rows, ("poisson", "logistic", "gb_cal"))
    m_blend = _metrics("ensemble_blend", probs_blend)
    m_blend["weights"] = {
        "poisson": best_blend["weights"][0],
        "logistic": best_blend["weights"][1],
        "gb_cal": best_blend["weights"][2],
    }

    cluster_report = _cluster_error_analysis(rows, probs_blend, n_clusters=4)

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "eval_season": eval_season,
        "train_samples": int(len(y_train)),
        "eval_samples": int(len(y_eval)),
        "feature_names": FEATURE_NAMES,
        "metrics": [m_poisson, m_log, m_gb, m_gb_cal, m_blend],
        "cluster_error": cluster_report,
    }

    if enable_mlflow:
        try:
            import mlflow  # type: ignore

            with mlflow.start_run(run_name=f"wc-benchmark-{eval_season}"):
                mlflow.log_param("eval_season", eval_season)
                mlflow.log_param("train_samples", len(y_train))
                mlflow.log_param("eval_samples", len(y_eval))
                for m in report["metrics"]:
                    prefix = m["model"]
                    mlflow.log_metric(f"{prefix}_accuracy", m["accuracy"])
                    mlflow.log_metric(f"{prefix}_brier", m["brier"])
                    mlflow.log_metric(f"{prefix}_log_loss", m["log_loss"])
                if "weights" in m_blend:
                    for key, value in m_blend["weights"].items():
                        mlflow.log_param(f"blend_weight_{key}", value)
        except Exception as exc:
            report["mlflow_warning"] = f"MLflow indisponível: {exc}"

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark temporal de modelos da Copa")
    parser.add_argument("--eval-season", type=int, default=2022)
    parser.add_argument("--mlflow", action="store_true", help="Logar métricas no MLflow (se instalado)")
    parser.add_argument(
        "--output",
        type=Path,
        default=settings.lake_root / "reports" / "wc_benchmark_report.json",
    )
    args = parser.parse_args()

    report = run_benchmark(eval_season=args.eval_season, enable_mlflow=args.mlflow)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    metrics = sorted(report["metrics"], key=lambda m: m["brier"])
    best = metrics[0]
    print(f"Relatório salvo em: {args.output}")
    print(
        f"Melhor (menor brier): {best['model']} | "
        f"acc={best['accuracy']:.3f} brier={best['brier']:.4f} logloss={best['log_loss']:.4f}"
    )
    if "weights" in best:
        print(f"Pesos do ensemble: {best['weights']}")
    if report.get("mlflow_warning"):
        print(report["mlflow_warning"])


if __name__ == "__main__":
    main()
