"""Respostas HTTP para endpoints que dependem da API Sofascore."""

from __future__ import annotations

from fastapi import HTTPException

from ingest.sofascore.client import SofascoreClient, SofascoreClientError, SofascoreWafBlockedError


def ensure_sofascore_not_in_cooldown() -> None:
    """Fail-fast: evita novas chamadas ao Sofascore durante cooldown WAF."""
    if not SofascoreClient.is_globally_blocked():
        return
    remaining = max(1, int(SofascoreClient.waf_cooldown_remaining_sec()))
    raise HTTPException(
        status_code=503,
        detail=(
            f"Sofascore em cooldown por bloqueio WAF — aguarde ~{remaining}s. "
            "Use sofascore_event_id manual ou tente novamente depois."
        ),
        headers={"Retry-After": str(remaining)},
    )


def raise_sofascore_http_error(exc: Exception) -> None:
    """Mapeia erros do cliente Sofascore para 503 (WAF) ou 502 (outros)."""
    if isinstance(exc, SofascoreWafBlockedError):
        remaining = max(1, int(SofascoreClient.waf_cooldown_remaining_sec()))
        raise HTTPException(
            status_code=503,
            detail=str(exc),
            headers={"Retry-After": str(remaining)},
        ) from exc
    if isinstance(exc, SofascoreClientError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise exc


__all__ = ["ensure_sofascore_not_in_cooldown", "raise_sofascore_http_error"]
