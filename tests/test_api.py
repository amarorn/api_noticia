from fastapi.testclient import TestClient

from api.main import app

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
