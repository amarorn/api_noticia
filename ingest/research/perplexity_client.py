"""Cliente Perplexity Sonar — pesquisa web em tempo real para análise pré-jogo."""
from __future__ import annotations

import httpx

from config import settings

_BASE_URL = "https://api.perplexity.ai"
_TIMEOUT = 45.0


class PerplexityError(Exception):
    pass


def search_pregame(home_team: str, away_team: str, extra_context: str = "") -> dict:
    """Consulta Perplexity Sonar sobre o confronto e retorna texto + fontes."""
    if not settings.perplexity_api_key:
        raise PerplexityError("PERPLEXITY_API_KEY não configurada.")

    query = (
        f"{home_team} vs {away_team} Copa do Mundo 2026 análise pré-jogo: "
        f"escalação provável, lesões, suspensões, forma recente, estatísticas, odds."
    )
    if extra_context:
        query += f" {extra_context}"

    payload = {
        "model": settings.perplexity_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Você é um analista esportivo especializado em apostas de futebol. "
                    "Forneça informações objetivas e atuais sobre a partida solicitada. "
                    "Inclua: escalação provável de ambos os times, lesões/suspensões confirmadas, "
                    "últimos 5 resultados de cada time, histórico H2H recente, "
                    "xG médio dos últimos jogos, árbitro designado se disponível, "
                    "e quaisquer informações relevantes para apostas (clima, local, pressão, etc.). "
                    "Seja preciso e cite apenas fatos verificáveis."
                ),
            },
            {"role": "user", "content": query},
        ],
        "search_recency_filter": "week",
        "return_citations": True,
        "return_images": False,
        "temperature": 0.1,
        "max_tokens": 2000,
    }

    headers = {
        "Authorization": f"Bearer {settings.perplexity_api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = httpx.post(
            f"{_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise PerplexityError(f"Perplexity HTTP {exc.response.status_code}: {exc.response.text[:300]}") from exc
    except httpx.RequestError as exc:
        raise PerplexityError(f"Erro de conexão Perplexity: {exc}") from exc

    data = resp.json()
    choice = data["choices"][0]
    text = choice["message"]["content"]
    citations = data.get("citations", [])

    return {
        "text": text,
        "citations": citations,
        "model": data.get("model", settings.perplexity_model),
        "usage": data.get("usage", {}),
    }
