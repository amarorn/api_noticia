"""Market shrinkage: mistura λ do modelo com λ implícito do mercado.

O mercado (odds Superbet ao vivo) contém informação que o modelo não tem:
- Escalações confirmadas, lesões de última hora
- Condições de campo, contexto motivacional
- Informação de insiders / fluxo de apostas

O shrinkage combina as duas fontes de informação com um peso α(minute)
que varia ao longo do jogo:
- Início (min 0): α = α_max (~0.70) → mercado domina
- Reta final (min 80+): α = α_min (~0.30) → modelo domina (mercado fica ruidoso)

Fórmula:
    λ_shrunk = α(min) × λ_market + (1 - α(min)) × λ_model

Onde λ_market = -ln(1 - P_market_ajustada) para converter probabilidades de
mercado (corrigidas pela margem) em intensidade Poisson equivalente.

Spec: docs/specs/spec-fase-1-quickwins-inplay.md § 1c
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# Parâmetros do shrinkage: α decresce linearmente de α_max para α_min
_ALPHA_MAX = 0.70   # Peso do mercado no início (mercado = informação fresca)
_ALPHA_MIN = 0.30   # Peso do mercado na reta final (mercado = ruidoso)
_ALPHA_DECAY_START = 0    # Minuto onde α = α_max
_ALPHA_DECAY_END = 80     # Minuto onde α = α_min (linear entre start e end)


@dataclass
class ShrinkageResult:
    """Resultado do shrinkage de λ com mercado."""

    lambda_shrunk_home: float
    lambda_shrunk_away: float
    alpha_used: float
    lambda_model_home: float
    lambda_model_away: float
    lambda_market_home: float
    lambda_market_away: float


def compute_alpha(minute: int) -> float:
    """Calcula o peso α do mercado para um dado minuto.

    α decresce linearmente de α_max (min 0) para α_min (min 80+).
    """
    if minute <= _ALPHA_DECAY_START:
        return _ALPHA_MAX
    if minute >= _ALPHA_DECAY_END:
        return _ALPHA_MIN

    # Interpolação linear
    frac = (minute - _ALPHA_DECAY_START) / (_ALPHA_DECAY_END - _ALPHA_DECAY_START)
    return _ALPHA_MAX - frac * (_ALPHA_MAX - _ALPHA_MIN)


def market_prob_to_lambda(
    prob_home: float,
    prob_draw: float,
    prob_away: float,
    match_minutes: int = 90,
) -> tuple[float, float]:
    """Converte probabilidades de mercado (ajustadas pela margem) em λ Poisson equivalente.

    Usa a relação de um modelo Poisson bivariado simplificado:
    - P(home win) ≈ 1 - exp(-λ_home_excess) para modelo de diferença
    - Aproximação via -ln(P(não-vitória)) ajustada

    Método mais robusto: resolve o sistema Poisson para achar λ_h, λ_a
    que melhor reproduzem as probabilidades dadas.

    Aqui usamos uma heurística rápida baseada no expected goals implícito:
    - λ_home ≈ -(match_minutes/90) × ln(P(away_win) + 0.5 × P(draw))
    - λ_away ≈ -(match_minutes/90) × ln(P(home_win) + 0.5 × P(draw))
    """
    # Corrigir probabilidades para somar 1
    total = prob_home + prob_draw + prob_away
    if total <= 0:
        return 1.2, 1.2  # fallback razoável

    ph = prob_home / total
    pd = prob_draw / total
    pa = prob_away / total

    # Heurística: probabilidade de "não marcar dominante"
    # P(home não domina) = P(draw) + P(away) → proxy para defesa adversária
    p_no_home = pa + 0.5 * pd
    p_no_away = ph + 0.5 * pd

    # Clip para evitar log(0)
    p_no_home = np.clip(p_no_home, 0.05, 0.95)
    p_no_away = np.clip(p_no_away, 0.05, 0.95)

    # λ ≈ -ln(P(não marca mais que adversário))
    # Ajuste empírico: fator 1.35 para alinhar com λ real de Copas (~1.3 gols/time/jogo)
    factor = 1.35
    lambda_home = float(-np.log(p_no_home) * factor)
    lambda_away = float(-np.log(p_no_away) * factor)

    # Limitar a valores razoáveis
    lambda_home = float(np.clip(lambda_home, 0.3, 3.5))
    lambda_away = float(np.clip(lambda_away, 0.3, 3.5))

    return lambda_home, lambda_away


def market_probs_from_h2h_implied(h2h_implied: dict[str, float] | None) -> tuple[float, float, float] | None:
    """Extrai (P1, PX, P2) normalizadas do snapshot Superbet."""
    if not h2h_implied:
        return None
    p1 = float(h2h_implied.get("1") or 0)
    px = float(h2h_implied.get("X") or 0)
    p2 = float(h2h_implied.get("2") or 0)
    if p1 <= 0 or px <= 0 or p2 <= 0:
        return None
    total = p1 + px + p2
    if total <= 0:
        return None
    return p1 / total, px / total, p2 / total


def shrink_probs_1x2(
    model_probs: dict[str, float],
    market_probs: dict[str, float],
    minute: int,
) -> dict[str, float]:
    """Aplica market shrinkage diretamente no espaço de probabilidades 1X2.

    Substitui a conversão lambda → Monte Carlo com uma mistura direta:
        p_final = α(min) × p_market + (1 - α) × p_model

    Mais estável numericamente e evita a dupla aplicação de market info
    (lambda shrinkage + blend_ensemble).

    Args:
        model_probs: {"1": p, "X": p, "2": p} do modelo (Poisson/ensemble).
        market_probs: {"1": p, "X": p, "2": p} do mercado (devigged).
        minute: minuto atual do jogo.

    Returns:
        {"1": p, "X": p, "2": p} normalizado.
    """
    alpha = compute_alpha(minute)
    keys = ("1", "X", "2")
    result = {
        k: alpha * market_probs.get(k, 1 / 3) + (1 - alpha) * model_probs.get(k, 1 / 3)
        for k in keys
    }
    total = sum(result.values())
    if total > 0:
        result = {k: v / total for k, v in result.items()}
    return result


def shrink_lambda(
    lambda_model_home: float,
    lambda_model_away: float,
    market_prob_home: float,
    market_prob_draw: float,
    market_prob_away: float,
    minute: int,
    match_minutes: int = 90,
) -> ShrinkageResult:
    """Aplica market shrinkage: mistura λ do modelo com λ implícito do mercado.

    Args:
        lambda_model_home: λ_home do modelo (pós-Bayesian).
        lambda_model_away: λ_away do modelo.
        market_prob_home: P(1) do mercado (corrigida pela margem).
        market_prob_draw: P(X) do mercado.
        market_prob_away: P(2) do mercado.
        minute: minuto atual do jogo.
        match_minutes: duração total.

    Returns:
        ShrinkageResult com λ_shrunk e metadados.
    """
    alpha = compute_alpha(minute)

    lambda_market_home, lambda_market_away = market_prob_to_lambda(
        market_prob_home, market_prob_draw, market_prob_away, match_minutes
    )

    lambda_shrunk_home = alpha * lambda_market_home + (1 - alpha) * lambda_model_home
    lambda_shrunk_away = alpha * lambda_market_away + (1 - alpha) * lambda_model_away

    return ShrinkageResult(
        lambda_shrunk_home=round(lambda_shrunk_home, 4),
        lambda_shrunk_away=round(lambda_shrunk_away, 4),
        alpha_used=round(alpha, 4),
        lambda_model_home=round(lambda_model_home, 4),
        lambda_model_away=round(lambda_model_away, 4),
        lambda_market_home=round(lambda_market_home, 4),
        lambda_market_away=round(lambda_market_away, 4),
    )
