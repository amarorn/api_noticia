"""Cliente HTTP para a API de oferta Superbet BR."""
from __future__ import annotations

import json
import logging
import re
import time

import httpx

logger = logging.getLogger(__name__)

from config import settings
from ingest.superbet.parser import (
    SuperbetEventSnapshot,
    SuperbetLiveEventSummary,
    parse_live_event_summary,
    parse_superbet_event,
)

_TRANSIENT_HTTP_ERRORS = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
)


class SuperbetClientError(Exception):
    pass


class SuperbetClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        locale: str | None = None,
        timeout_sec: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.superbet_base_url).rstrip("/")
        self.locale = locale or settings.superbet_locale
        self.timeout_sec = timeout_sec or settings.superbet_timeout_sec

    def fetch_event(self, event_id: int) -> SuperbetEventSnapshot:
        attempts = max(1, settings.superbet_fetch_retries + 1)
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                return self._fetch_event_once(event_id)
            except _TRANSIENT_HTTP_ERRORS as exc:
                last_exc = exc
                if attempt + 1 < attempts:
                    time.sleep(0.35 * (attempt + 1))
                    continue
                raise SuperbetClientError(
                    f"Falha ao buscar evento Superbet {event_id}: {exc}"
                ) from exc
            except SuperbetClientError:
                raise
        raise SuperbetClientError(f"Falha ao buscar evento Superbet {event_id}: {last_exc}")

    def _fetch_event_once(self, event_id: int) -> SuperbetEventSnapshot:
        url = f"{self.base_url}/v3/subscription/{self.locale}/events"
        params = {"events": str(event_id)}
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; BolaoAI/1.0)",
        }
        try:
            with httpx.Client(timeout=self.timeout_sec, follow_redirects=True) as client:
                with client.stream("GET", url, params=params, headers=headers) as response:
                    response.raise_for_status()
                    text = _read_first_sse_data(response)
                payload = _parse_sse_payload(text)
        except httpx.HTTPError as exc:
            if isinstance(exc, _TRANSIENT_HTTP_ERRORS):
                raise
            raise SuperbetClientError(f"Falha ao buscar evento Superbet {event_id}: {exc}") from exc

        if not payload:
            raise SuperbetClientError(f"Evento Superbet {event_id} não encontrado")
        return parse_superbet_event(payload[0])

    def fetch_live_events(
        self,
        *,
        sport_id: int | None = 5,
    ) -> list[SuperbetLiveEventSummary]:
        """Busca lista de eventos ao vivo via SSE streaming (lê primeira mensagem e fecha)."""
        attempts = max(1, settings.superbet_fetch_retries + 1)
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                return self._fetch_live_events_once(sport_id=sport_id)
            except _TRANSIENT_HTTP_ERRORS as exc:
                last_exc = exc
                if attempt + 1 < attempts:
                    time.sleep(0.35 * (attempt + 1))
                    continue
                raise SuperbetClientError(
                    f"Falha ao buscar jogos ao vivo Superbet: {exc}"
                ) from exc
            except SuperbetClientError:
                raise
        raise SuperbetClientError(f"Falha ao buscar jogos ao vivo Superbet: {last_exc}")

    def _fetch_live_events_once(
        self,
        *,
        sport_id: int | None,
    ) -> list[SuperbetLiveEventSummary]:
        url = f"{self.base_url}/v3/subscription/{self.locale}/live"
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; BolaoAI/1.0)",
        }
        try:
            with httpx.Client(timeout=self.timeout_sec, follow_redirects=True) as client:
                with client.stream("GET", url, headers=headers) as response:
                    response.raise_for_status()
                    text = _read_first_sse_data(response)
                raw_events = _parse_sse_array_payload(text)
        except httpx.HTTPError as exc:
            if isinstance(exc, _TRANSIENT_HTTP_ERRORS):
                raise
            raise SuperbetClientError(f"Falha ao buscar jogos ao vivo Superbet: {exc}") from exc

        summaries: list[SuperbetLiveEventSummary] = []
        for ev in raw_events:
            if not isinstance(ev, dict):
                continue
            summary = parse_live_event_summary(ev)
            if summary is None:
                continue
            if sport_id is not None and summary.sport_id != sport_id:
                continue
            summaries.append(summary)

        summaries.sort(
            key=lambda item: (
                -(item.home_score + item.away_score),
                -item.minute,
                item.event_name,
            ),
        )
        return summaries


def _read_first_sse_data(response: httpx.Response) -> str:
    """Lê o stream SSE até obter a primeira linha 'data:' com JSON válido e completo.

    Endpoints SSE da Superbet enviam um snapshot completo na primeira mensagem e depois mantêm
    a conexão aberta para incrementos. Precisamos apenas do snapshot inicial.
    O JSON pode chegar fragmentado em múltiplos chunks, então acumulamos até parsear com sucesso.
    """
    buffer = ""
    for chunk in response.iter_text():
        buffer += chunk
        idx = buffer.find("data:")
        if idx == -1:
            continue
        after_prefix = buffer[idx + 5:]
        newline_pos = after_prefix.find("\n")
        if newline_pos != -1:
            raw = after_prefix[:newline_pos].strip()
        else:
            raw = after_prefix.strip()
        if not raw or raw == "[DONE]":
            continue
        try:
            json.loads(raw)
            return buffer
        except json.JSONDecodeError:
            if newline_pos != -1:
                return buffer
            continue
    return buffer


def _parse_sse_array_payload(text: str) -> list[dict]:
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        raw = line[5:].strip()
        if not raw or raw == "[DONE]":
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"(\[{.*}\])", raw, re.DOTALL)
            if not match:
                continue
            data = json.loads(match.group(1))
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            return [data]
    return []


def _parse_sse_payload(text: str) -> list[dict]:
    chunks: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        raw = line[5:].strip()
        if not raw or raw == "[DONE]":
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"(\[{.*}\])", raw, re.DOTALL)
            if not match:
                continue
            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError:
                logger.warning("Superbet SSE chunk nao eh JSON valido; ignorando: %s", raw[:200])
                continue
        if isinstance(data, list) and data:
            if isinstance(data[0], dict):
                chunks.append(data[0])
        elif isinstance(data, dict):
            chunks.append(data)
    return chunks
