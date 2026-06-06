from __future__ import annotations

import time
from typing import Any

import structlog

logger = structlog.get_logger()

FIFA_RANKING_API = "https://inside.fifa.com/api/live-world-ranking"
FIFA_LIVE_API = "https://api.fifa.com/api/v3"


class FifaClientError(RuntimeError):
    pass


class FifaClient:
    """Cliente para APIs oficiais da FIFA.

    Endpoints:
    - Jogos da janela de ranking: /get-match-window-matches
    - Detalhes de jogo: /live/football/{IdMatch}
    """

    def __init__(
        self,
        *,
        ranking_api: str | None = None,
        live_api: str | None = None,
        min_interval_sec: float = 0.5,
    ):
        self._ranking_api = (ranking_api or FIFA_RANKING_API).rstrip("/")
        self._live_api = (live_api or FIFA_LIVE_API).rstrip("/")
        self._min_interval = min_interval_sec
        self._last_request_at = 0.0
        self._session = self._build_session()

    def _build_session(self):
        try:
            import httpx
        except ImportError as exc:
            raise FifaClientError(
                "httpx é obrigatório para a API da FIFA. "
                'Instale com: pip install -e ".[dev]"'
            ) from exc
        return httpx.Client(timeout=30.0, follow_redirects=True)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

    def get_json(self, url: str, *, params: dict | None = None) -> dict[str, Any]:
        self._throttle()
        response = self._session.get(url, params=params)
        self._last_request_at = time.monotonic()
        if response.status_code == 429:
            raise FifaClientError("FIFA retornou 429 (rate limit).")
        if response.status_code >= 400:
            raise FifaClientError(
                f"FIFA HTTP {response.status_code} para {url}: {response.text[:200]}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise FifaClientError(f"Resposta inesperada de {url}")
        return payload

    def match_window_matches(
        self,
        *,
        gender: int = 1,
        ranking_type: int = 0,
        locale: str = "pt",
    ) -> dict[str, Any]:
        """Busca jogos da janela atual de rankings FIFA.

        Args:
            gender: 1=masculino, 2=feminino
            ranking_type: 0=ranking geral
            locale: idioma (pt, en, etc.)

        Returns:
            Dict com chave 'matches' contendo jogos por time.
        """
        url = f"{self._ranking_api}/get-match-window-matches"
        params = {
            "locale": locale,
            "gender": gender,
            "rankingType": ranking_type,
        }
        return self.get_json(url, params=params)

    def match_details(self, match_id: str) -> dict[str, Any]:
        """Busca detalhes completos de um jogo pelo IdMatch.

        Retorna: escalações, gols, cartões, substituições, estádio, etc.
        """
        url = f"{self._live_api}/live/football/{match_id}"
        return self.get_json(url)

    def player_profile(self, player_id: str) -> dict[str, Any]:
        """Busca perfil de um jogador pelo IdPlayer."""
        url = f"{self._live_api}/players/{player_id}"
        return self.get_json(url)

    def team_matches(
        self,
        team_id: str,
        *,
        gender: int = 1,
        page: int = 0,
    ) -> list[dict[str, Any]]:
        """Busca jogos recentes de uma seleção.

        Nota: endpoint experimental da FIFA.
        """
        url = f"{self._live_api}/teams/{team_id}/matches"
        params = {"gender": gender, "page": page}
        data = self.get_json(url, params=params)
        return list(data.get("matches") or [])
