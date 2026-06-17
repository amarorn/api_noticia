"""Testes de rotas principais em api/main.py (smoke)."""
from __future__ import annotations

import json

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


def test_worldcup_superbet_postmortem_endpoint(monkeypatch, tmp_path):
    from config import settings

    event_id = 11499882
    event_dir = tmp_path / "gold" / "superbet" / "events" / str(event_id)
    event_dir.mkdir(parents=True)
    report = {
        "event_id": event_id,
        "home_team": "Bélgica",
        "away_team": "Egito",
        "final_score": "1x1",
        "ht_score": "0x1",
        "n_ticks": 10,
        "tip_summary": {
            "total_ticks_with_tip": 5,
            "unique_tips": 2,
            "won": 1,
            "lost": 1,
            "unknown": 0,
        },
        "tips_by_market": [],
        "model_timeline": [],
        "issues": [{"code": "bad_2h_away_minus_half", "detail": "teste"}],
    }
    (event_dir / "postmortem.json").write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(settings, "lake_root", tmp_path)

    client = _client(monkeypatch)
    resp = client.get(f"/worldcup/superbet/events/{event_id}/postmortem")
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_id"] == event_id
    assert data["tip_summary"]["won"] == 1
    assert data["issues"][0]["code"] == "bad_2h_away_minus_half"


def test_worldcup_superbet_postmortem_404(monkeypatch, tmp_path):
    from config import settings

    monkeypatch.setattr(settings, "lake_root", tmp_path)
    client = _client(monkeypatch)
    resp = client.get("/worldcup/superbet/events/999999/postmortem")
    assert resp.status_code == 404


def test_worldcup_superbet_validate_builder(monkeypatch):
    client = _client(monkeypatch)
    resp = client.post(
        "/worldcup/superbet/validate-builder",
        json={
            "legs": [
                {"market": "1h_over_1_5", "outcome": "yes", "label": "Over 1.5 1T"},
                {"market": "h2h", "outcome": "1", "label": "Casa"},
            ],
            "minute": 45,
            "home_score": 1,
            "away_score": 0,
            "combined_odd": 7.5,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert data["legs_count"] == 2
    codes = {e.get("code") for e in data["errors"]} | {w.get("code") for w in data["warnings"]}
    assert "ht_over_dead" in codes
    assert len(data["bet_builder_rules"]) >= 3
