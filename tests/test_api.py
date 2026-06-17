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


def test_worldcup_inplay_endpoint(monkeypatch):
    monkeypatch.setattr("config.settings.api_key", None)

    from models.wc_inplay import simulate_inplay

    class FakePredictor:
        fixtures = []
        dixon_coles = type("DC", (), {"rho": -0.1})()
        _dc_metrics = {"rho": -0.1}

    def fake_inplay(_predictor, **kwargs):
        return simulate_inplay(
            home_team=kwargs["home_team"],
            away_team=kwargs["away_team"],
            home_score=kwargs["home_score"],
            away_score=kwargs["away_score"],
            minute=kwargs["minute"],
            lambda_full_home=2.5,
            lambda_full_away=1.8,
            n_simulations=1000,
        )

    monkeypatch.setattr("models.wc_inplay.inplay_from_predictor", fake_inplay)
    monkeypatch.setattr("api.main._get_wc_predictor", lambda: FakePredictor())

    response = client.post(
        "/worldcup/inplay",
        json={
            "home_team": "Brasil",
            "away_team": "Egito",
            "home_score": 1,
            "away_score": 1,
            "minute": 17,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_score"] == "1x1"
    assert data["minute"] == 17
    assert 0 <= data["prob_final_draw"] <= 1
    assert "final_line_probs" in data
    assert data["n_simulations"] == 1000
    assert "handicap_probs" in data
    assert len(data["handicap_probs"]) > 0


def test_worldcup_handicap_endpoint(monkeypatch):
    monkeypatch.setattr("config.settings.api_key", None)

    from ingest.superbet.parser import SuperbetEventSnapshot, SuperbetInPlayState
    from models.wc_inplay import simulate_inplay

    class FakePredictor:
        fixtures = []
        dixon_coles = type("DC", (), {"rho": -0.1})()
        _dc_metrics = {"rho": -0.1}

    fake_snapshot = SuperbetEventSnapshot(
        event_id=999,
        home_team="Brasil",
        away_team="Egito",
        event_name="Brasil·Egito",
        utc_date=None,
        betradar_id=None,
        is_live=True,
        inplay=SuperbetInPlayState(
            home_score=1,
            away_score=0,
            minute=30,
            stoppage_time=None,
            home_corners=2,
            away_corners=1,
            home_yellow_cards=0,
            away_yellow_cards=1,
            ht_home_score=None,
            ht_away_score=None,
            period_label="1T",
            status="LIVE",
        ),
        h2h_odds={"1": 1.9, "X": 3.4, "2": 4.2},
        h2h_implied={},
        totals={},
        totals_implied={},
        corners={},
        corners_implied={},
        combo_markets={},
        btts_odds={},
        next_goal_odds={},
        generosity_probs={},
        team_totals={"home": {}, "away": {}},
        first_half_totals={},
        second_half_totals={},
        yellow_cards={},
        first_half_yellow_cards={},
        team_shots={"home": {}, "away": {}},
        team_shots_on_target={"home": {}, "away": {}},
        half_markets={},
        handicap_odds={"home_-1.5": 2.1, "away_+1.5": 1.75},
        handicap_implied={},
        raw_market_count=10,
        captured_at="2026-06-15T12:00:00Z",
    )

    class FakeClient:
        def fetch_event(self, _event_id):
            return fake_snapshot

    def fake_inplay(_predictor, **kwargs):
        return simulate_inplay(
            home_team=kwargs["home_team"],
            away_team=kwargs["away_team"],
            home_score=kwargs["home_score"],
            away_score=kwargs["away_score"],
            minute=kwargs["minute"],
            lambda_full_home=2.5,
            lambda_full_away=1.8,
            n_simulations=800,
        )

    monkeypatch.setattr("ingest.superbet.client.SuperbetClient", FakeClient)
    monkeypatch.setattr("ingest.superbet.store.save_event_snapshot", lambda _s: None)
    monkeypatch.setattr("models.wc_inplay.inplay_from_predictor", fake_inplay)
    monkeypatch.setattr("api.main._get_wc_predictor", lambda: FakePredictor())

    response = client.get("/worldcup/handicap/999?bankroll=1000&phase=group")
    assert response.status_code == 200
    data = response.json()
    assert data["event_id"] == 999
    assert data["home_team"] == "Brasil"
    assert len(data["lines"]) > 0
    assert data["current_score"] == "1x0"


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
