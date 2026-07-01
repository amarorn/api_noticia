"""Testes de seleção de modelo WC e backfill MLflow."""
from __future__ import annotations

import json

import pytest

from models.wc_model_selection import (
    build_implementable_leaderboard,
    pick_best_implementable_model,
    resolve_blend_weights,
    save_model_selection,
)


@pytest.fixture
def manifest_sample() -> dict:
    return {
        "created_at": "2026-06-15T05:28:44+00:00",
        "collab_metrics": {
            "accuracy": 0.578,
            "brier_score": 0.1832,
            "log_loss": 0.934,
        },
        "training_metrics": {"holdout_accuracy": 0.594},
        "ensemble_weights": {"dixon_coles": 0.0, "logistic": 1.0},
    }


@pytest.fixture
def wc_report_sample() -> dict:
    return {
        "eval_season": 2022,
        "metrics": [
            {"model": "poisson", "accuracy": 0.565, "brier": 0.1944, "log_loss": 1.12},
            {"model": "logistic", "accuracy": 0.507, "brier": 0.2006, "log_loss": 1.02},
            {
                "model": "ensemble_blend_linear",
                "accuracy": 0.564,
                "brier": 0.1831,
                "log_loss": 0.939,
                "weights": {"poisson": 0.5, "logistic": 0.0, "gb_cal": 0.5},
            },
        ],
    }


def test_leaderboard_prefers_lowest_brier(manifest_sample, wc_report_sample):
    board = build_implementable_leaderboard(
        manifest=manifest_sample,
        wc_report=wc_report_sample,
    )
    assert len(board) == 3
    assert board[0]["model"] == "artifact_ensemble"
    assert board[0]["rank"] == 1


def test_pick_best_returns_blend_weights(manifest_sample, wc_report_sample):
    best = pick_best_implementable_model(
        build_implementable_leaderboard(
            manifest=manifest_sample,
            wc_report=wc_report_sample,
        )
    )
    assert best["model"] == "artifact_ensemble"
    assert best["blend_weights"]["logistic"] == 1.0


def test_resolve_blend_auto_uses_selection(tmp_path, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "lake_root", tmp_path)
    monkeypatch.setattr(settings, "wc_model_selection_mode", "auto")

    sel_dir = tmp_path / "artifacts"
    sel_dir.mkdir(parents=True)
    payload = {
        "selected_model": "poisson",
        "blend_weights": {"dixon_coles": 1.0, "logistic": 0.0},
    }
    (sel_dir / "model_selection.json").write_text(json.dumps(payload), encoding="utf-8")

    dc, lg, meta = resolve_blend_weights(0.0, 1.0)
    assert dc == 1.0
    assert lg == 0.0
    assert meta["selected_model"] == "poisson"


def test_save_model_selection_writes_file(tmp_path, monkeypatch, manifest_sample, wc_report_sample):
    from config import settings

    monkeypatch.setattr(settings, "lake_root", tmp_path)
    monkeypatch.setattr(settings, "wc_artifact_dir", tmp_path / "artifacts" / "wc_predictor")
    settings.wc_artifact_dir.mkdir(parents=True)
    (settings.wc_artifact_dir / "manifest.json").write_text(
        json.dumps(manifest_sample), encoding="utf-8"
    )
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "wc_benchmark_report.json").write_text(
        json.dumps(wc_report_sample), encoding="utf-8"
    )

    out = save_model_selection(
        leaderboard=build_implementable_leaderboard(
            manifest=manifest_sample,
            wc_report=wc_report_sample,
        )
    )
    path = tmp_path / "artifacts" / "model_selection.json"
    assert path.exists()
    assert out["selected_model"] == "artifact_ensemble"


def test_registry_api(tmp_path, monkeypatch, manifest_sample, wc_report_sample):
    from fastapi.testclient import TestClient

    from api.main import app
    from config import settings

    monkeypatch.setattr(settings, "lake_root", tmp_path)
    monkeypatch.setattr(settings, "wc_artifact_dir", tmp_path / "artifacts" / "wc_predictor")
    monkeypatch.setattr(settings, "api_key", None)
    settings.wc_artifact_dir.mkdir(parents=True)
    (settings.wc_artifact_dir / "manifest.json").write_text(
        json.dumps(manifest_sample), encoding="utf-8"
    )
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "wc_benchmark_report.json").write_text(
        json.dumps(wc_report_sample), encoding="utf-8"
    )
    save_model_selection(
        leaderboard=build_implementable_leaderboard(
            manifest=manifest_sample,
            wc_report=wc_report_sample,
        )
    )

    client = TestClient(app)
    resp = client.get("/worldcup/models/registry")
    assert resp.status_code == 200
    data = resp.json()
    assert data["selection_mode"] in ("auto", "ensemble")
    assert len(data["leaderboard"]) >= 2
    assert data["active_selection"]["selected_model"] == "artifact_ensemble"
