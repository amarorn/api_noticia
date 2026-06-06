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


def test_worldcup_predict_with_sofascore_event_id(monkeypatch):
    from schemas.wc_kxl_dynamic import FeptEscalacao, FeptTitularesEstruturados, WcKxlMatchInput

    fake_fept = FeptEscalacao(
        esquema_mandante="4-2-3-1",
        mandante_titulares_notas=FeptTitularesEstruturados(
            goleiro={"nome": "Alisson", "nota_sofascore": 7.0},
        ),
    )

    def fake_merge(**_kwargs):
        return (
            WcKxlMatchInput(fept=fake_fept),
            {
                "source": "sofascore",
                "event_id": 11774480,
                "ratings_found": 11,
                "ratings_missing": 0,
                "auto_merged": True,
            },
        )

    class FakePred:
        home_team = "Brasil"
        away_team = "Argentina"
        prediction = "1"
        confidence = 0.55
        prob_home = 0.55
        prob_draw = 0.25
        prob_away = 0.2
        poisson_score = "2-1"
        expected_goals = "2.1x0.9"
        context = "ctx"
        h2h_summary = "h2h"
        model_breakdown = {
            "dixon_coles": {"1": 0.5, "X": 0.25, "2": 0.25},
            "logistic": {"1": 0.5, "X": 0.25, "2": 0.25},
            "ensemble_weights": {"dixon_coles": 0.5, "logistic": 0.5},
        }

    class FakePredictor:
        def predict(self, *_args, **kwargs):
            assert kwargs.get("kxl_match") is not None
            assert kwargs["kxl_match"].fept is not None
            return FakePred()

    monkeypatch.setattr("ingest.sofascore.kxl_merge.merge_sofascore_fept", fake_merge)
    monkeypatch.setattr("api.main._get_wc_predictor", lambda: FakePredictor())
    monkeypatch.setattr("api.main.official_match_exists", lambda *_a, **_k: True)

    response = client.post(
        "/worldcup/predict",
        json={
            "home_team": "Brasil",
            "away_team": "Argentina",
            "phase": "group",
            "sofascore_event_id": 11774480,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["model_breakdown"]["kxl_fept"]["event_id"] == 11774480
    assert data["model_breakdown"]["kxl_fept"]["auto_merged"] is True


def test_worldcup_corners_predict_endpoint(monkeypatch):
    monkeypatch.setattr("config.settings.api_key", None)

    from types import SimpleNamespace

    class FakeFactors:
        def as_dict(self):
            return {
                "league_avg": 5.0,
                "home_attack": 1.1,
                "away_attack": 0.9,
                "home_defense": 1.0,
                "away_defense": 1.0,
                "home_advantage": 0.15,
                "elo_factor_home": 1.0,
                "elo_factor_away": 1.0,
                "lambda_home": 5.8,
                "lambda_away": 4.2,
                "training_matches": 12,
                "blend_with_goal_proxy": 0.0,
            }

    class FakeCornersPred:
        prediction = SimpleNamespace(
            expected_home_corners=5.8,
            expected_away_corners=4.2,
            expected_total_corners=10.0,
            most_likely_score="6x4",
            prob_home_more=0.55,
            prob_draw_corners=0.18,
            prob_away_more=0.27,
            line_probs={"over_9.5": 0.52, "under_9.5": 0.48},
        )
        factors = FakeFactors()
        home_team = "Brasil"
        away_team = "Argentina"
        data_source = "sofascore_corners"
        training_summary = {"matches": 12, "teams": 8}

    class FakePredictor:
        def predict(self, *_args, **_kwargs):
            return FakeCornersPred()

    monkeypatch.setattr("api.main.CornersPredictor", FakePredictor)
    monkeypatch.setattr("api.main.official_match_exists", lambda *_a, **_k: True)

    response = client.post(
        "/worldcup/corners/predict",
        json={"home_team": "Brasil", "away_team": "Argentina", "phase": "group"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["expected_total_corners"] == 10.0
    assert data["line_probs"]["over_9.5"] == 0.52


def test_worldcup_sofascore_statistics_endpoint(monkeypatch):
    from ingest.sofascore.stats_ingest import MatchStatsIngestResult

    monkeypatch.setattr("config.settings.api_key", None)

    def fake_ingest(**_kwargs):
        return MatchStatsIngestResult(
            event_id=99,
            home_team="Brasil",
            away_team="Argentina",
            match_date="2026-06-10",
            stats={
                "home_corners": 7,
                "away_corners": 3,
                "home_possession_pct": 58.0,
            },
            json_path=None,
            parquet_path=None,
        )

    monkeypatch.setattr("ingest.sofascore.stats_ingest.ingest_match_stats", fake_ingest)
    response = client.get("/worldcup/sofascore/99/statistics?refresh=true")
    assert response.status_code == 200
    data = response.json()
    assert data["event_id"] == 99
    assert data["stats"]["home_corners"] == 7
    assert data["cached"] is False


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
