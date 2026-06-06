from __future__ import annotations

import time
from typing import Any

import structlog

from config import settings

logger = structlog.get_logger()

DEFAULT_BASE_URL = "https://api.sofascore.com/api/v1"
DEFAULT_IMPERSONATE = "chrome124"


class SofascoreClientError(RuntimeError):
    pass


class SofascoreClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        impersonate: str | None = None,
        min_interval_sec: float | None = None,
    ):
        self._base = (base_url or settings.sofascore_base_url).rstrip("/")
        self._impersonate = impersonate or settings.sofascore_impersonate
        self._min_interval = min_interval_sec or settings.sofascore_min_interval_sec
        self._last_request_at = 0.0
        self._session = self._build_session()

    def _build_session(self):
        try:
            from curl_cffi import requests as curl_requests
        except ImportError as exc:
            raise SofascoreClientError(
                "curl_cffi é obrigatório para a API Sofascore. "
                'Instale com: pip install -e ".[sofascore]"'
            ) from exc
        return curl_requests.Session(impersonate=self._impersonate)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

    def get_json(self, path: str, *, params: dict | None = None) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{self._base}/{path.lstrip('/')}"
        self._throttle()
        response = self._session.get(
            url,
            params=params,
            timeout=settings.sofascore_timeout_sec,
            headers={"Accept": "application/json"},
        )
        self._last_request_at = time.monotonic()
        if response.status_code == 403:
            raise SofascoreClientError(
                "Sofascore retornou 403 (WAF). Verifique curl_cffi e rate limits."
            )
        if response.status_code >= 400:
            raise SofascoreClientError(
                f"Sofascore HTTP {response.status_code} para {path}: {response.text[:200]}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise SofascoreClientError(f"Resposta inesperada de {path}")
        return payload

    def scheduled_events(self, sport: str, date_iso: str) -> list[dict[str, Any]]:
        data = self.get_json(f"sport/{sport}/scheduled-events/{date_iso}")
        return list(data.get("events") or [])

    def event(self, event_id: int) -> dict[str, Any]:
        data = self.get_json(f"event/{event_id}")
        return data.get("event") or data

    def event_lineups(self, event_id: int) -> dict[str, Any]:
        return self.get_json(f"event/{event_id}/lineups")

    def event_statistics(self, event_id: int) -> dict[str, Any]:
        return self.get_json(f"event/{event_id}/statistics")

    def event_incidents(self, event_id: int) -> dict[str, Any]:
        return self.get_json(f"event/{event_id}/incidents")

    def search_team(self, query: str) -> dict[str, Any] | None:
        data = self.get_json("search/teams", params={"q": query})
        for item in data.get("results") or []:
            entity = item.get("entity") or {}
            if entity.get("national"):
                return entity
        return None

    def player_statistics(self, player_id: int) -> list[dict[str, Any]]:
        data = self.get_json(f"player/{player_id}/statistics")
        return list(data.get("seasons") or [])

    def team_recent_events(self, team_id: int, page: int = 0) -> list[dict[str, Any]]:
        data = self.get_json(f"team/{team_id}/events/last/{page}")
        return list(data.get("events") or [])
