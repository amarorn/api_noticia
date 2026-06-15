"""Testes de rotas principais em api/main.py (smoke)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _client(monkeypatch) -> TestClient:
    monkeypatch.setattr("config.settings.api_key", None)
    from api.main import app

    return TestClient(app)


def test_health_live(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"


def test_worldcup_models_registry(monkeypatch, tmp_path):
    from config import settings

    monkeypatch.setattr(settings, "lake_root", tmp_path)
    monkeypatch.setattr(settings, "wc_artifact_dir", tmp_path / "artifacts" / "wc_predictor")
    settings.wc_artifact_dir.mkdir(parents=True)
    (settings.wc_artifact_dir / "manifest.json").write_text(
        '{"collab_metrics":{"brier_score":0.18,"accuracy":0.57},"ensemble_weights":{"dixon_coles":0,"logistic":1}}',
        encoding="utf-8",
    )
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "wc_benchmark_report.json").write_text(
        '{"metrics":[{"model":"poisson","accuracy":0.56,"brier":0.19,"log_loss":1.1}]}',
        encoding="utf-8",
    )

    client = _client(monkeypatch)
    resp = client.get("/worldcup/models/registry")
    assert resp.status_code == 200
    data = resp.json()
    assert "leaderboard" in data
    assert data["selection_mode"] in ("auto", "ensemble")


def test_worldcup_benchmark_history_404_when_empty(monkeypatch, tmp_path):
    from config import settings

    monkeypatch.setattr(settings, "lake_root", tmp_path)
    client = _client(monkeypatch)
    resp = client.get("/worldcup/benchmark/history")
    assert resp.status_code == 404
