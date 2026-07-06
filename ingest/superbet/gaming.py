"""Cliente da API pública de catálogo casino Superbet BR (Evolution, slots, etc.)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from config import settings

_GAMING_HTTP_ERRORS = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
)

# Jogos curados no Bolão AI — expandir seo_id conforme catálogo Superbet.
CURATED_CASINO_SEO_IDS: tuple[str, ...] = ("379099",)

CURATED_CASINO_NOTES: dict[str, str] = {
    "379099": "Mesa exclusiva Bac Bo ao vivo (Evolution). Apostas via WebSocket na Superbet.",
}


class SuperbetGamingClientError(Exception):
    pass


@dataclass(frozen=True)
class SuperbetCasinoGame:
    seo_id: str
    title: str
    slug: str
    provider_id: str
    integrator: str
    min_stake: float
    has_demo: bool
    has_anonymous_demo: bool
    product: str
    game_category: str | None
    studio: str | None
    image_url: str | None
    superbet_url: str
    tags: list[str] = field(default_factory=list)
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "seo_id": self.seo_id,
            "title": self.title,
            "slug": self.slug,
            "provider_id": self.provider_id,
            "integrator": self.integrator,
            "min_stake": self.min_stake,
            "has_demo": self.has_demo,
            "has_anonymous_demo": self.has_anonymous_demo,
            "product": self.product,
            "game_category": self.game_category,
            "studio": self.studio,
            "image_url": self.image_url,
            "superbet_url": self.superbet_url,
            "tags": list(self.tags),
            "note": self.note,
        }


def build_superbet_game_url(slug: str, seo_id: str) -> str:
    base = settings.superbet_site_url.rstrip("/")
    return f"{base}/jogo/{slug}/{seo_id}"


def resolve_casino_image_url(raw: str | None) -> str | None:
    if not raw:
        return None
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    cdn = settings.superbet_content_cdn_url.rstrip("/")
    path = raw.lstrip("/")
    return f"{cdn}/{path}"


def _label_value(payload: dict[str, Any], key: str) -> str | None:
    node = payload.get(key)
    if isinstance(node, dict):
        value = node.get("value")
        return str(value) if value is not None else None
    if node is not None:
        return str(node)
    return None


def parse_casino_game_payload(payload: dict[str, Any]) -> SuperbetCasinoGame:
    seo_id = str(payload.get("seo_id") or "")
    slug = str(payload.get("slug") or "")
    if not seo_id or not slug:
        raise SuperbetGamingClientError("Resposta de jogo casino incompleta (seo_id/slug)")

    image_raw = None
    image_node = payload.get("image")
    if isinstance(image_node, dict):
        image_raw = image_node.get("value")
    elif isinstance(image_node, str):
        image_raw = image_node
    if not image_raw:
        tile = payload.get("tile_content") or {}
        portrait = tile.get("portrait") if isinstance(tile, dict) else None
        if isinstance(portrait, dict):
            image_raw = portrait.get("poster_url")

    tags_raw = payload.get("tags") or []
    tags = [str(t) for t in tags_raw if t]

    return SuperbetCasinoGame(
        seo_id=seo_id,
        title=str(payload.get("title") or slug),
        slug=slug,
        provider_id=str(payload.get("provider_id") or ""),
        integrator=str(payload.get("integrator") or ""),
        min_stake=float(payload.get("min_stake") or 0),
        has_demo=bool(payload.get("has_demo")),
        has_anonymous_demo=bool(payload.get("has_anonymous_demo")),
        product=str(payload.get("product") or ""),
        game_category=_label_value(payload, "game_category"),
        studio=_label_value(payload, "studio") or _label_value(payload, "provider"),
        image_url=resolve_casino_image_url(str(image_raw) if image_raw else None),
        superbet_url=build_superbet_game_url(slug, seo_id),
        tags=tags,
        note=CURATED_CASINO_NOTES.get(seo_id),
    )


class SuperbetGamingClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_sec: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.superbet_gaming_api_url).rstrip("/")
        self.timeout_sec = timeout_sec or settings.superbet_timeout_sec

    def fetch_game_by_seo_id(self, seo_id: str) -> SuperbetCasinoGame:
        url = (
            f"{self.base_url}/games/offer/public/superbet-bet-br/v2/game/by-seo-id"
        )
        params = {"seo_id": seo_id}
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; BolaoAI/1.0)",
        }
        try:
            with httpx.Client(timeout=self.timeout_sec, follow_redirects=True) as client:
                response = client.get(url, params=params, headers=headers)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise SuperbetGamingClientError(f"Jogo casino seo_id={seo_id} não encontrado") from exc
            raise SuperbetGamingClientError(
                f"Falha ao buscar jogo casino seo_id={seo_id}: {exc}"
            ) from exc
        except _GAMING_HTTP_ERRORS as exc:
            raise SuperbetGamingClientError(
                f"Falha ao buscar jogo casino seo_id={seo_id}: {exc}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SuperbetGamingClientError(
                f"Falha ao buscar jogo casino seo_id={seo_id}: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise SuperbetGamingClientError(f"Resposta inválida para seo_id={seo_id}")
        return parse_casino_game_payload(payload)

    def fetch_curated_catalog(self) -> list[SuperbetCasinoGame]:
        games: list[SuperbetCasinoGame] = []
        errors: list[str] = []
        for seo_id in CURATED_CASINO_SEO_IDS:
            try:
                games.append(self.fetch_game_by_seo_id(seo_id))
            except SuperbetGamingClientError as exc:
                errors.append(str(exc))
        if not games and errors:
            raise SuperbetGamingClientError("; ".join(errors))
        return games
