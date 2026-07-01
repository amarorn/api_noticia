"""Testes do mapeamento HTTP Sofascore (cooldown WAF)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.sofascore_http import ensure_sofascore_not_in_cooldown, raise_sofascore_http_error
from ingest.sofascore.client import SofascoreClientError, SofascoreWafBlockedError


def test_ensure_sofascore_not_in_cooldown_raises_503(monkeypatch):
    monkeypatch.setattr("api.sofascore_http.SofascoreClient.is_globally_blocked", lambda: True)
    monkeypatch.setattr(
        "api.sofascore_http.SofascoreClient.waf_cooldown_remaining_sec",
        lambda: 300.0,
    )
    with pytest.raises(HTTPException) as exc_info:
        ensure_sofascore_not_in_cooldown()
    assert exc_info.value.status_code == 503
    assert exc_info.value.headers["Retry-After"] == "300"
    assert "cooldown" in exc_info.value.detail.lower()


def test_raise_sofascore_http_error_maps_waf_to_503():
    with pytest.raises(HTTPException) as exc_info:
        raise_sofascore_http_error(SofascoreWafBlockedError("WAF bloqueado"))
    assert exc_info.value.status_code == 503


def test_raise_sofascore_http_error_maps_client_to_502():
    with pytest.raises(HTTPException) as exc_info:
        raise_sofascore_http_error(SofascoreClientError("timeout"))
    assert exc_info.value.status_code == 502
