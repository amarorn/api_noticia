"""Moonshot (Kimi) — pesquisa web nativa + síntese em relatório estruturado de apostas."""
from __future__ import annotations

import json
import re

import httpx

from config import settings

_BASE_URL = "https://api.moonshot.cn/v1"
_TIMEOUT = 120.0  # busca web pode demorar mais


class MoonshotError(Exception):
    pass


_SYSTEM_PROMPT = """\
Você é um analista quantitativo sênior de apostas esportivas com expertise em futebol internacional.
Você tem acesso a busca na web para obter informações atualizadas sobre a partida.

Gere um relatório estruturado em JSON com EXATAMENTE estes campos:
{
  "resumo_executivo": "2-3 frases sobre o cenário geral do jogo",
  "favorito": "nome do time favorito ou 'Empate equilibrado'",
  "confianca_geral": "Alta|Média|Baixa",
  "principais_fatores": ["fator1", "fator2", "fator3"],
  "alertas_risco": ["risco1", "risco2"],
  "escalacao_home": {
    "status": "Completo|Desfalques importantes|Incerto",
    "lesoes_suspensoes": ["jogador1 (motivo)"],
    "destaque": "nome do jogador mais importante"
  },
  "escalacao_away": {
    "status": "Completo|Desfalques importantes|Incerto",
    "lesoes_suspensoes": ["jogador1 (motivo)"],
    "destaque": "nome do jogador mais importante"
  },
  "arbitro": {
    "nome": "nome ou 'Não divulgado'",
    "perfil": "descrição do estilo (rigoroso/permissivo/neutro) e média de cartões"
  },
  "analise_mercados": {
    "resultado": "análise do mercado 1X2 considerando modelo + contexto",
    "over_under": "análise gols totais",
    "btts": "análise ambas marcam",
    "handicap": "análise handicap asiático se relevante"
  },
  "picks_recomendados": [
    {
      "rank": 1,
      "aposta": "descrição clara",
      "racional": "por que apostar",
      "nivel_confianca": "Alta|Média|Baixa"
    }
  ],
  "placar_provavel": "X x Y",
  "nota_final": "observação relevante para o apostador"
}
Responda APENAS com o JSON válido, sem markdown, sem texto extra."""


def _build_user_message(home_team: str, away_team: str, model_data: dict, extra_web: str = "") -> str:
    return f"""
PARTIDA: {home_team} x {away_team} — Copa do Mundo 2026
Data de análise: {_today_str()}

=== DADOS DO MODELO PROBABILÍSTICO ===
Probabilidades:
  {home_team} vence: {model_data.get('prob_home', 0):.1%}
  Empate: {model_data.get('prob_draw', 0):.1%}
  {away_team} vence: {model_data.get('prob_away', 0):.1%}

Placar mais provável (Poisson): {model_data.get('poisson_score', '?')}
xG esperado: {model_data.get('expected_goals', '?')}
Confiança do modelo: {model_data.get('confidence', 0):.1%}
Predição: {model_data.get('prediction', '?')}

Picks com Kelly 25% (odd justa):
{_format_picks(model_data.get('ticket', {}))}

Top placares Poisson:
{_format_scorelines(model_data.get('top_scorelines', []))}

Histórico H2H: {model_data.get('h2h_summary', 'Sem dados')}
Grupo: {model_data.get('group', 'N/A')} | Fase: {model_data.get('phase', 'group')}

{('=== PESQUISA WEB ADICIONAL ===\n' + extra_web) if extra_web else ''}

=== INSTRUÇÃO ===
Use sua busca na web para obter informações ATUAIS sobre esta partida:
- Escalações prováveis e confirmadas
- Lesões, suspensões e desfalques
- Forma recente dos dois times (últimos 5 jogos)
- Árbitro designado e seu perfil
- Contexto da partida (pressão classificatória, confronto histórico recente)

Combine com os dados do modelo acima e gere o relatório JSON estruturado.
Priorize informações de lesões/suspensões que possam alterar as probabilidades.
"""


def synthesize_with_web_search(
    home_team: str,
    away_team: str,
    model_data: dict,
    extra_web: str = "",
) -> dict:
    """Usa Moonshot com busca web nativa ($web_search tool) para pesquisar + sintetizar."""
    if not settings.moonshot_api_key:
        raise MoonshotError("MOONSHOT_API_KEY não configurada.")

    tools = [
        {
            "type": "builtin_function",
            "function": {"name": "$web_search"},
        }
    ]

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_message(home_team, away_team, model_data, extra_web)},
    ]

    headers = {
        "Authorization": f"Bearer {settings.moonshot_api_key}",
        "Content-Type": "application/json",
    }

    search_results: list[str] = []

    # Loop de tool calling (Moonshot pode chamar a busca múltiplas vezes)
    for _turn in range(6):
        payload = {
            "model": settings.moonshot_model,
            "messages": messages,
            "tools": tools,
            "temperature": 0.15,
            "max_tokens": 4000,
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
            raise MoonshotError(
                f"Moonshot HTTP {exc.response.status_code}: {exc.response.text[:400]}"
            ) from exc
        except httpx.RequestError as exc:
            raise MoonshotError(f"Erro de conexão Moonshot: {exc}") from exc

        data = resp.json()
        choice = data["choices"][0]
        finish_reason = choice.get("finish_reason")
        assistant_message = choice["message"]

        messages.append(assistant_message)

        # Se o modelo chamou tool(s), executa e devolve os resultados
        if finish_reason == "tool_calls" and assistant_message.get("tool_calls"):
            for tc in assistant_message["tool_calls"]:
                func_name = tc["function"]["name"]
                func_args = json.loads(tc["function"].get("arguments", "{}"))

                if func_name == "$web_search":
                    # Chama a busca web via API Moonshot
                    result_content = _execute_web_search(
                        query=func_args.get("query", f"{home_team} vs {away_team} Copa 2026"),
                        headers=headers,
                    )
                    search_results.append(result_content[:500])
                else:
                    result_content = json.dumps({"error": f"função desconhecida: {func_name}"})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": func_name,
                    "content": result_content,
                })
            continue  # próxima rodada

        # Resposta final
        raw_text = assistant_message.get("content", "")
        report = _parse_json(raw_text)

        return {
            "report": report,
            "web_searches": search_results,
            "usage": data.get("usage", {}),
            "model": data.get("model", settings.moonshot_model),
        }

    raise MoonshotError("Moonshot não finalizou após 6 turnos de tool calling.")


def synthesize_pregame_report(
    home_team: str,
    away_team: str,
    model_data: dict,
    web_research: str = "",
) -> dict:
    """Entry-point principal: usa busca web nativa do Moonshot."""
    return synthesize_with_web_search(home_team, away_team, model_data, extra_web=web_research)


def _execute_web_search(query: str, headers: dict) -> str:
    """Executa uma busca via Moonshot search endpoint (se disponível) ou retorna placeholder."""
    # O Moonshot $web_search é executado internamente pelo servidor — o resultado
    # já vem na resposta quando finish_reason == "tool_calls". Neste wrapper
    # apenas logamos a query; o conteúdo real vem do servidor Moonshot.
    return json.dumps({"query": query, "status": "executed_by_moonshot"})


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {"resumo_executivo": raw[:500], "nota_final": "Falha ao parsear JSON da IA."}


def _today_str() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _format_picks(ticket: dict) -> str:
    lines = []
    for i, s in enumerate(ticket.get("singles", []), 1):
        lines.append(
            f"  {i}. {s.get('label')} — prob {s.get('model_prob', 0):.1%} "
            f"| odd justa {s.get('fair_odd', '?')} | Kelly {s.get('kelly_units', 0):.1f}u"
        )
    combo = ticket.get("combo")
    if combo:
        lines.append(
            f"  COMBO: {combo.get('label')} — prob {combo.get('model_prob', 0):.1%} "
            f"| odd justa {combo.get('fair_odd', '?')} | Kelly {combo.get('kelly_units', 0):.1f}u"
        )
    return "\n".join(lines) if lines else "  Sem picks disponíveis"


def _format_scorelines(scorelines: list) -> str:
    return "\n".join(f"  {s['score']}: {s['prob']:.1%}" for s in scorelines[:6])
