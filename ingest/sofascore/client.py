from __future__ import annotations

import time
from typing import Any

import structlog

from config import settings

logger = structlog.get_logger()

DEFAULT_BASE_URL = "https://api.sofascore.com/api/v1"
DEFAULT_IMPERSONATE = "chrome124"
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://www.sofascore.com",
    "Referer": "https://www.sofascore.com/",
}


class SofascoreClientError(RuntimeError):
    pass


class SofascoreWafBlockedError(SofascoreClientError):
    """WAF Cloudflare bloqueou o IP (403 challenge)."""


class SofascoreClient:
    _shared_waf_blocks: int = 0
    _shared_waf_cooldown_until: float = 0.0

    def __init__(
        self,
        *,
        base_url: str | None = None,
        impersonate: str | None = None,
        min_interval_sec: float | None = None,
        waf_max_retries: int | None = None,
    ):
        self._base = (base_url or settings.sofascore_base_url).rstrip("/")
        self._impersonate = impersonate or settings.sofascore_impersonate
        self._min_interval = min_interval_sec or settings.sofascore_min_interval_sec
        self._waf_max_retries = (
            waf_max_retries
            if waf_max_retries is not None
            else settings.sofascore_waf_max_retries
        )
        self._waf_retry_base_sec = settings.sofascore_waf_retry_base_sec
        self._waf_fail_fast_after = settings.sofascore_waf_fail_fast_after
        self._last_request_at = 0.0
        self._consecutive_waf_blocks = 0
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

    def _reset_session(self) -> None:
        self._session = self._build_session()

    @staticmethod
    def _is_waf_challenge(response: Any) -> bool:
        if response.status_code != 403:
            return False
        body = (response.text or "").lower()
        return "challenge" in body or '"code": 403' in body

    def _raise_waf_blocked(self) -> None:
        raise SofascoreWafBlockedError(
            "Sofascore retornou 403 (WAF challenge). O IP parece bloqueado — "
            "aguarde algumas horas, aumente SOFASCORE_MIN_INTERVAL_SEC (ex.: 2.0) "
            "e rode lotes menores (--home ou --limit). Troque de rede/VPN se persistir."
        )

    @classmethod
    def is_globally_blocked(cls) -> bool:
        return time.monotonic() < cls._shared_waf_cooldown_until

    @classmethod
    def waf_cooldown_remaining_sec(cls) -> float:
        return max(0.0, cls._shared_waf_cooldown_until - time.monotonic())

    @classmethod
    def _activate_global_cooldown(cls) -> None:
        cls._shared_waf_cooldown_until = time.monotonic() + settings.sofascore_waf_cooldown_sec
        logger.warning(
            "sofascore_waf_cooldown_ativo",
            cooldown_sec=settings.sofascore_waf_cooldown_sec,
        )

    @classmethod
    def _clear_global_cooldown(cls) -> None:
        cls._shared_waf_blocks = 0
        cls._shared_waf_cooldown_until = 0.0

    def _record_waf_block(self) -> None:
        SofascoreClient._shared_waf_blocks += 1
        self._consecutive_waf_blocks += 1
        if (
            self._consecutive_waf_blocks >= self._waf_fail_fast_after
            or SofascoreClient._shared_waf_blocks >= self._waf_fail_fast_after
        ):
            SofascoreClient._activate_global_cooldown()

    def probe(self) -> bool:
        """Testa conectividade com a API. Retorna True se responder 200."""
        saved_retries = self._waf_max_retries
        self._waf_max_retries = 0
        try:
            self.get_json("sport/football/scheduled-events/2026-06-11")
        except SofascoreWafBlockedError:
            return False
        except SofascoreClientError:
            return False
        finally:
            self._waf_max_retries = saved_retries
        return True

    @property
    def waf_blocked(self) -> bool:
        return self._consecutive_waf_blocks >= self._waf_fail_fast_after

    def get_json(self, path: str, *, params: dict | None = None) -> dict[str, Any]:
        if self.is_globally_blocked():
            raise SofascoreWafBlockedError(
                "Sofascore em cooldown por bloqueio WAF — aguarde alguns minutos."
            )
        url = path if path.startswith("http") else f"{self._base}/{path.lstrip('/')}"
        last_error: SofascoreClientError | None = None

        for attempt in range(self._waf_max_retries + 1):
            self._throttle()
            response = self._session.get(
                url,
                params=params,
                timeout=settings.sofascore_timeout_sec,
                headers=DEFAULT_HEADERS,
            )
            self._last_request_at = time.monotonic()

            if response.status_code == 403 and self._is_waf_challenge(response):
                self._record_waf_block()
                last_error = SofascoreWafBlockedError(
                    "Sofascore retornou 403 (WAF challenge). "
                    "Verifique curl_cffi, rate limits e bloqueio de IP."
                )
                if self.waf_blocked or self.is_globally_blocked():
                    logger.error(
                        "sofascore_waf_fail_fast",
                        consecutive_blocks=self._consecutive_waf_blocks,
                        path=path,
                    )
                    self._raise_waf_blocked()
                if attempt < self._waf_max_retries:
                    wait_sec = self._waf_retry_base_sec * (2**attempt)
                    logger.warning(
                        "sofascore_waf_retry",
                        attempt=attempt + 1,
                        wait_sec=wait_sec,
                        path=path,
                    )
                    time.sleep(wait_sec)
                    self._reset_session()
                    continue
                self._raise_waf_blocked()

            if response.status_code == 403:
                raise SofascoreClientError(
                    "Sofascore retornou 403 (WAF). Verifique curl_cffi e rate limits."
                )
            if response.status_code >= 400:
                raise SofascoreClientError(
                    f"Sofascore HTTP {response.status_code} para {path}: {response.text[:200]}"
                )

            self._consecutive_waf_blocks = 0
            SofascoreClient._clear_global_cooldown()
            payload = response.json()
            if not isinstance(payload, dict):
                raise SofascoreClientError(f"Resposta inesperada de {path}")
            return payload

        if last_error is not None:
            raise last_error
        raise SofascoreClientError(f"Falha ao consultar {path}")

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

    def event_pregame_form(self, event_id: int) -> dict[str, Any]:
        """Forma pré-jogo: posição, pontos, avgRating, sequência de resultados."""
        return self.get_json(f"event/{event_id}/pregame-form")

    def event_team_streaks(self, event_id: int) -> dict[str, Any]:
        """Séries do time: invencibilidade, vitórias seguidas, etc."""
        return self.get_json(f"event/{event_id}/team-streaks")

    def event_h2h(self, event_id: int) -> dict[str, Any]:
        """Histórico direto (head-to-head) entre os dois times."""
        return self.get_json(f"event/{event_id}/h2h")

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
        try:
            data = self.get_json(f"team/{team_id}/events/last/{page}")
        except SofascoreClientError as exc:
            if "HTTP 404" in str(exc):
                return []
            raise
        return list(data.get("events") or [])

    def team_upcoming_events(self, team_id: int, page: int = 0) -> list[dict[str, Any]]:
        try:
            data = self.get_json(f"team/{team_id}/events/next/{page}")
        except SofascoreClientError as exc:
            if "HTTP 404" in str(exc):
                return []
            raise
        return list(data.get("events") or [])
