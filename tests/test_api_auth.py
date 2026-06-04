from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_open_without_api_key_configured():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_live_always_public(monkeypatch):
    monkeypatch.setattr("config.settings.api_key", "secret-key")
    response = client.get("/health/live")
    assert response.status_code == 200


def test_requires_key_when_configured(monkeypatch):
    monkeypatch.setattr("config.settings.api_key", "secret-key")
    assert client.get("/health").status_code == 401
    assert client.get("/news/all").status_code == 401


def test_accepts_x_api_key_header(monkeypatch):
    monkeypatch.setattr("config.settings.api_key", "secret-key")
    response = client.get("/health", headers={"X-API-Key": "secret-key"})
    assert response.status_code == 200


def test_accepts_bearer_token(monkeypatch):
    monkeypatch.setattr("config.settings.api_key", "secret-key")
    response = client.get(
        "/health",
        headers={"Authorization": "Bearer secret-key"},
    )
    assert response.status_code == 200


def test_multiple_keys(monkeypatch):
    monkeypatch.setattr("config.settings.api_key", "alpha,beta")
    assert client.get("/health", headers={"X-API-Key": "beta"}).status_code == 200
    assert client.get("/health", headers={"X-API-Key": "gamma"}).status_code == 401
