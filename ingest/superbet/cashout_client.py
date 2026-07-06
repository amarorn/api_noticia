"""Cliente do endpoint de cash-out da Superbet."""
from __future__ import annotations

from typing import Any

import httpx

CASHOUT_BASE = "https://production-superbet-cashout.freetls.fastly.net/cashout/api/v2"
CASHOUT_VALUE_URL = f"{CASHOUT_BASE}/requestCashoutValue"


def fetch_cashout_value(ticket_code: str, target: str = "SB_BR", timeout: float = 10.0) -> dict[str, Any] | None:
    """Consulta o valor de cash-out disponível para um bilhete aberto na Superbet.

    Parâmetros
    ----------
    ticket_code : str
        Código do bilhete (ex: 892P-1YINSZ).
    target : str, default "SB_BR"
        Target de mercado da Superbet.
    timeout : float
        Timeout HTTP em segundos.

    Retorna
    -------
    dict | None
        Payload do cash-out ou None se falhar.
    """
    url = f"{CASHOUT_VALUE_URL}?target={target}&ticketCode={ticket_code}"
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


def execute_cashout(
    ticket_code: str,
    *,
    target: str = "SB_BR",
    min_value: float | None = None,
    auth_header: str | None = None,
    timeout: float = 12.0,
) -> dict[str, Any]:
    """Tenta executar cash-out via API Superbet (requer token/sessão do usuário).

    Em produção o fluxo autenticado roda na extensão Chrome; este helper serve para
    scripts e testes quando ``auth_header`` (Bearer) estiver disponível.
    """
    quote = fetch_cashout_value(ticket_code, target=target, timeout=timeout)
    if not quote:
        return {"ok": False, "error": "quote_failed"}
    if not quote.get("eligible"):
        return {
            "ok": False,
            "error": quote.get("unavailabilityReason") or "ineligible",
            "quote": quote,
        }

    value = float(quote.get("value") or 0)
    if min_value is not None and value < min_value:
        return {"ok": False, "error": "below_min", "value": value, "min_value": min_value}

    headers: dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
    if auth_header:
        headers["Authorization"] = auth_header if auth_header.startswith("Bearer") else f"Bearer {auth_header}"

    payload = {"target": target, "ticketCode": ticket_code, "value": value}
    endpoints = ("cashout", "requestCashout", "confirmCashout", "placeCashout")

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            for ep in endpoints:
                resp = client.post(f"{CASHOUT_BASE}/{ep}", json=payload, headers=headers)
                if resp.is_success:
                    data = resp.json() if resp.content else {}
                    return {"ok": True, "endpoint": ep, "value": value, "data": data}
            return {
                "ok": False,
                "error": "execute_post_failed",
                "value": value,
                "last_status": resp.status_code,
            }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "value": value}
