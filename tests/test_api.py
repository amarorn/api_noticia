import json

import api.wc_round_cache as wc_round_cache
from fastapi.testclient import TestClient

from api.main import app
from api.wc_round_cache import (
    artifact_fingerprint,
    get_cached,
    invalidate_wc_round_cache,
    match_key,
    persist_to_disk,
    set_cached,
    warm_from_disk,
)

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_lists_endpoints():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "endpoints" in body


def test_predict_single_build():
    response = client.post(
        "/predict",
        json={
            "home_team": "Flamengo",
            "away_team": "Palmeiras",
            "round_number": 1,
            "competition": "Brasileirão",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["prediction"] in ("1", "X", "2")
    assert data["home_team"] == "Flamengo"
    assert data["model_source"] == "baseline"
    assert set(data["probabilities"].keys()) == {"1", "X", "2"}
    assert abs(sum(data["probabilities"].values()) - 1.0) < 0.01


def test_wc_round_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("api.wc_round_cache.settings.lake_root", tmp_path)
    invalidate_wc_round_cache()

    sample = {
        "home_team": "Brasil",
        "away_team": "Marrocos",
        "prediction": "1",
        "confidence": 0.55,
        "prob_home": 0.55,
        "prob_draw": 0.25,
        "prob_away": 0.2,
        "poisson_score": "2-1",
        "expected_goals": "2.1 - 0.9",
        "context": "test",
        "h2h_summary": "test",
        "model_breakdown": {
            "dixon_coles": {"1": 0.5, "X": 0.25, "2": 0.25},
            "logistic": {"1": 0.5, "X": 0.25, "2": 0.25},
            "ensemble_weights": {"dixon_coles": 0.5, "logistic": 0.5},
        },
    }
    key = match_key("Brasil", "Marrocos", "group")
    set_cached(key, sample)
    persist_to_disk()

    wc_round_cache._memory.clear()
    wc_round_cache._disk_loaded = False
    assert len(wc_round_cache._memory) == 0

    loaded = warm_from_disk()
    assert loaded == 1
    assert get_cached(key)["home_team"] == "Brasil"

    cache_file = tmp_path / "cache" / "wc_round_predictions.json"
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    assert payload["artifact_fingerprint"] == artifact_fingerprint()


def test_worldcup_round_matchday_filter():
    response = client.get("/worldcup/round?round=1")
    if response.status_code == 503:
        return
    assert response.status_code == 200
    data = response.json()
    assert data["round"] == 1
    assert 20 <= len(data["predictions"]) <= 28

    full = client.get("/worldcup/round")
    assert full.status_code == 200
    assert len(full.json()["predictions"]) >= len(data["predictions"])
