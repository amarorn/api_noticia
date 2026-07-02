"""Copiloto ao vivo em modo agente — LLM orquestra tools sobre o advice quantitativo."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from config import settings
from models.inplay_bet_builder_guard import validate_bet_builder
from models.live_copilot_bilhete import (
    basket_bilhete_candidates,
    football_bilhete_candidates,
)
from models.live_llm_copilot import (
    LiveCopilotError,
    _allowed_keys,
    _basket_candidates,
    _build_context,
    _fallback_from_quant,
    _football_candidates,
    _parse_json,
    _pick_key,
    _validate_llm_payload,
)

_OPENAI_BASE = "https://api.openai.com/v1"
_MAX_HISTORY = 8

_AGENT_SYSTEM = """\
Você é copiloto de apostas in-play em modo AGENTE. Você pode chamar ferramentas para
consultar o motor quantitativo (EV/Kelly) e propor ações na interface.

Regras:
1. SEMPRE use tools antes de recomendar mercados — nunca invente odds ou EV.
2. Só proponha pernas presentes em get_opportunities ou validate_combo aprovado.
3. use set_ui_actions apenas quando tiver plano claro (notify, add_ticket_legs, switch_tab).
4. Responda em português do Brasil, direto e objetivo.
5. Ao finalizar, produza JSON (sem markdown) com:
{
  "reply": "resposta ao usuário (2-5 frases)",
  "momento": "timing do jogo",
  "acao_agora": "apostar|aguardar|cashout",
  "confianca_geral": "Alta|Média|Baixa",
  "picks": [{"rank":1,"market":"...","outcome":"...","label":"...","rationale":"...","confidence":"Alta|Média|Baixa"}],
  "alertas": ["..."],
  "bilhete": null,
  "ui_actions": [{"type":"notify|add_ticket_legs|switch_tab", ...}]
}
Máximo 2 picks. ui_actions opcional."""

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_opportunities",
            "description": "Lista oportunidades aprovadas pelo modelo (EV, odd, edge).",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_strategy_snapshot",
            "description": "Postura, wait_reason, cash-out, placar e minuto.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_combo",
            "description": "Valida pernas de combo (correlação, mercados mortos).",
            "parameters": {
                "type": "object",
                "properties": {
                    "legs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "market": {"type": "string"},
                                "outcome": {"type": "string"},
                                "label": {"type": "string"},
                            },
                            "required": ["market", "outcome"],
                        },
                    }
                },
                "required": ["legs"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_data_quality",
            "description": "Confiança dos dados, stale Superbet, cobertura.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_ui_actions",
            "description": "Registra ações de UI propostas (serão validadas no backend).",
            "parameters": {
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["notify", "add_ticket_legs", "switch_tab"],
                                },
                                "title": {"type": "string"},
                                "body": {"type": "string"},
                                "tab": {"type": "string"},
                                "legs": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "market": {"type": "string"},
                                            "outcome": {"type": "string"},
                                            "label": {"type": "string"},
                                        },
                                        "required": ["market", "outcome"],
                                    },
                                },
                            },
                            "required": ["type"],
                        },
                    }
                },
                "required": ["actions"],
            },
        },
    },
]


def _agent_enabled() -> bool:
    return (
        settings.live_copilot_enabled
        and bool(settings.openai_api_key)
        and settings.live_copilot_mode in {"agent", "autopilot"}
    )


def _parse_score(current_score: str | None) -> tuple[int, int]:
    if not current_score:
        return 0, 0
    parts = re.split(r"[x×:\-]", str(current_score).strip(), maxsplit=1)
    if len(parts) != 2:
        return 0, 0
    try:
        return int(parts[0].strip()), int(parts[1].strip())
    except ValueError:
        return 0, 0


def _tool_get_opportunities(advice: dict[str, Any], *, sport: str) -> dict[str, Any]:
    rows = _football_candidates(advice) if sport != "basketball" else _basket_candidates(advice)
    compact = []
    for row in rows[:8]:
        compact.append({
            "market": row.get("market"),
            "outcome": row.get("outcome"),
            "label": row.get("label"),
            "model_prob": row.get("model_prob"),
            "market_odd": row.get("market_odd"),
            "expected_value": row.get("expected_value"),
            "edge_pp": row.get("edge_pp"),
            "suggested_stake_pct": row.get("suggested_stake_pct"),
            "tier": row.get("tier"),
        })
    return {"count": len(compact), "opportunities": compact}


def _tool_get_strategy_snapshot(advice: dict[str, Any], *, sport: str) -> dict[str, Any]:
    strategy = advice.get("strategy") or {}
    cashout = strategy.get("cashout") or advice.get("cashout")
    out = {
        "partida": f"{advice.get('home_team')} x {advice.get('away_team')}",
        "placar": advice.get("current_score"),
        "minuto": advice.get("minute"),
        "periodo": advice.get("period_label"),
        "postura": strategy.get("posture"),
        "wait_reason": strategy.get("wait_reason"),
        "cashout": cashout,
        "is_live": advice.get("is_live"),
        "is_finished": advice.get("is_finished"),
    }
    if sport == "basketball":
        summary = advice.get("inplay_summary") or {}
        out["projecao_total"] = summary.get("expected_total")
    return out


def _tool_validate_combo(advice: dict[str, Any], *, sport: str, legs: list[dict[str, Any]]) -> dict[str, Any]:
    if sport == "basketball":
        return {"valid": False, "warnings": ["validate_combo disponível só para futebol nesta versão."]}
    hs, as_ = _parse_score(advice.get("current_score"))
    minute = int(advice.get("minute") or 0)
    ht_h = advice.get("ht_home_score")
    ht_a = advice.get("ht_away_score")
    normalized = [
        {"market": str(l.get("market", "")), "outcome": str(l.get("outcome", "")), "label": l.get("label", "")}
        for l in legs
        if l.get("market") and l.get("outcome")
    ]
    return validate_bet_builder(
        normalized,
        minute=minute,
        home_score=hs,
        away_score=as_,
        ht_home=ht_h,
        ht_away=ht_a,
    )


def _tool_get_data_quality(advice: dict[str, Any]) -> dict[str, Any]:
    conf = advice.get("confidence") or {}
    coverage = advice.get("analysis_coverage") or {}
    return {
        "superbet_stale": bool(advice.get("superbet_stale")),
        "confidence_score": conf.get("score"),
        "confidence_label": conf.get("label"),
        "captured_at": advice.get("captured_at"),
        "analysis_coverage": coverage,
        "has_timeline": bool(advice.get("timeline_events") or advice.get("live_timeline")),
    }


def _execute_tool(
    name: str,
    args: dict[str, Any],
    *,
    advice: dict[str, Any],
    sport: str,
    pending_ui_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    if name == "get_opportunities":
        return _tool_get_opportunities(advice, sport=sport)
    if name == "get_strategy_snapshot":
        return _tool_get_strategy_snapshot(advice, sport=sport)
    if name == "validate_combo":
        return _tool_validate_combo(advice, sport=sport, legs=args.get("legs") or [])
    if name == "get_data_quality":
        return _tool_get_data_quality(advice)
    if name == "set_ui_actions":
        actions = args.get("actions") or []
        pending_ui_actions.extend(actions)
        return {"accepted": len(actions), "pending_total": len(pending_ui_actions)}
    return {"error": f"tool desconhecida: {name}"}


def _validate_ui_actions(
    raw_actions: list[dict[str, Any]],
    *,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_key = {_pick_key(str(c.get("market", "")), str(c.get("outcome", ""))): c for c in candidates}
    allowed_tabs = {"resumo", "mercados", "qualidade", "bilhete"}
    out: list[dict[str, Any]] = []

    for action in raw_actions:
        if not isinstance(action, dict):
            continue
        atype = str(action.get("type") or "")
        if atype == "notify":
            title = str(action.get("title") or "Copiloto").strip()[:120]
            body = str(action.get("body") or "").strip()[:400]
            if body:
                out.append({"type": "notify", "title": title, "body": body})
        elif atype == "switch_tab":
            tab = str(action.get("tab") or "resumo").lower()
            if tab in allowed_tabs:
                out.append({"type": "switch_tab", "tab": tab})
        elif atype == "add_ticket_legs":
            validated_legs: list[dict[str, Any]] = []
            for leg in action.get("legs") or []:
                if not isinstance(leg, dict):
                    continue
                key = _pick_key(str(leg.get("market", "")), str(leg.get("outcome", "")))
                src = by_key.get(key)
                if not src:
                    continue
                validated_legs.append({
                    "market": src.get("market"),
                    "outcome": src.get("outcome"),
                    "label": src.get("label") or leg.get("label"),
                    "model_prob": src.get("model_prob"),
                    "market_odd": src.get("market_odd"),
                    "expected_value": src.get("expected_value"),
                    "edge_pp": src.get("edge_pp"),
                    "suggested_stake_pct": src.get("suggested_stake_pct"),
                })
            if validated_legs:
                out.append({"type": "add_ticket_legs", "legs": validated_legs})
    return out[:6]


def _call_openai_agent(messages: list[dict[str, Any]]) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise LiveCopilotError("OPENAI_API_KEY não configurada.")

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.openai_model,
        "messages": messages,
        "tools": _TOOLS,
        "temperature": settings.live_copilot_temperature,
        "max_tokens": settings.live_copilot_max_tokens,
    }
    try:
        resp = httpx.post(
            f"{_OPENAI_BASE}/chat/completions",
            json=payload,
            headers=headers,
            timeout=60.0,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise LiveCopilotError(
            f"OpenAI HTTP {exc.response.status_code}: {exc.response.text[:400]}"
        ) from exc
    except httpx.RequestError as exc:
        raise LiveCopilotError(f"Erro de conexão OpenAI: {exc}") from exc

    return resp.json()


def _extract_final_json(content: str) -> dict[str, Any]:
    try:
        return _parse_json(content)
    except LiveCopilotError:
        return {"reply": content.strip()[:2000]}


def run_live_copilot_agent(
    advice: dict[str, Any],
    *,
    sport: str = "football",
    message: str = "",
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Executa loop agente com tools; retorna reply + copilot validado + ui_actions."""
    event_id = int(advice.get("superbet_event_id") or 0)
    captured_at = datetime.now(UTC).isoformat()
    mode = settings.live_copilot_mode

    base: dict[str, Any] = {
        "mode": mode,
        "enabled": _agent_enabled(),
        "available": False,
        "sport": sport,
        "event_id": event_id,
        "captured_at": captured_at,
        "cached": False,
        "model": None,
        "error": None,
        "reply": "",
        "tools_used": [],
        "ui_actions": [],
        "auto_apply_ui": settings.live_copilot_mode == "autopilot" or settings.live_copilot_auto_ui,
        "wait_reason": None,
        "momento": "",
        "acao_agora": "aguardar",
        "confianca_geral": "Baixa",
        "picks": [],
        "alertas": [],
        "bilhete": None,
    }

    if not _agent_enabled():
        base["error"] = (
            "Modo agente desativado. Defina LIVE_COPILOT_MODE=agent e OPENAI_API_KEY."
        )
        fallback = _fallback_from_quant(advice, sport=sport)
        base.update({k: fallback[k] for k in ("momento", "acao_agora", "confianca_geral", "picks", "alertas", "bilhete")})
        base["reply"] = fallback.get("momento") or "Copiloto em modo narrador — ative LIVE_COPILOT_MODE=agent."
        base["available"] = bool(fallback.get("picks"))
        return base

    context = _build_context(advice, sport=sport)
    candidates = _football_candidates(advice) if sport != "basketball" else _basket_candidates(advice)
    bilhete_candidates = (
        football_bilhete_candidates(advice) if sport != "basketball" else basket_bilhete_candidates(advice)
    )
    allowed = _allowed_keys(candidates)
    base["wait_reason"] = context.get("wait_reason")

    user_text = (message or "").strip() or "Analise o jogo agora e diga o que fazer."
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _AGENT_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Contexto ao vivo (JSON):\n{json.dumps(context, ensure_ascii=False)}\n\n"
                f"Pergunta do apostador: {user_text}"
            ),
        },
    ]

    for item in (history or [])[-_MAX_HISTORY:]:
        role = str(item.get("role") or "user")
        content = str(item.get("content") or "")[:1500]
        if role in {"user", "assistant"} and content:
            messages.insert(-1, {"role": role, "content": content})

    pending_ui: list[dict[str, Any]] = []
    tools_used: list[str] = []
    model_name: str | None = None

    try:
        for _ in range(max(1, settings.live_copilot_max_agent_turns)):
            data = _call_openai_agent(messages)
            model_name = data.get("model", settings.openai_model)
            choice = data["choices"][0]
            finish = choice.get("finish_reason")
            assistant = choice["message"]
            messages.append(assistant)

            if finish == "tool_calls" and assistant.get("tool_calls"):
                for tc in assistant["tool_calls"]:
                    fname = tc["function"]["name"]
                    fargs = json.loads(tc["function"].get("arguments") or "{}")
                    tools_used.append(fname)
                    result = _execute_tool(
                        fname,
                        fargs,
                        advice=advice,
                        sport=sport,
                        pending_ui_actions=pending_ui,
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                continue

            content = assistant.get("content") or ""
            parsed = _extract_final_json(content)
            validated = _validate_llm_payload(
                parsed,
                allowed=allowed,
                candidates=candidates,
                bilhete_candidates=bilhete_candidates,
                advice=advice,
                sport=sport,
            )

            ui_from_llm = parsed.get("ui_actions") if isinstance(parsed.get("ui_actions"), list) else []
            ui_merged = pending_ui + ui_from_llm
            ui_valid = _validate_ui_actions(
                ui_merged,
                candidates=candidates + bilhete_candidates,
            )

            base["reply"] = str(parsed.get("reply") or validated.get("momento") or "").strip()[:2000]
            base.update(validated)
            base["ui_actions"] = ui_valid
            base["tools_used"] = tools_used
            base["model"] = model_name
            base["available"] = True
            return base

        raise LiveCopilotError("Agente excedeu turnos sem resposta final.")

    except LiveCopilotError as exc:
        base["error"] = str(exc)
        fallback = _fallback_from_quant(advice, sport=sport)
        base.update({k: fallback[k] for k in ("momento", "acao_agora", "confianca_geral", "picks", "alertas", "bilhete")})
        base["reply"] = fallback.get("momento") or str(exc)
        base["tools_used"] = tools_used
        base["available"] = bool(fallback.get("picks"))
        return base


__all__ = ["run_live_copilot_agent"]
