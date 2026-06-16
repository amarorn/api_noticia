"""Testes do histórico de benchmark de modelos."""
from __future__ import annotations

import json

from pipelines.model_benchmark_history import (
    _build_snapshot,
    append_snapshot,
    history_with_deltas,
    load_history,
    seed_history,
)


def test_build_snapshot_minimal():
    snap = _build_snapshot(
        source="test",
        wc_report={
            "eval_season": 2022,
            "eval_samples": 64,
            "metrics": [
                {"model": "ensemble_blend_linear", "accuracy": 0.57, "brier": 0.183, "log_loss": 0.94}
            ],
        },
        inplay_report={
            "live_ticks": {
                "brier_modelo": 0.078,
                "brier_mercado": 0.108,
                "delta_brier": -0.03,
                "accuracy_modelo": 0.85,
                "n_events": 39,
                "n_ticks": 905,
            }
        },
        walkforward_report={
            "editions_evaluated": 6,
            "summary": {"mean_accuracy": 0.597, "mean_brier": 0.173},
        },
        manifest={
            "created_at": "2026-06-12T05:46:10+00:00",
            "fixture_rows": 9176,
            "training_metrics": {"holdout_accuracy": 0.609375},
            "collab_metrics": {"brier_score": 0.182},
            "ensemble_weights": {"dixon_coles": 0.0, "logistic": 1.0},
        },
        timestamp="2026-06-12T12:00:00+00:00",
    )
    assert snap["source"] == "test"
    assert snap["metrics"]["wc_pregame"]["benchmark_brier"] == 0.183
    assert snap["metrics"]["inplay"]["live_brier_modelo"] == 0.078


def test_append_and_deltas(tmp_path, monkeypatch):
    history_file = tmp_path / "history.json"
    latest_file = tmp_path / "latest.json"
    monkeypatch.setattr(
        "pipelines.model_benchmark_history.HISTORY_PATH",
        history_file,
    )
    monkeypatch.setattr(
        "pipelines.model_benchmark_history.LATEST_PATH",
        latest_file,
    )

    s1 = _build_snapshot(
        source="test",
        inplay_report={"live_ticks": {"brier_modelo": 0.10}},
        timestamp="2026-06-10T12:00:00+00:00",
    )
    s2 = _build_snapshot(
        source="test",
        inplay_report={"live_ticks": {"brier_modelo": 0.08}},
        timestamp="2026-06-12T12:00:00+00:00",
    )
    append_snapshot(s1)
    append_snapshot(s2)

    payload = history_with_deltas()
    assert len(payload["snapshots"]) == 2
    assert payload["snapshots"][1]["deltas"]["inplay.live_brier_modelo"] == -0.02


def test_seed_history_idempotent(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    reports.mkdir()
    full = reports / "full_improvement_test.json"
    full.write_text(
        json.dumps(
            {
                "finished_at": "2026-06-12T12:15:31+00:00",
                "steps": {
                    "train_wc": {"holdout_accuracy": 0.61, "ensemble_brier": 0.18},
                    "walkforward_wc": {"summary": {"mean_accuracy": 0.59, "mean_brier": 0.17}},
                },
                "benchmark": {"live_ticks": {"brier_modelo": 0.078}},
            }
        ),
        encoding="utf-8",
    )
    history_file = reports / "model_benchmark_history.json"
    monkeypatch.setattr("pipelines.model_benchmark_history.HISTORY_PATH", history_file)
    monkeypatch.setattr(
        "pipelines.model_benchmark_history.LATEST_PATH",
        reports / "model_benchmark_latest.json",
    )
    monkeypatch.setattr("pipelines.model_benchmark_history.settings.lake_root", tmp_path)

    seed_history(force=True)
    h1 = load_history()
    seed_history(force=False)
    h2 = load_history()
    assert len(h1["snapshots"]) >= 1
    assert len(h2["snapshots"]) == len(h1["snapshots"])
