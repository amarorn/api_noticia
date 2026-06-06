from __future__ import annotations

import pytest

from ingest.fifa.client import FifaClient, FifaClientError


def test_fifa_client_init():
    client = FifaClient()
    assert client._ranking_api == "https://inside.fifa.com/api/live-world-ranking"
    assert client._live_api == "https://api.fifa.com/api/v3"


def test_fifa_client_custom_base():
    client = FifaClient(ranking_api="https://custom.api", live_api="https://live.custom")
    assert client._ranking_api == "https://custom.api"
    assert client._live_api == "https://live.custom"


def test_fifa_client_error_raised_on_bad_status():
    import httpx

    client = FifaClient()
    # Substitui session por um mock que retorna 404
    original_get = client._session.get

    def mock_get(*args, **kwargs):
        return httpx.Response(404, text="not found")

    client._session.get = mock_get

    with pytest.raises(FifaClientError, match="404"):
        client.get_json("https://example.com/test")

    client._session.get = original_get
