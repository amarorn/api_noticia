"""Cliente HTTP para a API de oferta Superbet BR."""
from __future__ import annotations

import json
import re

import httpx

from config import settings
from ingest.superbet.parser import (
    SuperbetEventSnapshot,
    SuperbetLiveEventSummary,
    parse_live_event_summary,
    parse_superbet_event,
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
        url = f"{self.base_url}/v3/subscription/{self.locale}/events"
        params = {"events": str(event_id)}
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; BolaoAI/1.0)",
        }
        try:
            with httpx.Client(timeout=self.timeout_sec, follow_redirects=True) as client:
                response = client.get(url, params=params, headers=headers)
                response.raise_for_status()
                payload = _parse_sse_payload(response.text)
        except httpx.HTTPError as exc:
            raise SuperbetClientError(f"Falha ao buscar evento Superbet {event_id}: {exc}") from exc

        if not payload:
            raise SuperbetClientError(f"Evento Superbet {event_id} não encontrado")
        return parse_superbet_event(payload[0])

    def fetch_live_events(
        self,
        *,
        sport_id: int | None = 5,
    ) -> list[SuperbetLiveEventSummary]:
        url = f"{self.base_url}/v3/subscription/{self.locale}/live"
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; BolaoAI/1.0)",
        }
        try:
            with httpx.Client(timeout=self.timeout_sec, follow_redirects=True) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                raw_events = _parse_sse_array_payload(response.text)
        except httpx.HTTPError as exc:
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
            data = json.loads(match.group(1))
        if isinstance(data, list) and data:
            if isinstance(data[0], dict):
                chunks.append(data[0])
        elif isinstance(data, dict):
            chunks.append(data)
    return chunks
