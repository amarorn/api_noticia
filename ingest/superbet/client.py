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
        """Busca lista de eventos ao vivo via SSE streaming (lê primeira mensagem e fecha)."""
        url = f"{self.base_url}/v3/subscription/{self.locale}/live"
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; BolaoAI/1.0)",
        }
        try:
            with httpx.Client(timeout=self.timeout_sec, follow_redirects=True) as client:
                with client.stream("GET", url, headers=headers) as response:
                    response.raise_for_status()
                    # SSE: lê apenas a primeira linha 'data:' (snapshot completo)
                    text = _read_first_sse_data(response)
                raw_events = _parse_sse_array_payload(text)
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


def _read_first_sse_data(response: httpx.Response) -> str:
    """Lê o stream SSE até obter a primeira linha 'data:' com JSON válido e completo.

    Endpoints SSE da Superbet enviam um snapshot completo na primeira mensagem e depois mantêm
    a conexão aberta para incrementos. Precisamos apenas do snapshot inicial.
    O JSON pode chegar fragmentado em múltiplos chunks, então acumulamos até parsear com sucesso.
    """
    buffer = ""
    for chunk in response.iter_text():
        buffer += chunk
        # Procura o prefixo 'data:' e tenta parsear o conteúdo da primeira linha
        idx = buffer.find("data:")
        if idx == -1:
            continue
        after_prefix = buffer[idx + 5:]
        # Pega só até a próxima newline (se houver), para não misturar mensagens SSE
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
            # Se já temos uma newline após data: e ainda falha, é erro de formato
            # Se não temos newline, o JSON pode estar incompleto (chunk parcial)
            if newline_pos != -1:
                # Linha completa mas JSON inválido — tentar regex fallback
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
            data = json.loads(match.group(1))
        if isinstance(data, list) and data:
            if isinstance(data[0], dict):
                chunks.append(data[0])
        elif isinstance(data, dict):
            chunks.append(data)
    return chunks
