"""Testes do embed Sportradar LMT Plus."""

from fastapi.testclient import TestClient

from api.main import app
from config import settings


def test_config_sportradar_sem_client_id(monkeypatch):
    monkeypatch.setattr(settings, "sportradar_client_id", None)
    client = TestClient(app)
    resp = client.get("/config/sportradar")
    assert resp.status_code == 200
    body = resp.json()
    assert body["embed_available"] is False
    assert body["widget"] == "match.lmtPlus"


def test_config_sportradar_com_client_id(monkeypatch):
    monkeypatch.setattr(settings, "sportradar_client_id", "demo-client")
    client = TestClient(app)
    resp = client.get("/config/sportradar")
    assert resp.status_code == 200
    assert resp.json()["embed_available"] is True


def test_lmt_embed_html_inclui_match_id(monkeypatch):
    monkeypatch.setattr(settings, "sportradar_client_id", "demo-client")
    client = TestClient(app)
    resp = client.get("/sportradar/lmt/67690926")
    assert resp.status_code == 200
    assert "match.lmtPlus" in resp.text
    assert "67690926" in resp.text
    assert "demo-client" in resp.text


def test_lmt_embed_sem_licenca(monkeypatch):
    monkeypatch.setattr(settings, "sportradar_client_id", None)
    client = TestClient(app)
    resp = client.get("/sportradar/lmt/67690926")
    assert resp.status_code == 200
    assert "SPORTRADAR_CLIENT_ID" in resp.text
