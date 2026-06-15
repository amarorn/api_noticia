"""Avaliação de confiança e tendência da previsão do modelo WC.

Este módulo determina se a probabilidade calculada pelo modelo é
CONFIÁVEL (baseada em dados sólidos) ou ESPECULATIVA (baseada em poucos
ou nenhum dado histórico).
"""
from __future__ import annotations

from dataclasses import dataclass

from pipelines.wc_stats import WcMatchFeatures


@dataclass
class TrendConfidence:
    """Resultado da avaliação de confiança da previsão."""

    score: float  # 0.0 a 1.0 — quão confiável é a previsão
    label: str  # "alta", "media", "baixa", "especulativa"
    reason: str  # Explicação em português para o usuário
    data_quality_score: float  # 0.0 a 1.0 — qualidade dos dados de entrada
    sample_size_score: float  # 0.0 a 1.0 — quantidade de jogos no histórico
    recency_score: float  # 0.0 a 1.0 — quão recentes são os dados


def assess_prediction_confidence(
    features: WcMatchFeatures | None,
    *,
    home_team: str,
    away_team: str,
    minute: int = 0,
    home_score: int = 0,
    away_score: int = 0,
) -> TrendConfidence:
    """Avalia se a previsão do modelo é confiável ou especulativa.

    Retorna um score de 0.0 (puro chute) a 1.0 (dados sólidos).
    """
    if features is None:
        return TrendConfidence(
            score=0.0,
            label="especulativa",
            reason="Não há dados históricos para estes times. O modelo está "
            "adivinhando baseado em médias genéricas.",
            data_quality_score=0.0,
            sample_size_score=0.0,
            recency_score=0.0,
        )

    # 1. Qualidade dos dados (0.0 a 1.0)
    data_quality = _data_quality_score(features)

    # 2. Tamanho da amostra (0.0 a 1.0)
    sample_size = _sample_size_score(features)

    # 3. Recência dos dados (0.0 a 1.0)
    recency = _recency_score(features, minute=minute)

    # 4. Penalidade por placar extremo (dificulta previsão)
    score_penalty = _score_extremity_penalty(home_score, away_score, minute)

    # Score final = média ponderada
    score = (
        data_quality * 0.35
        + sample_size * 0.35
        + recency * 0.20
        - score_penalty * 0.10
    )
    score = max(0.0, min(1.0, score))

    label, reason = _confidence_label(score, features, home_team, away_team)

    return TrendConfidence(
        score=round(score, 3),
        label=label,
        reason=reason,
        data_quality_score=round(data_quality, 3),
        sample_size_score=round(sample_size, 3),
        recency_score=round(recency, 3),
    )


def _data_quality_score(features: WcMatchFeatures) -> float:
    """Avalia se os dados do time são reais ou genéricos."""
    score = 0.0

    # Elo: se for o valor inicial (1500), é genérico
    if features.elo_home != 1500.0 and features.elo_away != 1500.0:
        score += 0.3
    elif features.elo_home != 1500.0 or features.elo_away != 1500.0:
        score += 0.15

    # H2H: se tiver jogos reais entre os times
    if features.h2h_total >= 2:
        score += 0.3
    elif features.h2h_total >= 1:
        score += 0.15

    # Forma: se tiver dados de gols reais (não genéricos ~1.0)
    if features.home_goals_rate > 0.5 and features.home_goals_rate < 3.0:
        score += 0.2
    if features.away_goals_rate > 0.5 and features.away_goals_rate < 3.0:
        score += 0.2

    return min(1.0, score)


def _sample_size_score(features: WcMatchFeatures) -> float:
    """Avalia quantos jogos temos no histórico."""
    # Usa h2h_total como proxy de amostra (ideal: 5+ jogos = 1.0)
    total = features.h2h_total
    if total >= 5:
        return 1.0
    if total >= 3:
        return 0.7
    if total >= 1:
        return 0.4
    return 0.1


def _recency_score(features: WcMatchFeatures, *, minute: int = 0) -> float:
    """Avalia se os dados são recentes ou antigos."""
    # Em jogos ao vivo, dados do pré-jogo são sempre "recentes"
    # Penalidade se for muito cedo no jogo (dados ainda não ajustados)
    if minute < 10:
        return 0.6  # Dados pré-jogo, ainda não testados
    if minute < 30:
        return 0.8  # Começando a ter evidência
    return 1.0  # Dados ao vivo consolidados


def _score_extremity_penalty(home_score: int, away_score: int, minute: int) -> float:
    """Penaliza previsões quando o placar é extremo (dificulta modelagem)."""
    deficit = abs(home_score - away_score)
    if deficit >= 3:
        return 0.5  # Virada de 3+ é muito difícil de prever
    if deficit >= 2 and minute > 75:
        return 0.3  # Final de jogo com 2 gols de diferença
    return 0.0


def _confidence_label(
    score: float,
    features: WcMatchFeatures,
    home_team: str,
    away_team: str,
) -> tuple[str, str]:
    """Gera label e explicação em português simples."""
    if score >= 0.7:
        return (
            "alta",
            f"Confiança ALTA: temos {features.h2h_total} jogos entre {home_team} e "
            f"{away_team} no histórico. A previsão é baseada em dados reais.",
        )
    if score >= 0.4:
        return (
            "media",
            f"Confiança MÉDIA: poucos jogos entre {home_team} e {away_team} no "
            f"histórico. A previsão é razoável, mas não é garantia.",
        )
    if score >= 0.2:
        return (
            "baixa",
            f"Confiança BAIXA: {home_team} e {away_team} quase não se enfrentaram. "
            f"O modelo está usando médias genéricas.",
        )
    return (
        "especulativa",
        f"Confiança MUITO BAIXA: não temos dados suficientes sobre {home_team} e "
        f"{away_team}. O modelo está praticamente adivinhando.",
    )
