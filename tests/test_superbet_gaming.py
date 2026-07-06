"""Testes do cliente e endpoints casino Superbet."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from ingest.superbet.gaming import (
    SuperbetGamingClient,
    build_superbet_game_url,
    parse_casino_game_payload,
    resolve_casino_image_url,
)

client = TestClient(app)

BACBO_PAYLOAD = {
    "provider_id": "SuperbetBacBo001",
    "has_anonymous_demo": False,
    "has_demo": False,
    "slug": "bac-bo-superbet",
    "tags": ["Evolution Gaming", "top card"],
    "integrator": "evolution",
    "min_stake": 2.0,
    "seo_id": "379099",
    "product": "live_casino",
    "title": "Bac Bo Superbet",
    "game_category": {"value": "top_card"},
    "studio": {"value": "Evolution Gaming"},
    "image": {"value": "cdn/images/evolution_SuperbetBacBo001/poster.png"},
}


def test_parse_casino_game_payload():
    game = parse_casino_game_payload(BACBO_PAYLOAD)
    assert game.seo_id == "379099"
    assert game.provider_id == "SuperbetBacBo001"
    assert game.min_stake == 2.0
    assert game.integrator == "evolution"
    assert "superbet.bet.br/jogo/bac-bo-superbet/379099" in game.superbet_url
    assert game.image_url is not None
    assert game.image_url.endswith("poster.png")


def test_resolve_casino_image_url_relative():
    url = resolve_casino_image_url("cdn/images/foo.png")
    assert url == "https://superbet-content.freetls.fastly.net/cdn/images/foo.png"


def test_build_superbet_game_url():
    assert build_superbet_game_url("bac-bo-superbet", "379099").endswith("/379099")


@patch.object(SuperbetGamingClient, "fetch_curated_catalog")
def test_casino_catalog_endpoint(mock_fetch, monkeypatch):
    monkeypatch.setattr("config.settings.api_key", None)
    from ingest.superbet.gaming import parse_casino_game_payload

    mock_fetch.return_value = [parse_casino_game_payload(BACBO_PAYLOAD)]
    response = client.get("/casino/games")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["games"][0]["title"] == "Bac Bo Superbet"
    assert "WebSocket" in body["betting_note"]


@patch.object(SuperbetGamingClient, "fetch_game_by_seo_id")
def test_casino_game_endpoint(mock_fetch, monkeypatch):
    monkeypatch.setattr("config.settings.api_key", None)
    from ingest.superbet.gaming import parse_casino_game_payload

    mock_fetch.return_value = parse_casino_game_payload(BACBO_PAYLOAD)
    response = client.get("/casino/games/379099")
    assert response.status_code == 200
    assert response.json()["provider_id"] == "SuperbetBacBo001"


@patch.object(SuperbetGamingClient, "fetch_game_by_seo_id")
def test_casino_game_not_found(mock_fetch, monkeypatch):
    monkeypatch.setattr("config.settings.api_key", None)
    from ingest.superbet.gaming import SuperbetGamingClientError

    mock_fetch.side_effect = SuperbetGamingClientError("Jogo casino seo_id=0 não encontrado")
    response = client.get("/casino/games/0")
    assert response.status_code == 404
