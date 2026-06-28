"""Google Gemini — pesquisa via Google Search Grounding + síntese estruturada de análise pré-jogo."""
from __future__ import annotations

import json
import re

import httpx

from config import settings

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_TIMEOUT = 90.0


class GeminiError(Exception):
    pass


_SYSTEM_PROMPT = """\
Você é um analista quantitativo sênior de apostas esportivas com expertise em futebol internacional.
Use sua capacidade de busca no Google para obter informações ATUAIS sobre a partida solicitada.

Retorne SOMENTE um JSON válido (sem markdown, sem texto extra) com esta estrutura exata:
{
  "resumo_executivo": "2-3 frases sobre o cenário geral",
  "favorito": "nome do time favorito ou 'Empate equilibrado'",
  "confianca_geral": "Alta|Média|Baixa",
  "principais_fatores": ["fator1", "fator2", "fator3"],
  "alertas_risco": ["risco1", "risco2"],
  "escalacao_home": {
    "status": "Completo|Desfalques importantes|Incerto",
    "lesoes_suspensoes": ["jogador (motivo)"],
    "destaque": "jogador mais importante"
  },
  "escalacao_away": {
    "status": "Completo|Desfalques importantes|Incerto",
    "lesoes_suspensoes": ["jogador (motivo)"],
    "destaque": "jogador mais importante"
  },
  "arbitro": {
    "nome": "nome ou 'Não divulgado'",
    "perfil": "estilo e média de cartões por jogo (ex: rigoroso, ~4.2 cartões/jogo)",
    "card_lambda": 4.2,
    "penalty_rate": 0.35
  },
  "analise_mercados": {
    "resultado": "análise 1X2",
    "over_under": "análise gols totais",
    "btts": "análise ambas marcam",
    "handicap": "análise handicap asiático"
  },
  "picks_recomendados": [
    {"rank": 1, "aposta": "descrição", "racional": "motivação", "nivel_confianca": "Alta|Média|Baixa"}
  ],
  "placar_provavel": "X x Y",
  "nota_final": "observação final para o apostador"
}"""


_FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


def synthesize_with_google_search(
    home_team: str,
    away_team: str,
    model_data: dict,
    extra_context: str = "",
) -> dict:
    """Chama Gemini com Google Search Grounding para pesquisar + sintetizar análise pré-jogo."""
    if not settings.gemini_api_key:
        raise GeminiError("GEMINI_API_KEY não configurada.")

    user_prompt = _build_prompt(home_team, away_team, model_data, extra_context)

    # Tenta o modelo configurado e os fallbacks em sequência
    models_to_try = [settings.gemini_model] + [m for m in _FALLBACK_MODELS if m != settings.gemini_model]
    errors_by_model: list[str] = []
    quota_exhausted = False

    for model in models_to_try:
        url = f"{_BASE_URL}/{model}:generateContent?key={settings.gemini_api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "tools": [{"google_search": {}}],
            # responseMimeType é incompatível com google_search — omitido intencionalmente
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 4096,
            },
        }

        try:
            resp = httpx.post(url, json=payload, timeout=_TIMEOUT)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            text = exc.response.text[:200]
            if status == 429:
                # Quota esgotada — marca flag, tenta próximo modelo
                quota_exhausted = True
                errors_by_model.append(f"{model}: quota esgotada (429)")
                continue
            if status == 404:
                # Modelo não encontrado — tenta próximo fallback
                errors_by_model.append(f"{model}: modelo não encontrado (404)")
                continue
            # Outro erro HTTP — não tenta fallbacks
            raise GeminiError(f"Gemini HTTP {status}: {exc.response.text[:400]}") from exc
        except httpx.RequestError as exc:
            raise GeminiError(f"Erro de conexão Gemini: {exc}") from exc

        # Sucesso — extrai e retorna
        data = resp.json()

        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise GeminiError(f"Gemini retornou resposta vazia: {json.dumps(data)[:300]}")
            parts = candidates[0].get("content", {}).get("parts", [])
            raw_text = "".join(p.get("text", "") for p in parts).strip()
        except (KeyError, IndexError) as exc:
            raise GeminiError(f"Formato de resposta inesperado: {data!r}") from exc

        citations: list[str] = []
        try:
            grounding = candidates[0].get("groundingMetadata", {})
            for chunk in grounding.get("groundingChunks", []):
                uri = chunk.get("web", {}).get("uri", "")
                if uri:
                    citations.append(uri)
        except Exception:
            pass

        return {
            "report": _parse_json(raw_text),
            "citations": citations,
            "usage": data.get("usageMetadata", {}),
            "model": model,
        }

    # Todos os modelos falharam
    if quota_exhausted:
        raise GeminiError(
            f"Todos os modelos Gemini atingiram a cota diária. "
            f"Tentados: {', '.join(errors_by_model)}"
        )
    raise GeminiError(
        f"Nenhum modelo Gemini disponível. "
        f"Tentados: {', '.join(errors_by_model)}"
    )


# Alias para compatibilidade com o endpoint existente
def synthesize_pregame_report(
    home_team: str,
    away_team: str,
    model_data: dict,
    web_research: str = "",
) -> dict:
    result = synthesize_with_google_search(home_team, away_team, model_data, extra_context=web_research)
    return {
        "report": result["report"],
        "web_searches": result.get("citations", []),
        "usage": result.get("usage", {}),
        "model": result.get("model", settings.gemini_model),
    }


def _build_prompt(home: str, away: str, model_data: dict, extra: str) -> str:
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    picks_txt = _format_picks(model_data.get("ticket", {}))
    scores_txt = _format_scorelines(model_data.get("top_scorelines", []))

    return f"""Analise a partida: {home} x {away} — Copa do Mundo 2026
Data: {today}

=== DADOS DO MODELO PROBABILÍSTICO ===
{home} vence: {model_data.get('prob_home', 0):.1%}
Empate: {model_data.get('prob_draw', 0):.1%}
{away} vence: {model_data.get('prob_away', 0):.1%}

Placar Poisson: {model_data.get('poisson_score', '?')}
xG: {model_data.get('expected_goals', '?')}
Confiança: {model_data.get('confidence', 0):.1%}
Predição: {model_data.get('prediction', '?')}
H2H: {model_data.get('h2h_summary', 'Sem dados')}
Grupo: {model_data.get('group', 'N/A')}

Picks Kelly 25%:
{picks_txt}

Placares mais prováveis:
{scores_txt}

{('Contexto adicional:\n' + extra) if extra else ''}

=== TAREFA ===
Busque no Google as informações mais recentes sobre esta partida:
- Escalação provável e confirmada de ambos os times
- Lesões, suspensões e desfalques
- Forma recente (últimos 5 jogos de cada time na Copa/amistosos)
- Árbitro designado e seu perfil estatístico
- Contexto do grupo (quem precisa vencer para classificar?)

Combine com os dados do modelo e retorne o JSON estruturado."""


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    # Remove markdown se houver
    raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
    raw = re.sub(r"\n?```\s*$", "", raw)
    raw = raw.strip()

    # Tentativa 1: texto inteiro é JSON válido
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Tentativa 2: extrair bloco { ... } usando primeiro { e último }
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass

    # Tentativa 3: o modelo retornou JSON incompleto (truncado) — tenta completar
    if start != -1 and end == -1:
        try:
            candidate = raw[start:]
            # Conta chaves abertas para tentar fechar
            depth = 0
            for ch in candidate:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
            if depth > 0:
                candidate += "}" * depth
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return {"resumo_executivo": raw[:800], "nota_final": "Falha ao parsear JSON da IA."}


def _format_picks(ticket: dict) -> str:
    lines = []
    for i, s in enumerate(ticket.get("singles", []), 1):
        lines.append(
            f"  {i}. {s.get('label')} — {s.get('model_prob', 0):.1%} | odd justa {s.get('fair_odd', '?')} | Kelly {s.get('kelly_units', 0):.1f}u"
        )
    combo = ticket.get("combo")
    if combo:
        lines.append(f"  COMBO: {combo.get('label')} — {combo.get('model_prob', 0):.1%} | odd justa {combo.get('fair_odd', '?')}")
    return "\n".join(lines) or "  Sem picks"


def _format_scorelines(scorelines: list) -> str:
    return "\n".join(f"  {s['score']}: {s['prob']:.1%}" for s in scorelines[:6])
