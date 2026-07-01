"""Top picks sociais Superbet (sentimento da casa) — melhor esforço com fallback."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from config import settings

logger = logging.getLogger(__name__)


def fetch_social_top_picks(
    fixture_id: str,
    *,
    event_id: int | None = None,
) -> dict[str, Any]:
    """Busca apostas populares in-play; retorna payload vazio se indisponível."""
    out: dict[str, Any] = {
        "available": False,
        "source": "social-front",
        "reason": None,
        "picks": [],
    }
    if not settings.social_top_picks_enabled:
        out["reason"] = "social_top_picks desabilitado"
        return out

    base = settings.social_top_picks_base_url.rstrip("/")
    path = (
        f"/top-picks/in-play/{settings.scorealarm_brand}/"
        f"{settings.scorealarm_locale}"
    )
    url = f"{base}{path}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; BolaoAI/1.0)",
        "Origin": settings.social_top_picks_origin,
        "Referer": settings.social_top_picks_origin + "/",
    }
    params = {"fixture-id": fixture_id}
    if event_id is not None:
        params["event-id"] = str(event_id)

    try:
        with httpx.Client(timeout=settings.social_top_picks_timeout_sec, follow_redirects=True) as client:
            response = client.get(url, params=params, headers=headers)
            if response.status_code != 200:
                out["reason"] = f"social-front HTTP {response.status_code}"
                return out
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type:
                out["reason"] = "social-front retornou formato não-JSON"
                return out
            data = response.json()
    except httpx.HTTPError as exc:
        logger.debug("social_top_picks_falha fixture=%s: %s", fixture_id, exc)
        out["reason"] = f"social-front indisponível: {exc}"
        return out

    picks = _normalize_picks(data)
    if not picks:
        out["reason"] = "social-front sem picks para o fixture"
        return out

    out["available"] = True
    out["picks"] = picks
    return out


def _normalize_picks(data: Any) -> list[dict[str, Any]]:
    """Aceita lista direta ou objeto com chave ``picks`` / ``top_picks``."""
    raw_list: list[Any]
    if isinstance(data, list):
        raw_list = data
    elif isinstance(data, dict):
        raw_list = (
            data.get("picks")
            or data.get("top_picks")
            or data.get("items")
            or []
        )
    else:
        return []

    picks: list[dict[str, Any]] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("name") or item.get("market_name") or "").strip()
        if not label:
            continue
        picks.append(
            {
                "label": label,
                "market": str(item.get("market") or item.get("market_type") or ""),
                "outcome": str(item.get("outcome") or item.get("selection") or ""),
                "odd": _safe_float(item.get("odd") or item.get("odds")),
                "bet_count": int(item.get("bet_count") or item.get("count") or 0) or None,
                "share_pct": _safe_float(item.get("share_pct") or item.get("percentage")),
            }
        )
    return picks[:8]


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["fetch_social_top_picks"]
