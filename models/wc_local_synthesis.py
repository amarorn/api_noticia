"""Gerador de síntese Deep Research local (sem APIs externas).

Usa dados do match_context (relatório TXT, Sofascore, FIFA) + modelo WC
para gerar análise estruturada quando Gemini/Moonshot estão indisponíveis.
"""
from __future__ import annotations

from typing import Any

from ingest.superbet.match_context_store import load_match_context
from models.wc_referee_inplay import parse_referee_from_match_context


def _build_picks_from_model(model_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extrai picks recomendados dos dados do modelo.

    Funciona tanto com dados de ticket (pré-jogo) quanto com probabilidades
    simples (in-play / simulate_match).
    """
    picks = []

    # Formato 1: ticket com singles (pré-jogo)
    singles = model_data.get("ticket", {}).get("singles", [])
    combo = model_data.get("ticket", {}).get("combo")

    for s in singles:
        if s["market"] in ("1", "X", "2"):
            prob = s["model_prob"]
            conf = "Alta" if prob >= 0.65 else "Média" if prob >= 0.45 else "Baixa"
            picks.append({
                "aposta": s["label"],
                "nivel_confianca": conf,
                "racional": f"Probabilidade modelo: {prob:.1%}. Odd justa: {s.get('fair_odd', 'N/A')}",
            })

    if combo and combo.get("model_prob", 0) >= 0.35:
        picks.append({
            "aposta": combo["label"],
            "nivel_confianca": "Média",
            "racional": f"Probabilidade combinada: {combo['model_prob']:.1%}. Odd justa: {combo.get('fair_odd', 'N/A')}",
        })

    # Formato 2: probabilidades diretas (in-play / simulate)
    prob_home = model_data.get("prob_home", 0)
    prob_draw = model_data.get("prob_draw", 0)
    prob_away = model_data.get("prob_away", 0)

    if prob_home > 0 and not any(p["aposta"].startswith("1 -") for p in picks):
        if prob_home >= 0.50:
            conf = "Alta" if prob_home >= 0.65 else "Média"
            picks.append({
                "aposta": f"1 - Vitória mandante ({prob_home:.0%})",
                "nivel_confianca": conf,
                "racional": f"Modelo Poisson: {prob_home:.1%} de chance de vitória do mandante",
            })

    if prob_away > 0 and prob_away >= 0.35 and not any(p["aposta"].startswith("2 -") for p in picks):
        conf = "Alta" if prob_away >= 0.50 else "Média"
        picks.append({
            "aposta": f"2 - Vitória visitante ({prob_away:.0%})",
            "nivel_confianca": conf,
            "racional": f"Modelo Poisson: {prob_away:.1%} de chance de vitória do visitante",
        })

    if prob_draw > 0 and prob_draw >= 0.30 and not any("empate" in p["aposta"].lower() for p in picks):
        picks.append({
            "aposta": f"X - Empate ({prob_draw:.0%})",
            "nivel_confianca": "Média" if prob_draw >= 0.35 else "Baixa",
            "racional": f"Modelo Poisson: {prob_draw:.1%} de chance de empate",
        })

    # Over 2.5
    over_prob = model_data.get("over_2_5_prob") or model_data.get("over25")
    if over_prob and over_prob >= 0.5:
        picks.append({
            "aposta": f"Over 2.5 gols ({over_prob:.0%})",
            "nivel_confianca": "Média" if over_prob >= 0.55 else "Baixa",
            "racional": f"Poisson: {over_prob:.1%} de chance de mais de 2.5 gols",
        })

    # BTTS
    btts_prob = model_data.get("btts_prob") or model_data.get("btts")
    if btts_prob and btts_prob >= 0.45:
        picks.append({
            "aposta": f"Ambas marcam ({btts_prob:.0%})",
            "nivel_confianca": "Média" if btts_prob >= 0.50 else "Baixa",
            "racional": f"Poisson: {btts_prob:.1%} de chance de ambas marcarem",
        })

    # Placar provável
    top_scores = model_data.get("top_scores") or model_data.get("top_scorelines")
    if top_scores and not picks:
        if isinstance(top_scores, dict):
            top_score = max(top_scores, key=top_scores.get)
            top_prob = top_scores[top_score]
        elif isinstance(top_scores, list) and len(top_scores) > 0:
            top_score = top_scores[0]["score"] if isinstance(top_scores[0], dict) else top_scores[0]
            top_prob = top_scores[0].get("prob", 0.1) if isinstance(top_scores[0], dict) else 0.1
        else:
            top_score = None
            top_prob = 0

        if top_score:
            picks.append({
                "aposta": f"Placar exato {top_score} ({top_prob:.0%})",
                "nivel_confianca": "Baixa",
                "racional": "Placar mais provável segundo modelo Monte Carlo",
            })

    # Adiciona rank sequencial (esperado pelo frontend)
    return [{**p, "rank": i + 1} for i, p in enumerate(picks[:5])]


def _build_escalacao_from_context(match_context: dict[str, Any] | None, side: str) -> dict[str, Any]:
    """Extrai escalação do match_context."""
    if not match_context:
        return {"status": "Não disponível", "lesoes_suspensoes": [], "destaque": None}

    lineups = match_context.get("lineups", {})
    team_data = lineups.get(side, {})

    if not team_data:
        return {"status": "Não disponível", "lesoes_suspensoes": [], "destaque": None}

    lesoes = team_data.get("doubts", []) or team_data.get("lesoes_suspensoes", [])
    destaque = team_data.get("destaque")

    # Formata escalação
    parts = []
    if team_data.get("gk"):
        parts.append(f"GOL: {team_data['gk']}")
    if team_data.get("def"):
        parts.append(f"DEF: {', '.join(team_data['def'])}")
    if team_data.get("mid"):
        parts.append(f"MEI: {', '.join(team_data['mid'])}")
    if team_data.get("fwd"):
        parts.append(f"ATA: {', '.join(team_data['fwd'])}")

    return {
        "status": "Provável" if parts else "Não disponível",
        "lesoes_suspensoes": lesoes,
        "destaque": destaque or (parts[0] if parts else None),
    }


def _build_arbitro_from_context(match_context: dict[str, Any] | None) -> dict[str, Any]:
    """Extrai dados do árbitro do match_context."""
    if not match_context:
        return {"nome": "Não divulgado", "perfil": "Não disponível"}

    referee = parse_referee_from_match_context(match_context)
    if not referee:
        return {"nome": "Não divulgado", "perfil": "Não disponível"}

    profile_desc = {
        "punitivista": f"Árbitro punitivista — {referee.card_lambda:.1f} cartões/jogo em média. Espere jogo truncado.",
        "pacificador": f"Árbitro pacificador — {referee.card_lambda:.1f} cartões/jogo. Jogo mais fluido.",
        "equilibrado": f"Árbitro equilibrado — {referee.card_lambda:.1f} cartões/jogo.",
    }

    return {
        "nome": referee.name,
        "perfil": profile_desc.get(referee.profile, referee.profile),
        "nacionalidade": referee.nationality,
        "card_lambda": referee.card_lambda,
        "foul_lambda": referee.foul_lambda,
        "penalty_rate": referee.penalty_rate,
        "red_card_rate": referee.red_card_rate,
    }


def _build_fatores_from_context(match_context: dict[str, Any] | None, model_data: dict[str, Any]) -> list[str]:
    """Constrói lista de fatores positivos."""
    fatores = []

    # Dados do modelo
    pred = model_data.get("prediction", "")
    conf = model_data.get("confidence", 0)
    if conf >= 0.6:
        fatores.append(f"Modelo confiante ({conf:.0%}) — predição: {pred}")
    elif conf >= 0.4:
        fatores.append(f"Modelo com confiança moderada ({conf:.0%})")

    # H2H
    h2h = model_data.get("h2h_summary", "")
    if h2h:
        fatores.append(f"Histórico confrontos: {h2h}")

    # Dados do contexto
    if match_context:
        h2h_total = match_context.get("h2h_total_games")
        h2h_home_wins = match_context.get("h2h_home_wins")
        if h2h_total and h2h_home_wins:
            win_rate = h2h_home_wins / h2h_total
            if win_rate >= 0.7:
                fatores.append(f"Dominância histórica: {h2h_home_wins}/{h2h_total} vitórias")

        h2h_home_goals = match_context.get("h2h_home_goals_avg")
        if h2h_home_goals and h2h_home_goals >= 2.0:
            fatores.append(f"Média de {h2h_home_goals:.1f} gols marcados por jogo no H2H")

        # Stakes
        stakes = match_context.get("brasil_stakes") or match_context.get("stakes")
        if stakes:
            if isinstance(stakes, dict):
                for k, v in stakes.items():
                    if "vencer" in k or "win" in k:
                        fatores.append(f"Stakes altos: {v}")
                        break

        # Referee
        referee = parse_referee_from_match_context(match_context)
        if referee and referee.is_punitivista:
            fatores.append(f"Árbitro punitivista ({referee.card_lambda:.1f} cartões/jogo) — mercado de cartões com valor")

    return fatores[:6]


def _build_riscos_from_context(match_context: dict[str, Any] | None, model_data: dict[str, Any]) -> list[str]:
    """Constrói lista de alertas de risco."""
    riscos = []

    conf = model_data.get("confidence", 0)
    if conf < 0.35:
        riscos.append("Baixa confiança do modelo — mercado pode estar desajustado")

    if match_context:
        # H2H com zebra recente
        h2h_total = match_context.get("h2h_total_games")
        h2h_away_wins = match_context.get("h2h_away_wins")
        if h2h_total and h2h_away_wins and h2h_away_wins / h2h_total >= 0.3:
            riscos.append(f"Histórico com {h2h_away_wins} vitória(s) do visitante em {h2h_total} jogos")

        # Dúvidas de escalação
        lineups = match_context.get("lineups", {})
        for side in ["brasil", "home", "away"]:
            team = lineups.get(side, {})
            doubts = team.get("doubts", []) or team.get("lesoes_suspensoes", [])
            if doubts:
                riscos.append(f"Dúvidas em {side}: {', '.join(doubts[:3])}")

        # Clima
        temp = match_context.get("weather_temp_c")
        if temp and temp >= 30:
            riscos.append(f"Temperatura alta ({temp}°C) pode afetar rendimento")

        # Gramado sintético
        pitch = match_context.get("pitch_type", "")
        if "sintetico" in pitch.lower() or "synthetic" in pitch.lower():
            riscos.append("Gramado sintético — pode alterar dinâmica do jogo")

    # Modelo com empate como predição
    pred = model_data.get("prediction", "")
    if pred == "X":
        riscos.append("Modelo prevê empate — mercado de 1X2 pode ser volátil")

    return riscos[:5]


def _build_mercados_from_model(model_data: dict[str, Any]) -> dict[str, str]:
    """Constrói análise de mercados."""
    mercados = {}

    prob_home = model_data.get("prob_home", 0)
    prob_draw = model_data.get("prob_draw", 0)
    prob_away = model_data.get("prob_away", 0)

    # 1X2
    if prob_home > prob_draw and prob_home > prob_away:
        mercados["resultado"] = f"Favorito mandante ({prob_home:.0%}) — valor se odd > {round(1/prob_home, 2)}"
    elif prob_away > prob_home and prob_away > prob_draw:
        mercados["resultado"] = f"Favorito visitante ({prob_away:.0%}) — possível zebra"
    else:
        mercados["resultado"] = f"Empate provável ({prob_draw:.0%}) — mercado equilibrado"

    # Over/Under
    singles = model_data.get("ticket", {}).get("singles", [])
    over = next((s for s in singles if s["market"] == "over_2_5"), None)
    if over:
        mercados["over_under"] = f"Over 2.5: {over['model_prob']:.0%} — {'valor' if over['model_prob'] >= 0.55 else 'evitar'}"

    # BTTS
    btts = next((s for s in singles if s["market"] == "btts"), None)
    if btts:
        mercados["btts"] = f"Ambas marcam: {btts['model_prob']:.0%}"

    return mercados


def _build_resumo_executivo(
    home: str,
    away: str,
    model_data: dict[str, Any],
    match_context: dict[str, Any] | None,
) -> str:
    """Constrói resumo executivo em português."""
    parts = []

    prob_home = model_data.get("prob_home", 0)
    prob_draw = model_data.get("prob_draw", 0)
    prob_away = model_data.get("prob_away", 0)

    # Determina palpite
    if prob_home > prob_draw and prob_home > prob_away:
        pred = f"vitória {home} ({prob_home:.0%})"
    elif prob_away > prob_home and prob_away > prob_draw:
        pred = f"vitória {away} ({prob_away:.0%})"
    else:
        pred = f"empate ({prob_draw:.0%})"

    conf = model_data.get("confidence", 0)
    eg = model_data.get("expected_goals", "?x?")

    parts.append(f"Análise local (sem APIs externas) para {home} x {away}.")
    parts.append(f"Modelo prevê {pred} com {conf:.0%} de confiança. Expectativa de gols: {eg}.")

    if match_context:
        comp = match_context.get("competition", "")
        if comp:
            parts.append(f"Competição: {comp}.")

        # H2H do match_context (formato novo do wc_inplay_h2h_adjust)
        h2h = match_context.get("h2h", {})
        if isinstance(h2h, dict) and h2h.get("total", 0) >= 2:
            h2h_total = h2h["total"]
            h2h_home_wins = h2h.get("home_wins", 0)
            avg_goals = h2h.get("avg_total_goals", 0)
            if h2h_home_wins == h2h_total and h2h_total >= 3:
                parts.append(f"Histórico perfeito do mandante: {h2h_home_wins}/{h2h_total} vitórias.")
            elif avg_goals > 0:
                parts.append(f"H2H: {h2h_total} jogos, média {avg_goals:.1f} gols/jogo.")

        # H2H formato antigo (fallback)
        h2h_total_old = match_context.get("h2h_total_games")
        h2h_home_wins_old = match_context.get("h2h_home_wins")
        if h2h_total_old and h2h_home_wins_old == h2h_total_old and h2h_total_old >= 3:
            if not any("Histórico perfeito" in p for p in parts):
                parts.append(f"Histórico perfeito do mandante: {h2h_home_wins_old}/{h2h_total_old} vitórias.")

        referee = parse_referee_from_match_context(match_context)
        if referee:
            parts.append(f"Árbitro: {referee.name} ({referee.profile}, {referee.card_lambda:.1f} cartões/jogo).")

    return " ".join(parts)


def _build_placar_provavel(model_data: dict[str, Any]) -> str:
    """Extrai placar mais provável dos scorelines."""
    scorelines = model_data.get("top_scorelines", [])
    if scorelines:
        return scorelines[0]["score"]
    eg = model_data.get("expected_goals", "?x?")
    return eg


def generate_local_synthesis(
    home: str,
    away: str,
    model_data: dict[str, Any],
    match_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Gera síntese Deep Research local usando dados do modelo + contexto.

    Retorna estrutura compatível com ResearchSynthesis do frontend.
    """
    if match_context is None:
        # Tenta carregar do match_context_store
        # Não temos event_id aqui, então usamos apenas model_data
        pass

    # Determina favorito e confiança
    prob_home = model_data.get("prob_home", 0)
    prob_draw = model_data.get("prob_draw", 0)
    prob_away = model_data.get("prob_away", 0)

    if prob_home > prob_away and prob_home > prob_draw:
        favorito = home
        confianca = "Alta" if prob_home >= 0.65 else "Média" if prob_home >= 0.50 else "Baixa"
    elif prob_away > prob_home and prob_away > prob_draw:
        favorito = away
        confianca = "Alta" if prob_away >= 0.50 else "Média" if prob_away >= 0.35 else "Baixa"
    else:
        favorito = "Empate"
        confianca = "Média" if prob_draw >= 0.35 else "Baixa"

    # Ajusta confiança baseada no match_context
    if match_context:
        h2h_total = match_context.get("h2h_total_games")
        h2h_home_wins = match_context.get("h2h_home_wins")
        if h2h_total and h2h_home_wins and h2h_home_wins / h2h_total >= 0.8:
            if confianca == "Média":
                confianca = "Alta"

    return {
        "resumo_executivo": _build_resumo_executivo(home, away, model_data, match_context),
        "favorito": favorito,
        "confianca_geral": confianca,
        "principais_fatores": _build_fatores_from_context(match_context, model_data),
        "alertas_risco": _build_riscos_from_context(match_context, model_data),
        "escalacao_home": _build_escalacao_from_context(match_context, "brasil" if "brasil" in home.lower() else "home"),
        "escalacao_away": _build_escalacao_from_context(match_context, "away"),
        "arbitro": _build_arbitro_from_context(match_context),
        "analise_mercados": _build_mercados_from_model(model_data),
        "picks_recomendados": _build_picks_from_model(model_data),
        "placar_provavel": _build_placar_provavel(model_data),
        "nota_final": "Análise gerada localmente (sem APIs externas). Use as abas Picks e Probabilidades para dados do modelo em tempo real.",
        "_source": "local_synthesis",
    }


def generate_local_synthesis_with_context_lookup(
    home: str,
    away: str,
    model_data: dict[str, Any],
    event_id: int | None = None,
) -> dict[str, Any] | None:
    """Gera síntese local tentando carregar match_context do event_id."""
    match_context = None
    if event_id:
        match_context = load_match_context(event_id)

    return generate_local_synthesis(home, away, model_data, match_context)
