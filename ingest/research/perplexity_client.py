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


def search_inplay_context(
    home_team: str,
    away_team: str,
    *,
    competition: str = "Copa do Mundo 2026",
) -> dict:
    """
    Busca contexto para jogo ao vivo via Perplexity: árbitro, forma recente,
    H2H, xG médio e lesões/suspensões. Retorna texto formatado para o
    match_context_parser extrair os campos estruturados.
    """
    if not settings.perplexity_api_key:
        raise PerplexityError("PERPLEXITY_API_KEY não configurada.")

    system_prompt = (
        f"Você é um analista de apostas esportivas. Preencha o relatório abaixo com dados REAIS e ATUAIS "
        f"sobre {home_team} x {away_team} ({competition}). "
        "REGRAS OBRIGATÓRIAS:\n"
        "1. Substitua TODOS os valores entre <> por números reais (sem colchetes, sem chaves, sem aspas).\n"
        "2. Use ponto como separador decimal: 1.82 (não 1,82).\n"
        "3. Mantenha o formato de pipe | exatamente como no modelo.\n"
        "4. Se não souber um valor, estime com base em médias históricas da liga — nunca deixe em branco.\n\n"
        "--- FORMATO OBRIGATÓRIO (copie e preencha) ---\n\n"
        f"ANÁLISE - {home_team} x {away_team}\n\n"
        "ÁRBITRO\n"
        "Árbitro: <nome completo>\n"
        "Media <3.80> cartoes amarelos por jogo nesta temporada\n"
        "Cartoes amarelos | <142> | <3.80>\n"
        "Penaltis marcados | <18> | <0.49>\n\n"
        f"ESTATÍSTICAS {home_team} (últimos 5 jogos)\n"
        "xG (gols esperados) | <1.45>\n"
        "Forma: V D E V V (mais recente primeiro)\n"
        "Gols marcados: <8> (media de <1.60> por jogo)\n"
        "Gols sofridos: <4> (media de <0.80> por jogo)\n\n"
        f"ESTATÍSTICAS {away_team} (últimos 5 jogos)\n"
        "xG (gols esperados) | <1.12>\n"
        "Forma: E V D D V (mais recente primeiro)\n"
        "Gols marcados: <6> (media de <1.20> por jogo)\n"
        "Gols sofridos: <7> (media de <1.40> por jogo)\n\n"
        "CONFRONTOS DIRETOS (H2H)\n"
        "Últimos 5 confrontos:\n"
        "<lista de resultados>\n"
        "Media de <2.40> gols por jogo no histórico recente\n\n"
        "LESÕES E SUSPENSÕES\n"
        f"{home_team}: <lista de ausentes ou 'Nenhuma confirmada'>\n"
        f"{away_team}: <lista de ausentes ou 'Nenhuma confirmada'>\n\n"
        "CONTEXTO\n"
        "<situação no grupo/torneio, o que está em jogo, pressão, clima se relevante>\n\n"
        "--- FIM DO FORMATO ---\n\n"
        "IMPORTANTE: substitua cada <valor> por um número real. Nunca escreva <> no output final."
    )

    payload = {
        "model": settings.perplexity_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Pesquise e preencha a análise de {home_team} x {away_team} "
                    f"em {competition}. Foque em dados atuais e verificáveis."
                ),
            },
        ],
        "search_recency_filter": "week",
        "return_citations": True,
        "return_images": False,
        "temperature": 0.1,
        "max_tokens": 1800,
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
        raise PerplexityError(
            f"Perplexity HTTP {exc.response.status_code}: {exc.response.text[:300]}"
        ) from exc
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
