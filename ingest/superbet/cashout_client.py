"""Cliente do endpoint de cash-out da Superbet."""
from __future__ import annotations

from typing import Any

import httpx

CASHOUT_BASE = "https://production-superbet-cashout.freetls.fastly.net/cashout/api/v2/requestCashoutValue"


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
    url = f"{CASHOUT_BASE}?target={target}&ticketCode={ticket_code}"
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None
