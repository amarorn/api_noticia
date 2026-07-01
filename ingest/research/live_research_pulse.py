"""Live Research Pulse — deep research em tempo real durante eventos críticos do jogo."""
from __future__ import annotations

import json
import time
from typing import Any

import httpx

from config import settings

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_TIMEOUT = 60.0
_LIVE_CACHE_TTL_SEC = 120  # 2 minutos entre pesquisas ao vivo


class LiveResearchError(Exception):
    pass


_LIVE_SYSTEM_PROMPT = """\
Você é um analista quantitativo sênior de apostas esportivas ao vivo.
A partida está EM ANDAMENTO. Use busca no Google para obter informações ATUAIS sobre eventos recentes.

Retorne SOMENTE um JSON válido (sem markdown, sem texto extra) com esta estrutura:
{
  "eventos_detectados": [
    {
      "tipo": "lesao|substituicao|cartao_vermelho|gol_controverso|clima|motivacional|tatico",
      "descricao": "descrição curta do evento",
      "jogador_envolvido": "nome do jogador ou null",
      "time_afetado": "home|away|ambos",
      "minuto_aproximado": 0,
      "impacto_estimado": {
        "ataque_pct": 0,
        "defesa_pct": 0,
        "confianca_pct": 0,
        "gols_esperados_delta": 0.0
      }
    }
  ],
  "alertas_ao_vivo": ["alerta1", "alerta2"],
  "recomendacao_modelo": "aumentar|diminuir|manter",
  "confianca_alteracao": "Alta|Média|Baixa",
  "justificativa": "por que o modelo deve ajustar"
}

Regras de impacto:
- Lesão jogador chave (atacante/meia): ataque -15%, defesa -5%, gols_esperados_delta -0.3
- Lesão goleiro/zagueiro: defesa -12%, confianca -10%
- Cartão vermelho: ataque -20% time, defesa +15% adversário
- Substituição ofensiva (3+ atacantes): ataque +10%, gols_esperados_delta +0.2
- Substituição defensiva (5+ defensores): ataque -8%, defesa +10%
- Chuva forte: gols_esperados_delta -0.2, escanteios +15%
- Torcida hostil/pressão: confianca -8% time visitante
"""


# Cache simples em memória: event_id -> (timestamp, resultado)
_live_research_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _get_cached(event_id: str) -> dict[str, Any] | None:
    """Retorna resultado cacheado se ainda válido."""
    if event_id not in _live_research_cache:
        return None
    ts, result = _live_research_cache[event_id]
    if time.time() - ts > _LIVE_CACHE_TTL_SEC:
        return None
    return result


def _set_cached(event_id: str, result: dict[str, Any]) -> None:
    """Armazena resultado no cache."""
    _live_research_cache[event_id] = (time.time(), result)


def _build_live_query(
    home_team: str,
    away_team: str,
    minute: int,
    home_score: int,
    away_score: int,
    recent_events: list[dict[str, Any]] | None = None,
) -> str:
    """Constrói query de pesquisa ao vivo com contexto atual."""
    query = (
        f"{home_team} vs {away_team} ao vivo minuto {minute} "
        f"placar {home_score}-{away_score} "
        f"eventos recentes lesões substituições cartões"
    )
    if recent_events:
        eventos_str = ", ".join(
            f"{e.get('type', '?')} min {e.get('minute', '?')}"
            for e in recent_events[-3:]  # últimos 3 eventos
        )
        query += f". Eventos detectados: {eventos_str}"
    return query


def _call_gemini_live(query: str) -> dict[str, Any]:
    """Chama Gemini com search grounding para pesquisa ao vivo."""
    api_key = settings.gemini_api_key
    if not api_key:
        raise LiveResearchError("GEMINI_API_KEY não configurada.")

    model = getattr(settings, "gemini_model", "gemini-2.5-flash-preview-05-20")
    url = f"{_BASE_URL}/{model}:generateContent?key={api_key}"

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": _LIVE_SYSTEM_PROMPT},
                    {"text": f"Pesquise no Google e analise: {query}"},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1500,
            "responseMimeType": "application/json",
        },
        "tools": [{"googleSearch": {}}],
    }

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise LiveResearchError("Quota Gemini esgotada (429).") from exc
        raise LiveResearchError(f"Gemini HTTP {exc.response.status_code}: {exc.response.text[:200]}") from exc
    except Exception as exc:
        raise LiveResearchError(f"Erro Gemini: {exc}") from exc

    # Extrai texto da resposta
    candidates = data.get("candidates", [])
    if not candidates:
        raise LiveResearchError("Resposta Gemini vazia (sem candidates).")

    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise LiveResearchError("Resposta Gemini vazia (sem parts).")

    raw_text = parts[0].get("text", "")
    if not raw_text:
        raise LiveResearchError("Resposta Gemini vazia (sem texto).")

    # Limpa markdown
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LiveResearchError(f"JSON inválido: {text[:200]}...") from exc

    return parsed


def live_research_pulse(
    event_id: str,
    home_team: str,
    away_team: str,
    minute: int,
    home_score: int,
    away_score: int,
    recent_events: list[dict[str, Any]] | None = None,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Executa deep research ao vivo durante eventos críticos.

    Args:
        event_id: ID do evento Superbet/Sofascore
        home_team, away_team: Nomes dos times
        minute: Minuto atual do jogo
        home_score, away_score: Placar atual
        recent_events: Lista de eventos recentes (gols, cartões, etc.)
        force: Ignora cache

    Returns:
        Dict com eventos_detectados, alertas, recomendação de ajuste do modelo
    """
    # Cache
    if not force:
        cached = _get_cached(event_id)
        if cached is not None:
            return {**cached, "_cached": True}

    # Só pesquisa em momentos críticos (evita spam)
    if minute < 10 and not force:
        return {
            "eventos_detectados": [],
            "alertas_ao_vivo": [],
            "recomendacao_modelo": "manter",
            "confianca_alteracao": "Baixa",
            "justificativa": "Jogo no início, sem eventos críticos suficientes.",
            "_cached": False,
        }

    query = _build_live_query(home_team, away_team, minute, home_score, away_score, recent_events)

    try:
        result = _call_gemini_live(query)
    except LiveResearchError as exc:
        # Fallback: retorna estrutura vazia com erro documentado
        return {
            "eventos_detectados": [],
            "alertas_ao_vivo": [f"Erro research: {exc}"],
            "recomendacao_modelo": "manter",
            "confianca_alteracao": "Baixa",
            "justificativa": f"Falha na pesquisa ao vivo: {exc}. Usando modelo sem ajuste.",
            "_error": str(exc),
            "_cached": False,
        }

    result["_cached"] = False
    _set_cached(event_id, result)
    return result


def apply_live_research_to_lambda(
    lam_h: float,
    lam_a: float,
    research_result: dict[str, Any],
) -> tuple[float, float, list[str]]:
    """Aplica impactos do live research aos lambdas do modelo.

    Lógica:
    - ataque_pct positivo -> time marca MAIS gols -> λ aumenta
    - ataque_pct negativo -> time marca MENOS gols -> λ diminui
    - defesa_pct positivo -> time sofre MENOS gols -> λ adversário diminui
    - defesa_pct negativo -> time sofre MAIS gols -> λ adversário aumenta
    - gols_esperados_delta -> adiciona ao λ do time afetado

    Returns:
        (lam_h_ajustado, lam_a_ajustado, lista de alertas aplicados)
    """
    alerts: list[str] = []
    lam_h_new, lam_a_new = lam_h, lam_a

    for evento in research_result.get("eventos_detectados", []):
        impacto = evento.get("impacto_estimado", {})
        time_afetado = evento.get("time_afetado", "ambos")
        tipo = evento.get("tipo", "")

        ataque_pct = impacto.get("ataque_pct", 0)
        defesa_pct = impacto.get("defesa_pct", 0)
        gols_delta = impacto.get("gols_esperados_delta", 0.0)

        # Time HOME afetado
        if time_afetado == "home" or time_afetado == "ambos":
            # Ataque home -> afeta λ home (gols que home marca)
            if ataque_pct != 0:
                lam_h_new *= (1 + ataque_pct / 100)
                alerts.append(f"{tipo} home: ataque {ataque_pct:+d}%")
            # Defesa home -> afeta λ away (gols que away marca contra home)
            if defesa_pct != 0:
                # defesa positiva = home defende melhor = away marca menos
                lam_a_new *= (1 - defesa_pct / 100)
                alerts.append(f"{tipo} home defesa: away λ {defesa_pct:+d}%")
            # Gols esperados delta -> afeta λ home
            if gols_delta != 0:
                lam_h_new += gols_delta
                alerts.append(f"{tipo} home: gols Δ {gols_delta:+.2f}")

        # Time AWAY afetado
        if time_afetado == "away" or time_afetado == "ambos":
            # Ataque away -> afeta λ away (gols que away marca)
            if ataque_pct != 0:
                lam_a_new *= (1 + ataque_pct / 100)
                alerts.append(f"{tipo} away: ataque {ataque_pct:+d}%")
            # Defesa away -> afeta λ home (gols que home marca contra away)
            if defesa_pct != 0:
                # defesa positiva = away defende melhor = home marca menos
                lam_h_new *= (1 - defesa_pct / 100)
                alerts.append(f"{tipo} away defesa: home λ {defesa_pct:+d}%")
            # Gols esperados delta -> afeta λ away
            if gols_delta != 0:
                lam_a_new += gols_delta
                alerts.append(f"{tipo} away: gols Δ {gols_delta:+.2f}")

    # Clamp para evitar valores absurdos
    lam_h_new = max(0.05, min(lam_h_new, 5.0))
    lam_a_new = max(0.05, min(lam_a_new, 5.0))

    return lam_h_new, lam_a_new, alerts
