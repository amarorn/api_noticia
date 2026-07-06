"""Copiloto e resumo IA para análise pré-jogo (modelo WC + Deep Research opcional)."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from config import settings
from models.live_llm_copilot import LiveCopilotError, _parse_json

_OPENAI_BASE = "https://api.openai.com/v1"
_TIMEOUT = 45.0
_MAX_HISTORY = 8

_PREGAME_NARRATE_SYSTEM = """\
Você é copiloto de apostas PRÉ-JOGO para a Copa do Mundo. Interprete probabilidades
do modelo estatístico e, se houver, insights de pesquisa (escalações, lesões, notícias).

Regras:
1. Não invente odds ou probabilidades — use só os dados fornecidos.
2. Explique por que a confiança é alta/média/baixa (jogo equilibrado, empate provável, etc.).
3. Se research discordar do modelo, mencione o alerta.
4. Responda APENAS JSON válido em português do Brasil:

{
  "momento": "Pré-jogo · contexto do confronto em 1 frase",
  "acao_agora": "apostar|aguardar|evitar",
  "confianca_geral": "Alta|Média|Baixa",
  "picks": [{"rank":1,"market":"...","outcome":"...","label":"...","rationale":"...","confidence":"Alta|Média|Baixa"}],
  "alertas": ["..."],
  "bilhete": {"tipo":"combo|simples|nenhum","titulo":"","resumo":"","pernas":[],"avisos_correlacao":[]}
}
Máximo 2 picks. acao_agora=aguardar se confiança Baixa e jogo equilibrado.
NUNCA recomende mercado next_goal (próximo gol / Nº gol) — variância extrema, fora do escopo pré-jogo."""

_AGENT_SYSTEM = """\
Você é copiloto pré-jogo em modo AGENTE. Use tools para consultar modelo e research
antes de recomendar. Pode propor switch_tab (bilhete|research|picks) via set_ui_actions.

JSON final (sem markdown):
{
  "reply": "resposta 2-5 frases",
  "momento": "...",
  "acao_agora": "apostar|aguardar|evitar",
  "confianca_geral": "Alta|Média|Baixa",
  "picks": [...],
  "alertas": [...],
  "bilhete": null,
  "ui_actions": [{"type":"notify|switch_tab","message":"...","tab":"research|bilhete|picks"}]
}"""

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_model_analysis",
            "description": "Probabilidades 1X2, ticket, picks e xG do modelo WC.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_research_insights",
            "description": "Resumo Deep Research: lesões, escalações, alertas (se disponível).",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_ui_actions",
            "description": "Ações de UI: notify ou switch_tab.",
            "parameters": {
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "enum": ["notify", "switch_tab"]},
                                "message": {"type": "string"},
                                "tab": {"type": "string", "enum": ["bilhete", "research", "picks", "resumo"]},
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


def _enabled() -> bool:
    return bool(settings.live_copilot_enabled and settings.openai_api_key)


def _compact_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    ticket = analysis.get("ticket") or {}
    return {
        "home_team": analysis.get("home_team"),
        "away_team": analysis.get("away_team"),
        "phase": analysis.get("phase"),
        "kickoff_local": analysis.get("kickoff_local"),
        "prob_home": analysis.get("prob_home"),
        "prob_draw": analysis.get("prob_draw"),
        "prob_away": analysis.get("prob_away"),
        "confidence": analysis.get("confidence"),
        "prediction": analysis.get("prediction"),
        "expected_goals": analysis.get("expected_goals"),
        "poisson_score": analysis.get("poisson_score"),
        "h2h_summary": analysis.get("h2h_summary"),
        "top_scorelines": (analysis.get("top_scorelines") or [])[:4],
        "ticket_singles": ticket.get("singles", [])[:3],
        "ticket_combo": ticket.get("combo"),
    }


def _compact_research(synthesis: dict[str, Any] | None) -> dict[str, Any] | None:
    if not synthesis:
        return None
    return {
        "resumo_executivo": synthesis.get("resumo_executivo"),
        "favorito": synthesis.get("favorito"),
        "confianca_geral": synthesis.get("confianca_geral"),
        "principais_fatores": (synthesis.get("principais_fatores") or [])[:5],
        "alertas_risco": (synthesis.get("alertas_risco") or [])[:5],
        "picks_recomendados": (synthesis.get("picks_recomendados") or [])[:3],
        "placar_provavel": synthesis.get("placar_provavel"),
    }


def fallback_pregame_summary(
    analysis: dict[str, Any],
    synthesis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resumo determinístico quando OpenAI indisponível."""
    home = analysis.get("home_team", "Mandante")
    away = analysis.get("away_team", "Visitante")
    ph = float(analysis.get("prob_home") or 0)
    pd = float(analysis.get("prob_draw") or 0)
    pa = float(analysis.get("prob_away") or 0)
    conf = float(analysis.get("confidence") or 0)
    spread = max(ph, pa) - min(ph, pa)

    if spread < 0.08:
        narrative = (
            f"Confronto muito equilibrado entre {home} e {away} "
            f"({ph:.0%} / {pd:.0%} / {pa:.0%}). O modelo não identifica favorito claro — "
            "combos de resultado + gols tendem a ter probabilidade baixa."
        )
        confianca = "Baixa"
        acao = "aguardar"
    elif pd >= 0.28:
        narrative = (
            f"Empate com peso relevante ({pd:.0%}). {home} x {away} pode ser truncado; "
            "mercados de gols ou dupla chance podem fazer mais sentido que vitória seca."
        )
        confianca = "Média" if conf >= 0.45 else "Baixa"
        acao = "aguardar" if confianca == "Baixa" else "apostar"
    else:
        fav = home if ph >= pa else away
        fav_p = max(ph, pa)
        narrative = (
            f"Leve favoritismo de {fav} ({fav_p:.0%}). xG esperado {analysis.get('expected_goals', '—')}. "
            f"Placar Poisson mais provável: {analysis.get('poisson_score', '—')}."
        )
        confianca = "Alta" if fav_p >= 0.55 and conf >= 0.5 else "Média" if fav_p >= 0.45 else "Baixa"
        acao = "apostar" if confianca != "Baixa" else "aguardar"

    alertas: list[str] = []
    combo = (analysis.get("ticket") or {}).get("combo")
    if combo and combo.get("confidence") == "Baixa":
        alertas.append(
            f"Combo principal ({combo.get('label')}) com apenas "
            f"{combo.get('model_prob', 0):.0%} de probabilidade — stake conservador."
        )

    modelo_vs = None
    if synthesis:
        syn_fav = str(synthesis.get("favorito") or "").strip()
        model_side = home if ph >= pa else away
        if syn_fav and syn_fav in (home, away) and syn_fav != model_side and spread < 0.15:
            modelo_vs = f"Pesquisa favorece {syn_fav}; modelo inclina {model_side} ({max(ph, pa):.0%})."
            alertas.append(modelo_vs)
        for r in (synthesis.get("alertas_risco") or [])[:2]:
            if r not in alertas:
                alertas.append(r)

    return {
        "enabled": True,
        "home_team": home,
        "away_team": away,
        "narrative": narrative,
        "confianca": synthesis.get("confianca_geral") if synthesis else confianca,
        "acao_sugerida": acao,
        "alertas": alertas[:4],
        "modelo_vs_noticias": modelo_vs,
        "from_cache": False,
        "provider": "local",
    }


def generate_pregame_summary(
    analysis: dict[str, Any],
    synthesis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not _enabled():
        out = fallback_pregame_summary(analysis, synthesis)
        out["enabled"] = False
        out["error"] = "Copiloto desativado ou OPENAI_API_KEY ausente."
        return out

    payload = {
        "analise_modelo": _compact_analysis(analysis),
        "research": _compact_research(synthesis),
    }
    user_msg = (
        "Gere um resumo curto (3-4 frases) para exibir na aba Bilhete pré-jogo. "
        "Inclua confiança, se vale apostar ou aguardar, e alertas. JSON:\n"
        '{"narrative":"...","confianca":"Alta|Média|Baixa","acao_sugerida":"apostar|aguardar|evitar",'
        '"alertas":["..."],"modelo_vs_noticias":null ou "texto se discordar"}'
        f"\n\nDados:\n{json.dumps(payload, ensure_ascii=False)}"
    )

    try:
        raw = _openai_chat(
            [
                {"role": "system", "content": "Você resume análise pré-jogo de apostas. Só JSON."},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.25,
            max_tokens=600,
        )
        parsed = _parse_json(raw)
        return {
            "enabled": True,
            "home_team": analysis.get("home_team"),
            "away_team": analysis.get("away_team"),
            "narrative": str(parsed.get("narrative") or parsed.get("resumo") or ""),
            "confianca": str(parsed.get("confianca") or parsed.get("confianca_geral") or "Média"),
            "acao_sugerida": str(parsed.get("acao_sugerida") or "aguardar"),
            "alertas": list(parsed.get("alertas") or [])[:4],
            "modelo_vs_noticias": parsed.get("modelo_vs_noticias"),
            "from_cache": False,
            "provider": f"openai:{settings.openai_model}",
        }
    except LiveCopilotError:
        return fallback_pregame_summary(analysis, synthesis)


def _picks_from_analysis(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    picks: list[dict[str, Any]] = []
    ticket = analysis.get("ticket") or {}
    for i, s in enumerate(ticket.get("singles") or []):
        picks.append(
            {
                "rank": i + 1,
                "market": s.get("market", ""),
                "outcome": s.get("market", ""),
                "label": s.get("label", ""),
                "rationale": f"Prob. modelo {s.get('model_prob', 0):.0%}",
                "confidence": s.get("confidence", "Baixa"),
                "model_prob": s.get("model_prob"),
            }
        )
    return picks[:2]


def _normalize_h2h_shorthand(market: str, outcome: str, label: str) -> tuple[str, str, str]:
    """Corrige saída LLM onde market='2' e outcome='Vitória Marrocos'."""
    m = market.strip()
    o = outcome.strip()
    lb = label.strip()
    if m in {"1", "2", "X"} and o and o not in {"1", "2", "X", "yes", "no"}:
        return "h2h", m, lb or o
    if m in {"1", "2", "X"} and (not o or o in {"1", "2", "X"}):
        return "h2h", m, lb or o or m
    if m == "h2h" and not lb:
        return m, o, o
    return m, o, lb or o or m


def _normalize_pregame_pick(raw: dict[str, Any], rank: int) -> dict[str, Any]:
    market, outcome, label = _normalize_h2h_shorthand(
        str(raw.get("market") or ""),
        str(raw.get("outcome") or ""),
        str(raw.get("label") or ""),
    )
    conf = str(raw.get("confidence") or "Média")
    if conf not in {"Alta", "Média", "Baixa"}:
        conf = "Média"
    return {
        "rank": int(raw.get("rank") or rank),
        "market": market,
        "outcome": outcome or market,
        "label": label[:120],
        "rationale": str(raw.get("rationale") or "").strip()[:400],
        "confidence": conf,
        "model_prob": raw.get("model_prob"),
        "market_odd": raw.get("market_odd"),
        "expected_value": raw.get("expected_value"),
        "edge_pp": raw.get("edge_pp"),
        "suggested_stake_pct": raw.get("suggested_stake_pct"),
    }


def _normalize_pregame_picks(raw_picks: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_picks, list):
        return []
    out: list[dict[str, Any]] = []
    for i, raw in enumerate(raw_picks):
        if not isinstance(raw, dict):
            continue
        out.append(_normalize_pregame_pick(raw, i + 1))
        if len(out) >= 2:
            break
    return out


def _normalize_pregame_bilhete(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    tipo = str(raw.get("tipo") or "nenhum").lower()
    if tipo not in {"combo", "simples", "nenhum"}:
        tipo = "nenhum"

    pernas: list[dict[str, Any]] = []
    for i, leg in enumerate(raw.get("pernas") or []):
        if not isinstance(leg, dict):
            continue
        market, outcome, label = _normalize_h2h_shorthand(
            str(leg.get("market") or ""),
            str(leg.get("outcome") or ""),
            str(leg.get("label") or ""),
        )
        if not market:
            continue
        papel = str(leg.get("papel") or ("ancora" if i == 0 else "complemento")).lower()
        if papel not in {"ancora", "complemento"}:
            papel = "ancora" if i == 0 else "complemento"
        pernas.append(
            {
                "rank": int(leg.get("rank") or i + 1),
                "market": market,
                "outcome": outcome or market,
                "label": label[:120],
                "papel": papel,
                "rationale": str(leg.get("rationale") or "").strip()[:300],
                "market_odd": leg.get("market_odd"),
                "model_prob": leg.get("model_prob"),
                "expected_value": leg.get("expected_value"),
                "edge_pp": leg.get("edge_pp"),
            }
        )
        if len(pernas) >= 4:
            break

    if tipo == "nenhum" or not pernas:
        return {
            "tipo": "nenhum",
            "titulo": str(raw.get("titulo") or "Sem combo recomendado")[:120],
            "resumo": str(raw.get("resumo") or "").strip()[:400],
            "pernas": [],
            "valid": False,
            "avisos_correlacao": [],
            "validation_warnings": [],
            "combined_odd": None,
            "combined_odd_simple": None,
            "pricing_mode": None,
        }

    avisos = [
        str(a).strip()[:200]
        for a in (raw.get("avisos_correlacao") or [])
        if isinstance(a, str) and a.strip()
    ][:4]

    return {
        "tipo": "simples" if len(pernas) == 1 else "combo",
        "titulo": str(raw.get("titulo") or "Bilhete sugerido")[:120],
        "resumo": str(raw.get("resumo") or "").strip()[:400],
        "pernas": pernas if tipo != "simples" else pernas[:1],
        "valid": len(pernas) >= 1,
        "avisos_correlacao": avisos,
        "validation_warnings": [],
        "combined_odd": raw.get("combined_odd"),
        "combined_odd_simple": raw.get("combined_odd_simple"),
        "pricing_mode": raw.get("pricing_mode"),
    }


def _sanitize_pregame_copilot_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Garante campos obrigatórios do schema LiveCopilotResponse após saída LLM."""
    acao = str(payload.get("acao_agora") or "aguardar").lower()
    if acao not in {"apostar", "aguardar", "cashout", "evitar"}:
        acao = "aguardar"
    conf = str(payload.get("confianca_geral") or "Média")
    if conf not in {"Alta", "Média", "Baixa"}:
        conf = "Média"

    picks = _normalize_pregame_picks(payload.get("picks"))
    if not picks and payload.get("picks"):
        picks = _picks_from_analysis(payload.get("_analysis_fallback") or {})

    bilhete = _normalize_pregame_bilhete(payload.get("bilhete"))
    alertas = [
        str(a).strip()[:200]
        for a in (payload.get("alertas") or [])
        if isinstance(a, str) and a.strip()
    ][:5]

    out = {k: v for k, v in payload.items() if not str(k).startswith("_")}
    return {
        **out,
        "acao_agora": acao,
        "confianca_geral": conf,
        "picks": picks,
        "alertas": alertas,
        "bilhete": bilhete,
    }


def _fallback_copilot(analysis: dict[str, Any], synthesis: dict[str, Any] | None) -> dict[str, Any]:
    summary = fallback_pregame_summary(analysis, synthesis)
    combo = (analysis.get("ticket") or {}).get("combo")
    bilhete = None
    if combo:
        bilhete = {
            "tipo": "combo",
            "titulo": combo.get("label", ""),
            "resumo": summary["narrative"][:200],
            "pernas": [],
            "valid": combo.get("confidence") != "Baixa",
            "combined_odd": combo.get("fair_odd"),
        }
    out = {
        "enabled": True,
        "available": True,
        "sport": "football",
        "event_id": 0,
        "cached": False,
        "model": "local",
        "momento": f"Pré-jogo · {analysis.get('home_team')} x {analysis.get('away_team')}",
        "acao_agora": summary["acao_sugerida"],
        "confianca_geral": summary["confianca"],
        "picks": _picks_from_analysis(analysis),
        "alertas": summary["alertas"],
        "bilhete": bilhete,
    }
    return _sanitize_pregame_copilot_payload({**out, "_analysis_fallback": analysis})


def run_pregame_copilot(
    analysis: dict[str, Any],
    synthesis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not _enabled():
        out = _fallback_copilot(analysis, synthesis)
        out["enabled"] = False
        out["error"] = "Copiloto desativado ou OPENAI_API_KEY ausente."
        return out

    ctx = {
        "analise_modelo": _compact_analysis(analysis),
        "research": _compact_research(synthesis),
    }
    try:
        raw = _openai_chat(
            [
                {"role": "system", "content": _PREGAME_NARRATE_SYSTEM},
                {"role": "user", "content": json.dumps(ctx, ensure_ascii=False)},
            ],
            temperature=settings.live_copilot_temperature,
            max_tokens=settings.live_copilot_max_tokens,
        )
        parsed = _parse_json(raw)
        base = _fallback_copilot(analysis, synthesis)
        base.update(
            {
                "available": True,
                "model": settings.openai_model,
                "momento": parsed.get("momento") or base["momento"],
                "acao_agora": parsed.get("acao_agora") or base["acao_agora"],
                "confianca_geral": parsed.get("confianca_geral") or base["confianca_geral"],
                "picks": parsed.get("picks") or base["picks"],
                "alertas": parsed.get("alertas") or base["alertas"],
                "bilhete": parsed.get("bilhete") or base["bilhete"],
            }
        )
        return _sanitize_pregame_copilot_payload({**base, "_analysis_fallback": analysis})
    except LiveCopilotError:
        return _fallback_copilot(analysis, synthesis)


def run_pregame_copilot_agent(
    analysis: dict[str, Any],
    synthesis: dict[str, Any] | None,
    message: str,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    base = run_pregame_copilot(analysis, synthesis)
    mode = settings.live_copilot_mode

    if not _enabled() or mode not in {"agent", "autopilot"}:
        reply = base.get("momento") or "Copiloto em modo narrador."
        if mode not in {"agent", "autopilot"}:
            reply = "Ative LIVE_COPILOT_MODE=agent para chat interativo."
        return {
            **base,
            "reply": reply,
            "mode": mode,
            "ui_actions": [],
            "auto_apply_ui": False,
        }

    ctx_store = {"analysis": _compact_analysis(analysis), "research": _compact_research(synthesis)}
    pending_ui: list[dict[str, Any]] = []

    def _tool(name: str, _args: dict[str, Any]) -> str:
        if name == "get_model_analysis":
            return json.dumps(ctx_store["analysis"], ensure_ascii=False)
        if name == "get_research_insights":
            return json.dumps(ctx_store["research"] or {"disponivel": False}, ensure_ascii=False)
        if name == "set_ui_actions":
            pending_ui.extend(_args.get("actions") or [])
            return json.dumps({"ok": True, "count": len(pending_ui)})
        return json.dumps({"error": "tool desconhecida"})

    messages: list[dict[str, Any]] = [{"role": "system", "content": _AGENT_SYSTEM}]
    for h in (history or [])[-_MAX_HISTORY:]:
        messages.append({"role": h["role"], "content": h["content"][:1500]})
    messages.append({"role": "user", "content": message[:2000]})

    try:
        for _ in range(max(1, settings.live_copilot_max_agent_turns)):
            resp = _openai_chat(messages, tools=_TOOLS, temperature=0.2, max_tokens=900, raw=True)
            choice = resp["choices"][0]["message"]
            if choice.get("tool_calls"):
                messages.append(choice)
                for tc in choice["tool_calls"]:
                    fn = tc.get("function") or {}
                    name = fn.get("name", "")
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    result = _tool(name, args)
                    messages.append(
                        {"role": "tool", "tool_call_id": tc["id"], "content": result}
                    )
                continue

            content = choice.get("content") or ""
            parsed = _parse_json(content)
            out = {
                **base,
                "reply": parsed.get("reply") or content[:500],
                "momento": parsed.get("momento") or base["momento"],
                "acao_agora": parsed.get("acao_agora") or base["acao_agora"],
                "confianca_geral": parsed.get("confianca_geral") or base["confianca_geral"],
                "picks": parsed.get("picks") or base["picks"],
                "alertas": parsed.get("alertas") or base["alertas"],
                "bilhete": parsed.get("bilhete") or base.get("bilhete"),
                "mode": "agent",
                "ui_actions": _sanitize_ui_actions(pending_ui or parsed.get("ui_actions") or []),
                "auto_apply_ui": settings.live_copilot_mode == "autopilot"
                or settings.live_copilot_auto_ui,
            }
            return out

        raise LiveCopilotError("Agente excedeu turnos sem resposta final.")
    except LiveCopilotError as exc:
        return {
            **base,
            "reply": str(exc),
            "mode": "agent",
            "ui_actions": [],
            "auto_apply_ui": False,
            "error": str(exc),
        }


def _sanitize_ui_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    allowed_tabs = {"bilhete", "research", "picks", "resumo", "placar", "h2h", "contexto"}
    out: list[dict[str, Any]] = []
    for a in actions[:5]:
        t = a.get("type")
        if t not in ("notify", "switch_tab"):
            continue
        item: dict[str, Any] = {"type": t, "legs": []}
        if t == "notify":
            body = str(a.get("body") or a.get("message") or "")[:400]
            if body:
                item["title"] = str(a.get("title") or "Copiloto pré-jogo")[:120]
                item["body"] = body
        if t == "switch_tab" and a.get("tab") in allowed_tabs:
            item["tab"] = a["tab"]
        if t == "notify" and not item.get("body"):
            continue
        if t == "switch_tab" and not item.get("tab"):
            continue
        out.append(item)
    return out


def _openai_chat(
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 800,
    tools: list[dict[str, Any]] | None = None,
    raw: bool = False,
) -> Any:
    if not settings.openai_api_key:
        raise LiveCopilotError("OPENAI_API_KEY não configurada.")

    body: dict[str, Any] = {
        "model": settings.openai_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    try:
        r = httpx.post(
            f"{_OPENAI_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json=body,
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise LiveCopilotError(f"Erro de conexão OpenAI: {exc}") from exc

    if r.status_code >= 400:
        raise LiveCopilotError(f"OpenAI HTTP {r.status_code}: {r.text[:200]}")

    data = r.json()
    if raw:
        return data

    content = data["choices"][0]["message"].get("content") or ""
    content = re.sub(r"^```(?:json)?\s*", "", content.strip())
    content = re.sub(r"\s*```$", "", content)
    return content


__all__ = [
    "fallback_pregame_summary",
    "generate_pregame_summary",
    "run_pregame_copilot",
    "run_pregame_copilot_agent",
]
