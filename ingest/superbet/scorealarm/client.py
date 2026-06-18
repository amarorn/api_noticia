"""HTTP/SSE ScoreAlarm (freetls.fastly.net)."""
from __future__ import annotations

import json
import logging
import time

import httpx

from config import settings

logger = logging.getLogger(__name__)

_TRANSIENT_HTTP_ERRORS = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
)


class ScorealarmClientError(Exception):
    pass


class ScorealarmClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        brand: str | None = None,
        locale: str | None = None,
        timeout_sec: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.scorealarm_base_url).rstrip("/")
        self.brand = brand or settings.scorealarm_brand
        self.locale = locale or settings.scorealarm_locale
        self.timeout_sec = timeout_sec or settings.scorealarm_timeout_sec

    def fetch_json(self, path: str, *, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; BolaoAI/1.0)",
        }
        attempts = max(1, settings.scorealarm_fetch_retries + 1)
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                with httpx.Client(timeout=self.timeout_sec, follow_redirects=True) as client:
                    response = client.get(url, params=params, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                if not isinstance(data, dict):
                    raise ScorealarmClientError(f"Resposta inválida ScoreAlarm: {path}")
                return data
            except _TRANSIENT_HTTP_ERRORS as exc:
                last_exc = exc
                if attempt + 1 < attempts:
                    time.sleep(0.25 * (attempt + 1))
                    continue
                raise ScorealarmClientError(f"Falha ScoreAlarm {path}: {exc}") from exc
            except httpx.HTTPError as exc:
                if isinstance(exc, _TRANSIENT_HTTP_ERRORS):
                    raise
                raise ScorealarmClientError(f"Falha ScoreAlarm {path}: {exc}") from exc
        raise ScorealarmClientError(f"Falha ScoreAlarm {path}: {last_exc}")

    def fetch_first_sse_json(self, path: str, *, params: dict | None = None) -> dict | None:
        """Lê primeira mensagem ``data:`` válida de um endpoint SSE."""
        url = f"{self.base_url}{path}"
        headers = {
            "Accept": "text/event-stream",
            "User-Agent": "Mozilla/5.0 (compatible; BolaoAI/1.0)",
        }
        attempts = max(1, settings.scorealarm_fetch_retries + 1)
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                with httpx.Client(timeout=self.timeout_sec, follow_redirects=True) as client:
                    with client.stream("GET", url, params=params, headers=headers) as response:
                        response.raise_for_status()
                        payload = _read_first_sse_data(response)
                return payload
            except _TRANSIENT_HTTP_ERRORS as exc:
                last_exc = exc
                if attempt + 1 < attempts:
                    time.sleep(0.25 * (attempt + 1))
                    continue
                raise ScorealarmClientError(f"Falha SSE ScoreAlarm {path}: {exc}") from exc
            except httpx.HTTPError as exc:
                if isinstance(exc, _TRANSIENT_HTTP_ERRORS):
                    raise
                raise ScorealarmClientError(f"Falha SSE ScoreAlarm {path}: {exc}") from exc
        raise ScorealarmClientError(f"Falha SSE ScoreAlarm {path}: {last_exc}")

    def offer_fixture_id(self, event_id: int) -> str:
        return f"ax:match:{event_id}"


def _read_first_sse_data(response: httpx.Response) -> dict | None:
    buffer = ""
    for chunk in response.iter_text():
        buffer += chunk
        for line in buffer.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw or raw == "[DONE]":
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return data
    return None


__all__ = ["ScorealarmClient", "ScorealarmClientError"]
