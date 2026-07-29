"""Copiloto ao vivo via OpenAI — narra oportunidades aprovadas pelo motor quantitativo."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from config import settings
from models.live_copilot_bilhete import (
    basket_bilhete_candidates,
    baseball_bilhete_candidates,
    bilhete_context_baseball,
    bilhete_context_basket,
    bilhete_context_football,
    fallback_bilhete_from_optimizer,
    football_bilhete_candidates,
    validate_copilot_bilhete,
)
from models.live_copilot_cache import get_cached_copilot, set_cached_copilot

_OPENAI_BASE = "https://api.openai.com/v1"
_TIMEOUT = 45.0

_SYSTEM_PROMPT = """\
Você é copiloto de apostas esportivas in-play. Seu papel é interpretar sinais quantitativos
(modelo Poisson/MC, EV, Kelly) e orientar o apostador em português do Brasil.

Regras obrigatórias:
1. Recomende SOMENTE picks presentes em "oportunidades_aprovadas" ou "watch_list".
2. Nunca invente odds, probabilidades ou mercados que não estejam nos dados.
3. Se "wait_reason" existir e não houver oportunidade forte, ação deve ser "aguardar".
4. Se houver cashout crítico nos blindagens, priorize alerta de saída.
5. Seja direto: 1 frase para o momento, picks curtos com racional objetivo.
6. Responda APENAS JSON válido, sem markdown.

Schema exato:
{
  "momento": "frase sobre o timing do jogo agora",
  "acao_agora": "apostar|aguardar|cashout",
  "confianca_geral": "Alta|Média|Baixa",
  "picks": [
    {
      "rank": 1,
      "market": "copiar do dado",
      "outcome": "copiar do dado",
      "label": "copiar do dado",
      "rationale": "1-2 frases objetivas",
      "confidence": "Alta|Média|Baixa"
    }
  ],
  "alertas": ["alerta curto 1", "alerta curto 2"],
  "bilhete": {
    "tipo": "combo|simples|nenhum",
    "titulo": "nome curto do bilhete",
    "resumo": "por que estas pernas juntas",
    "pernas": [
      {
        "rank": 1,
        "market": "copiar do mercados_scan",
        "outcome": "copiar do mercados_scan",
        "label": "copiar do mercados_scan",
        "papel": "ancora|complemento",
        "rationale": "1 frase"
      }
    ],
    "avisos_correlacao": ["evitar X com Y se aplicável"]
  }
}
Máximo 2 picks isolados. Bilhete: 1-4 pernas só de mercados_scan; evite pernas redundantes.
NUNCA recomende next_goal (próximo gol / Nº gol) — variância extrema, fora do escopo do copiloto.
Se bilhetes_otimizados_modelo existir, use como referência mas pode ajustar narrativa.
Se nada combinar, bilhete.tipo=nenhum e pernas=[]."""

_BASEBALL_SYSTEM_SUFFIX = """

Contexto beisebol (MLB/KBO/NPB):
- "entrada" = inning (1–9+); após 5ª entrada mercados F5 estão mortos.
- Runs = "corridas", não gols. Use linguagem de beisebol.
- Respeite bet_guardrails (block_new_bets) e mercados mortos.
- Se cashout.action for cashout/cashout_parcial com trend_influenced, priorize alerta de saída.
- Não recomende highest_inning ou run_n com odd > 15 sem edge explícito no scan.
- Bilhete: ML, run line, total FT, F5 (só até 5I), total por entrada/time."""


class LiveCopilotError(Exception):
    pass


def _pick_key(market: str, outcome: str) -> str:
    return f"{market}:{str(outcome).lower()}"


def _football_candidates(advice: dict[str, Any]) -> list[dict[str, Any]]:
    strategy = advice.get("strategy") or {}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in (strategy.get("opportunities") or [], strategy.get("watch_list") or []):
        for row in source:
            if not isinstance(row, dict):
                continue
            key = _pick_key(str(row.get("market", "")), str(row.get("outcome", "")))
            if not key or key in seen:
                continue
            if str(row.get("market") or "") == "next_goal":
                continue
            if source is strategy.get("watch_list") and not row.get("meets_threshold", True):
                continue
            if row.get("tier") == "abaixo_limiar":
                continue
            seen.add(key)
            out.append(row)
    return out[:8]


def _basket_candidates(advice: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in advice.get("aportes") or []:
        if not isinstance(row, dict):
            continue
        if row.get("action") not in ("apostar", "aporte", "monitorar"):
            continue
        out.append(row)
    return out[:8]


def _baseball_candidates(advice: dict[str, Any]) -> list[dict[str, Any]]:
    strategy = advice.get("strategy") or {}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in (
        strategy.get("opportunities") or [],
        strategy.get("watch_list") or [],
        advice.get("aportes") or [],
    ):
        for row in source:
            if not isinstance(row, dict):
                continue
            market = str(row.get("market") or "")
            outcome = str(row.get("outcome") or "")
            if not market or not outcome:
                continue
            key = _pick_key(market, outcome)
            if key in seen:
                continue
            if source is advice.get("aportes") and row.get("action") not in (
                "apostar",
                "aporte",
                "monitorar",
            ):
                continue
            if source is strategy.get("opportunities") and row.get("tier") == "abaixo_limiar":
                continue
            seen.add(key)
            out.append(row)
    out.sort(key=lambda r: float(r.get("expected_value") or 0), reverse=True)
    return out[:10]


def _aport_sport_candidates(advice: dict[str, Any], *, sport: str) -> list[dict[str, Any]]:
    if sport == "basketball":
        return _basket_candidates(advice)
    if sport == "baseball":
        return _baseball_candidates(advice)
    return _football_candidates(advice)


def _aport_sport_bilhete_candidates(advice: dict[str, Any], *, sport: str) -> list[dict[str, Any]]:
    if sport == "basketball":
        return basket_bilhete_candidates(advice)
    if sport == "baseball":
        return baseball_bilhete_candidates(advice)
    return football_bilhete_candidates(advice)


def _allowed_keys(candidates: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for row in candidates:
        market = str(row.get("market", ""))
        outcome = str(row.get("outcome", ""))
        if market and outcome:
            keys.add(_pick_key(market, outcome))
    return keys


def _build_football_context(advice: dict[str, Any]) -> dict[str, Any]:
    strategy = advice.get("strategy") or {}
    candidates = _football_candidates(advice)
    compact = []
    for row in candidates[:6]:
        compact.append({
            "market": row.get("market"),
            "outcome": row.get("outcome"),
            "label": row.get("label"),
            "tier": row.get("tier"),
            "model_prob": row.get("model_prob"),
            "market_odd": row.get("market_odd"),
            "expected_value": row.get("expected_value"),
            "edge_pp": row.get("edge_pp"),
            "suggested_stake_pct": row.get("suggested_stake_pct"),
            "timing": row.get("timing"),
            "timing_reason": row.get("timing_reason"),
        })
    shields = [
        {"title": s.get("title"), "reason": s.get("reason"), "action": s.get("action")}
        for s in (strategy.get("shields") or [])[:4]
        if isinstance(s, dict)
    ]
    trend = advice.get("trend_report") or {}
    ctx = {
        "sport": "football",
        "partida": f"{advice.get('home_team')} x {advice.get('away_team')}",
        "placar": advice.get("current_score"),
        "minuto": advice.get("minute"),
        "periodo": advice.get("period_label"),
        "postura": strategy.get("posture"),
        "wait_reason": strategy.get("wait_reason"),
        "cashout": strategy.get("cashout") or advice.get("cashout"),
        "confianca_modelo": advice.get("confidence"),
        "oportunidades_aprovadas": compact,
        "watch_list": compact[:3],
        "blindagens": shields,
        "tendencia": {
            "dominant_trend": trend.get("dominant_trend"),
            "position_advice": (trend.get("position_advice") or {}).get("action"),
        },
    }
    ctx.update(bilhete_context_football(advice))
    return ctx


def _build_basket_context(advice: dict[str, Any]) -> dict[str, Any]:
    candidates = _basket_candidates(advice)
    compact = []
    for row in candidates[:6]:
        compact.append({
            "market": row.get("market"),
            "outcome": row.get("outcome"),
            "label": row.get("label"),
            "model_prob": row.get("model_prob"),
            "market_odd": row.get("market_odd"),
            "expected_value": row.get("expected_value"),
            "edge_pp": row.get("edge_pp"),
            "suggested_stake_pct": row.get("suggested_stake_pct"),
            "action": row.get("action"),
        })
    summary = advice.get("inplay_summary") or {}
    ctx = {
        "sport": "basketball",
        "partida": f"{advice.get('home_team')} x {advice.get('away_team')}",
        "placar": advice.get("current_score"),
        "minuto": advice.get("minute"),
        "periodo": advice.get("period_label"),
        "confianca_modelo": advice.get("confidence"),
        "projecao_total": summary.get("expected_total"),
        "spread_mercado": summary.get("market_spread_line"),
        "total_mercado": summary.get("market_total_line"),
        "oportunidades_aprovadas": compact,
        "watch_list": compact[:3],
        "blindagens": [],
    }
    ctx.update(bilhete_context_basket(advice))
    return ctx


def _build_baseball_context(advice: dict[str, Any]) -> dict[str, Any]:
    candidates = _baseball_candidates(advice)
    compact = []
    for row in candidates[:8]:
        compact.append({
            "market": row.get("market"),
            "outcome": row.get("outcome"),
            "label": row.get("label"),
            "tier": row.get("tier"),
            "model_prob": row.get("model_prob"),
            "market_odd": row.get("market_odd"),
            "expected_value": row.get("expected_value"),
            "edge_pp": row.get("edge_pp"),
            "suggested_stake_pct": row.get("suggested_stake_pct"),
            "action": row.get("action"),
        })
    strategy = advice.get("strategy") or {}
    phase = advice.get("game_phase") or {}
    summary = advice.get("inplay_summary") or {}
    guardrails = advice.get("bet_guardrails") or {}
    trend = advice.get("trend_report") or {}
    benchmark = advice.get("market_benchmark") or {}
    shields = [
        {"title": s.get("title"), "reason": s.get("reason"), "action": s.get("action")}
        for s in (strategy.get("shields") or [])[:4]
        if isinstance(s, dict)
    ]
    innings = advice.get("baseball_innings") or []
    ctx = {
        "sport": "baseball",
        "partida": f"{advice.get('home_team')} x {advice.get('away_team')}",
        "placar": advice.get("current_score"),
        "entrada": advice.get("inning") or advice.get("minute"),
        "periodo": advice.get("period_label"),
        "fase": phase.get("label") or phase.get("phase"),
        "postura": strategy.get("posture"),
        "wait_reason": strategy.get("wait_reason"),
        "cashout": strategy.get("cashout") or advice.get("cashout"),
        "trend_report": {
            "dominant_trend": trend.get("dominant_trend"),
            "position_advice": trend.get("position_advice"),
        }
        if trend
        else None,
        "bet_guardrails": {
            "block_new_bets": guardrails.get("block_new_bets"),
            "block_reason": guardrails.get("block_reason"),
            "dead_markets": guardrails.get("dead_markets"),
        },
        "confianca_modelo": advice.get("confidence"),
        "projecao_total": summary.get("expected_total"),
        "rpi_home": summary.get("rpi_home"),
        "rpi_away": summary.get("rpi_away"),
        "score_adapted": summary.get("score_adapted"),
        "spread_mercado": summary.get("market_spread_line"),
        "total_mercado": summary.get("market_total_line"),
        "benchmark_ml": benchmark.get("moneyline"),
        "benchmark_total": benchmark.get("total"),
        "linha_por_entrada": innings[-6:],
        "oportunidades_aprovadas": compact,
        "watch_list": compact[:3],
        "blindagens": shields,
    }
    ctx.update(bilhete_context_baseball(advice))
    return ctx


def _build_context(advice: dict[str, Any], *, sport: str) -> dict[str, Any]:
    if sport == "basketball":
        return _build_basket_context(advice)
    if sport == "baseball":
        return _build_baseball_context(advice)
    return _build_football_context(advice)


def _copilot_cache_key(advice: dict[str, Any], *, sport: str) -> tuple[Any, ...]:
    if sport in {"basketball", "baseball"}:
        top = (_aport_sport_candidates(advice, sport=sport) or [{}])[0]
        key_fields: tuple[Any, ...] = (
            sport,
            advice.get("superbet_event_id"),
            advice.get("current_score"),
            advice.get("minute") or advice.get("inning"),
            top.get("market"),
            top.get("outcome"),
            round(float(top.get("expected_value") or 0), 3),
        )
        if sport == "baseball":
            strategy = advice.get("strategy") or {}
            key_fields = (
                *key_fields,
                strategy.get("posture"),
                (advice.get("cashout") or {}).get("action"),
            )
        return key_fields
    strategy = advice.get("strategy") or {}
    top = (_football_candidates(advice) or [{}])[0]
    return (
        sport,
        advice.get("superbet_event_id"),
        advice.get("current_score"),
        advice.get("minute"),
        strategy.get("posture"),
        top.get("market"),
        top.get("outcome"),
        round(float(top.get("expected_value") or 0), 3),
    )


def _parse_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise LiveCopilotError("Resposta GPT não é JSON válido.") from None


def _call_openai(context: dict[str, Any], *, sport: str = "football") -> dict[str, Any]:
    if not settings.openai_api_key:
        raise LiveCopilotError("OPENAI_API_KEY não configurada.")

    system_prompt = _SYSTEM_PROMPT
    if sport == "baseball":
        system_prompt = f"{_SYSTEM_PROMPT}\n{_BASEBALL_SYSTEM_SUFFIX}"

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Analise o contexto ao vivo abaixo e gere orientação para o apostador.\n\n"
                    f"{json.dumps(context, ensure_ascii=False)}"
                ),
            },
        ],
        "temperature": settings.live_copilot_temperature,
        "max_tokens": settings.live_copilot_max_tokens,
        "response_format": {"type": "json_object"},
    }
    try:
        resp = httpx.post(
            f"{_OPENAI_BASE}/chat/completions",
            json=payload,
            headers=headers,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise LiveCopilotError(
            f"OpenAI HTTP {exc.response.status_code}: {exc.response.text[:400]}"
        ) from exc
    except httpx.RequestError as exc:
        raise LiveCopilotError(f"Erro de conexão OpenAI: {exc}") from exc

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    parsed = _parse_json(content)
    parsed["_model"] = data.get("model", settings.openai_model)
    parsed["_usage"] = data.get("usage", {})
    return parsed


def _validate_llm_payload(
    parsed: dict[str, Any],
    *,
    allowed: set[str],
    candidates: list[dict[str, Any]],
    bilhete_candidates: list[dict[str, Any]],
    advice: dict[str, Any],
    sport: str,
) -> dict[str, Any]:
    by_key = {
        _pick_key(str(c.get("market", "")), str(c.get("outcome", ""))): c for c in candidates
    }
    acao = str(parsed.get("acao_agora") or "aguardar").lower()
    if acao not in {"apostar", "aguardar", "cashout"}:
        acao = "aguardar"

    confianca = str(parsed.get("confianca_geral") or "Média")
    if confianca not in {"Alta", "Média", "Baixa"}:
        confianca = "Média"

    validated_picks: list[dict[str, Any]] = []
    for raw_pick in parsed.get("picks") or []:
        if not isinstance(raw_pick, dict):
            continue
        key = _pick_key(str(raw_pick.get("market", "")), str(raw_pick.get("outcome", "")))
        if key not in allowed:
            continue
        source = by_key.get(key, {})
        conf = str(raw_pick.get("confidence") or "Média")
        if conf not in {"Alta", "Média", "Baixa"}:
            conf = "Média"
        validated_picks.append({
            "rank": int(raw_pick.get("rank") or len(validated_picks) + 1),
            "market": source.get("market") or raw_pick.get("market"),
            "outcome": source.get("outcome") or raw_pick.get("outcome"),
            "label": source.get("label") or raw_pick.get("label"),
            "rationale": str(raw_pick.get("rationale") or "").strip()[:400],
            "confidence": conf,
            "model_prob": source.get("model_prob"),
            "market_odd": source.get("market_odd"),
            "expected_value": source.get("expected_value"),
            "edge_pp": source.get("edge_pp"),
            "suggested_stake_pct": source.get("suggested_stake_pct"),
        })
        if len(validated_picks) >= 2:
            break

    if acao == "apostar" and not validated_picks:
        acao = "aguardar"

    alertas = [
        str(a).strip()[:200]
        for a in (parsed.get("alertas") or [])
        if isinstance(a, str) and a.strip()
    ][:5]

    bilhete = validate_copilot_bilhete(
        parsed,
        candidates=bilhete_candidates,
        advice=advice,
        sport=sport,
    )
    if bilhete is None:
        bilhete = fallback_bilhete_from_optimizer(advice, sport=sport)

    return {
        "momento": str(parsed.get("momento") or "").strip()[:500],
        "acao_agora": acao,
        "confianca_geral": confianca,
        "picks": validated_picks,
        "alertas": alertas,
        "bilhete": bilhete,
    }


def _fallback_from_quant(advice: dict[str, Any], *, sport: str) -> dict[str, Any]:
    if sport == "basketball":
        candidates = _basket_candidates(advice)
        wait_reason = None
        posture = None
    elif sport == "baseball":
        strategy = advice.get("strategy") or {}
        candidates = _baseball_candidates(advice)
        wait_reason = strategy.get("wait_reason")
        posture = strategy.get("posture")
    else:
        strategy = advice.get("strategy") or {}
        candidates = _football_candidates(advice)
        wait_reason = strategy.get("wait_reason")
        posture = strategy.get("posture")

    strong = [c for c in candidates if float(c.get("expected_value") or 0) >= 0.05]
    picks = []
    for idx, row in enumerate(strong[:2], start=1):
        picks.append({
            "rank": idx,
            "market": row.get("market"),
            "outcome": row.get("outcome"),
            "label": row.get("label"),
            "rationale": f"EV {float(row.get('expected_value') or 0):.1%} · edge {float(row.get('edge_pp') or 0):+.1f} pp",
            "confidence": "Alta" if float(row.get("expected_value") or 0) >= 0.12 else "Média",
            "model_prob": row.get("model_prob"),
            "market_odd": row.get("market_odd"),
            "expected_value": row.get("expected_value"),
            "edge_pp": row.get("edge_pp"),
            "suggested_stake_pct": row.get("suggested_stake_pct"),
        })

    if picks:
        acao = "apostar"
        if sport == "baseball":
            inn = advice.get("inning") or advice.get("minute")
            momento = f"{inn}I — {len(picks)} oportunidade(s) com EV positivo."
        else:
            momento = f"{advice.get('minute')}' — {len(picks)} oportunidade(s) com EV positivo."
    elif wait_reason:
        acao = "aguardar"
        momento = str(wait_reason)
    else:
        acao = "aguardar"
        if sport == "baseball":
            inn = advice.get("inning") or advice.get("minute")
            momento = f"{inn}I — aguardar melhor janela de entrada."
        else:
            momento = f"{advice.get('minute')}' — aguardar melhor janela de entrada."

    alertas = []
    if posture:
        alertas.append(f"Postura do plano: {posture}")
    cashout = (advice.get("strategy") or {}).get("cashout") or advice.get("cashout")
    if sport == "baseball" and isinstance(cashout, dict):
        if cashout.get("action") in {"cashout", "cashout_parcial"}:
            alertas.append(f"Cash-out: {cashout.get('reason', '')[:120]}")

    bilhete = fallback_bilhete_from_optimizer(advice, sport=sport)

    return {
        "momento": momento,
        "acao_agora": acao,
        "confianca_geral": "Média",
        "picks": picks,
        "alertas": alertas,
        "bilhete": bilhete,
    }


def run_live_copilot(advice: dict[str, Any], *, sport: str = "football") -> dict[str, Any]:
    """Gera orientação narrativa GPT a partir do payload de advice ao vivo."""
    event_id = int(advice.get("superbet_event_id") or 0)
    captured_at = datetime.now(UTC).isoformat()
    enabled = settings.live_copilot_enabled and bool(settings.openai_api_key)

    base = {
        "enabled": enabled,
        "available": False,
        "sport": sport,
        "event_id": event_id,
        "captured_at": captured_at,
        "cached": False,
        "model": None,
        "error": None,
        "wait_reason": None,
        "momento": "",
        "acao_agora": "aguardar",
        "confianca_geral": "Baixa",
        "picks": [],
        "alertas": [],
        "bilhete": None,
    }

    if not enabled:
        base["error"] = "Copiloto desativado ou OPENAI_API_KEY ausente."
        fallback = _fallback_from_quant(advice, sport=sport)
        base.update(fallback)
        base["available"] = bool(fallback.get("picks"))
        return base

    cache_key = _copilot_cache_key(advice, sport=sport)
    cached = get_cached_copilot(cache_key)
    if cached is not None:
        cached["cached"] = True
        return cached

    context = _build_context(advice, sport=sport)
    candidates = _aport_sport_candidates(advice, sport=sport)
    bilhete_candidates = _aport_sport_bilhete_candidates(advice, sport=sport)
    allowed = _allowed_keys(candidates)
    base["wait_reason"] = context.get("wait_reason")

    try:
        llm_raw = _call_openai(context, sport=sport)
        validated = _validate_llm_payload(
            llm_raw,
            allowed=allowed,
            candidates=candidates,
            bilhete_candidates=bilhete_candidates,
            advice=advice,
            sport=sport,
        )
        base.update(validated)
        base["model"] = llm_raw.get("_model")
        base["available"] = True
    except LiveCopilotError as exc:
        base["error"] = str(exc)
        fallback = _fallback_from_quant(advice, sport=sport)
        base.update(fallback)
        base["available"] = bool(fallback.get("picks"))

    set_cached_copilot(cache_key, base, ttl_sec=float(settings.live_copilot_cache_ttl_sec))
    return base


def warm_live_copilot(advice: dict[str, Any], *, sport: str = "football") -> dict[str, Any] | None:
    """Pré-aquece cache GPT durante o poll ao vivo (best-effort)."""
    import logging

    logger = logging.getLogger(__name__)
    if not settings.live_copilot_enabled or not settings.live_copilot_poll_enabled:
        return None
    if not settings.openai_api_key:
        return None
    if not advice.get("is_live") or advice.get("is_finished"):
        return None
    try:
        return run_live_copilot(advice, sport=sport)
    except Exception as exc:
        logger.warning(
            "copilot_warm_falha event_id=%s: %s",
            advice.get("superbet_event_id"),
            exc,
        )
        return None


__all__ = ["LiveCopilotError", "run_live_copilot", "warm_live_copilot"]
