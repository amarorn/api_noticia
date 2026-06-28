"""Momentum ao vivo: ajusta λ com base no contexto tático do jogo em andamento.

O momentum captura efeitos que o λ pré-jogo (ou Bayesian) não enxerga:
- Time na frente tende a recuar → λ_ataque diminui, adversário pressiona → λ_adversário sobe
- Minuto avançado → ambos os λ se comprimem (menos tempo = menos gols esperados)
- Cartão vermelho → time afetado perde capacidade ofensiva/defensiva
- Substituição ofensiva → time busca gol → λ sobe

Fase 2: suporta coeficientes calibrados via MLE (InPlayCoefficients).
Se disponíveis, substitui as constantes manuais por β's estimados.

Referência: docs/analise-inplay-backend.md § 4.1
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from models.wc_inplay_coefficients import InPlayCoefficients, load_inplay_coefficients


# --- Constantes de ajuste (tunable via config futuro) ---

# Efeito do placar no comportamento tático
_GOAL_DIFF_ATTACK_FACTOR = 0.06  # cada gol de vantagem reduz λ_ataque próprio em 6%
_GOAL_DIFF_DEFEND_PRESSURE = 0.08  # cada gol atrás aumenta λ_ataque em 8% (time pressiona)

# Compressão temporal: nos últimos minutos há pressa mas menos tempo
_LATE_GAME_COMPRESS_START = 75  # minuto a partir do qual comprime
_LATE_GAME_COMPRESS_FACTOR = 0.85  # multiplicador de λ acima de 75'

# Cartão vermelho
_RED_CARD_OWN_PENALTY = 0.15  # reduz λ_ataque do time com -1 jogador em 15%
_RED_CARD_OPP_BOOST = 0.10  # aumenta λ_ataque adversário em 10%

# Substituição ofensiva
_OFFENSIVE_SUB_BOOST = 0.05  # +5% no λ_ataque do time que fez sub ofensiva

# Lesão: jogador sai machucado → time perde poder ofensivo/defensivo
_INJURY_OWN_PENALTY = 0.07   # −7% no λ do time que sofreu lesão


@dataclass
class GameEvent:
    """Evento de jogo ao vivo (gol, cartão, substituição, etc.)."""

    event_type: str  # "goal", "red_card", "yellow_card", "sub_offensive", "sub_defensive"
    minute: int
    team: str  # "home" ou "away"
    detail: str = ""


@dataclass
class MomentumContext:
    """Contexto completo para cálculo de momentum."""

    home_score: int
    away_score: int
    minute: int
    match_minutes: int = 90
    events: list[GameEvent] = field(default_factory=list)
    home_corners: int = 0
    away_corners: int = 0


@dataclass
class MomentumResult:
    """Resultado do ajuste de momentum: fatores multiplicadores para λ."""

    home_factor: float  # multiplicador para λ_home (ex: 1.12 = +12%)
    away_factor: float  # multiplicador para λ_away
    reasons: list[str] = field(default_factory=list)  # explicações humanas


def compute_momentum(ctx: MomentumContext) -> MomentumResult:
    """Calcula fatores de momentum que ajustam λ_home e λ_away.

    Retorna multiplicadores (ex: 1.0 = sem ajuste, 0.85 = reduz 15%, 1.10 = aumenta 10%).
    Os fatores são aplicados sobre o λ_full (pós-Bayesian) antes de calcular λ_remaining.

    Regras implementadas (fase 1 — baseado em placar + minuto + eventos):
    1. Efeito do placar: time na frente recua, time atrás pressiona
    2. Compressão temporal: menos gols esperados na reta final
    3. Cartão vermelho: penaliza time com inferioridade numérica
    4. Substituição ofensiva: boost para time buscando gol
    """
    home_factor = 1.0
    away_factor = 1.0
    reasons: list[str] = []

    # --- 1. Efeito do placar ---
    goal_diff = ctx.home_score - ctx.away_score

    if goal_diff > 0:
        # Casa na frente: recua → ataque reduz; fora pressiona → ataque aumenta
        recuo = min(goal_diff * _GOAL_DIFF_ATTACK_FACTOR, 0.20)
        pressao = min(goal_diff * _GOAL_DIFF_DEFEND_PRESSURE, 0.25)
        home_factor -= recuo
        away_factor += pressao
        reasons.append(
            f"Casa lidera por {goal_diff}: ataque casa -{recuo*100:.0f}%, "
            f"ataque fora +{pressao*100:.0f}% (pressão)"
        )
    elif goal_diff < 0:
        # Fora na frente: fora recua, casa pressiona
        diff = abs(goal_diff)
        recuo = min(diff * _GOAL_DIFF_ATTACK_FACTOR, 0.20)
        pressao = min(diff * _GOAL_DIFF_DEFEND_PRESSURE, 0.25)
        away_factor -= recuo
        home_factor += pressao
        reasons.append(
            f"Fora lidera por {diff}: ataque fora -{recuo*100:.0f}%, "
            f"ataque casa +{pressao*100:.0f}% (pressão)"
        )

    # --- 2. Compressão temporal ---
    if ctx.minute >= _LATE_GAME_COMPRESS_START:
        # Nos últimos 15 minutos, ambos comprimem (urgência vs cansaço)
        # Mas o time atrás comprime MENOS (está desesperado)
        compress = _LATE_GAME_COMPRESS_FACTOR
        if goal_diff > 0:
            # Casa na frente: comprime mais (gerencia jogo)
            home_factor *= compress * 0.9  # comprime 23.5%
            away_factor *= compress * 1.05  # comprime só 10.75% (ainda pressiona)
        elif goal_diff < 0:
            away_factor *= compress * 0.9
            home_factor *= compress * 1.05
        else:
            # Empate: ambos comprimem igualmente
            home_factor *= compress
            away_factor *= compress
        reasons.append(
            f"Min {ctx.minute}' (reta final): compressão temporal aplicada"
        )

    # --- 3. Eventos: cartão vermelho ---
    home_reds = sum(
        1 for e in ctx.events if e.event_type == "red_card" and e.team == "home"
    )
    away_reds = sum(
        1 for e in ctx.events if e.event_type == "red_card" and e.team == "away"
    )

    if home_reds > 0:
        penalty = min(home_reds * _RED_CARD_OWN_PENALTY, 0.30)
        boost = min(home_reds * _RED_CARD_OPP_BOOST, 0.20)
        home_factor -= penalty
        away_factor += boost
        reasons.append(
            f"Casa com {home_reds} cartão(ões) vermelho(s): "
            f"ataque casa -{penalty*100:.0f}%, ataque fora +{boost*100:.0f}%"
        )

    if away_reds > 0:
        penalty = min(away_reds * _RED_CARD_OWN_PENALTY, 0.30)
        boost = min(away_reds * _RED_CARD_OPP_BOOST, 0.20)
        away_factor -= penalty
        home_factor += boost
        reasons.append(
            f"Fora com {away_reds} cartão(ões) vermelho(s): "
            f"ataque fora -{penalty*100:.0f}%, ataque casa +{boost*100:.0f}%"
        )

    # --- 4. Substituições ofensivas ---
    home_off_subs = sum(
        1 for e in ctx.events if e.event_type == "sub_offensive" and e.team == "home"
    )
    away_off_subs = sum(
        1 for e in ctx.events if e.event_type == "sub_offensive" and e.team == "away"
    )

    if home_off_subs > 0:
        boost = min(home_off_subs * _OFFENSIVE_SUB_BOOST, 0.15)
        home_factor += boost
        reasons.append(f"Casa fez {home_off_subs} sub(s) ofensiva(s): +{boost*100:.0f}%")

    if away_off_subs > 0:
        boost = min(away_off_subs * _OFFENSIVE_SUB_BOOST, 0.15)
        away_factor += boost
        reasons.append(f"Fora fez {away_off_subs} sub(s) ofensiva(s): +{boost*100:.0f}%")

    # --- 5. Lesões ---
    home_injuries = sum(
        1 for e in ctx.events if e.event_type == "injury" and e.team == "home"
    )
    away_injuries = sum(
        1 for e in ctx.events if e.event_type == "injury" and e.team == "away"
    )
    if home_injuries > 0:
        penalty = min(home_injuries * _INJURY_OWN_PENALTY, 0.20)
        home_factor -= penalty
        reasons.append(f"Casa com {home_injuries} lesão(ões): ataque -{penalty*100:.0f}%")
    if away_injuries > 0:
        penalty = min(away_injuries * _INJURY_OWN_PENALTY, 0.20)
        away_factor -= penalty
        reasons.append(f"Fora com {away_injuries} lesão(ões): ataque -{penalty*100:.0f}%")

    # --- 6. Pressão via escanteios (proxy de ataque real ao vivo) ---
    total_corners = ctx.home_corners + ctx.away_corners
    if total_corners >= 2:
        # Proporção de escanteios como medida de pressão ofensiva
        # Dominância de 75% nos escanteios = +3% no λ
        home_share = ctx.home_corners / total_corners
        away_share = ctx.away_corners / total_corners
        # Converte share em ajuste: 0.5 = 0%, 0.75 = +3%, 1.0 = +6%
        corner_boost_home = (home_share - 0.5) * 0.12
        corner_boost_away = (away_share - 0.5) * 0.12
        # Limitar impacto
        corner_boost_home = max(-0.06, min(corner_boost_home, 0.06))
        corner_boost_away = max(-0.06, min(corner_boost_away, 0.06))
        home_factor += corner_boost_home
        away_factor += corner_boost_away
        if abs(corner_boost_home) >= 0.01:
            reasons.append(
                f"Escanteios: casa {ctx.home_corners}×{ctx.away_corners} fora → "
                f"ataque casa {corner_boost_home:+.0%}, ataque fora {corner_boost_away:+.0%}"
            )
    home_factor = max(0.50, min(home_factor, 1.80))
    away_factor = max(0.50, min(away_factor, 1.80))

    return MomentumResult(
        home_factor=round(home_factor, 4),
        away_factor=round(away_factor, 4),
        reasons=reasons,
    )


def adjust_lambdas(
    lambda_home: float,
    lambda_away: float,
    ctx: MomentumContext,
) -> tuple[float, float, MomentumResult]:
    """Aplica momentum sobre os λ e retorna os valores ajustados + detalhes.

    Uso típico:
        lam_h_adj, lam_a_adj, momentum = adjust_lambdas(lam_h, lam_a, ctx)
    """
    result = compute_momentum(ctx)
    return (
        lambda_home * result.home_factor,
        lambda_away * result.away_factor,
        result,
    )


# --- Cache global de coeficientes calibrados ---
_cached_coefficients: InPlayCoefficients | None = None
_coefficients_loaded: bool = False


def _get_calibrated_coefficients() -> InPlayCoefficients | None:
    """Carrega coeficientes calibrados (com cache em memória)."""
    global _cached_coefficients, _coefficients_loaded
    if not _coefficients_loaded:
        _cached_coefficients = load_inplay_coefficients()
        _coefficients_loaded = True
    return _cached_coefficients


def compute_momentum_calibrated(ctx: MomentumContext) -> MomentumResult:
    """Versão calibrada do momentum usando β's do MLE (Fase 2).

    Se coeficientes calibrados estiverem disponíveis E a feature flag
    `inplay_use_calibrated_coefficients` estiver ativa, usa o modelo log-linear:
        factor = exp(X @ β)

    Se não disponíveis ou flag desligada, cai no compute_momentum() default.
    """
    from config import settings

    if not settings.inplay_use_calibrated_coefficients:
        return compute_momentum(ctx)

    coefs = _get_calibrated_coefficients()
    if coefs is None or not coefs.momentum_betas:
        return compute_momentum(ctx)

    # Construir vetor de features (mesma ordem de MOMENTUM_FEATURES no tune)
    goal_diff = ctx.home_score - ctx.away_score
    late_game_val = max(0, ctx.minute - 75) / 15.0
    total_corners = ctx.home_corners + ctx.away_corners
    corner_share = (ctx.home_corners / total_corners - 0.5) if total_corners > 0 else 0.0

    home_reds = sum(1 for e in ctx.events if e.event_type == "red_card" and e.team == "home")
    away_reds = sum(1 for e in ctx.events if e.event_type == "red_card" and e.team == "away")

    features = {
        "intercept": 1.0,
        "goal_diff": float(goal_diff),
        "goal_diff_squared": float(goal_diff ** 2),
        "late_game": late_game_val,
        "home_red_cards": float(home_reds),
        "away_red_cards": float(away_reds),
        "corner_share": corner_share,
        "goal_diff_x_late": float(goal_diff) * late_game_val,
    }

    # Calcular log(factor) = Σ β_i × x_i
    log_factor = 0.0
    for beta in coefs.momentum_betas:
        x_val = features.get(beta.name, 0.0)
        log_factor += beta.value * x_val

    # factor = exp(log_factor), com clamp para segurança
    factor = float(np.clip(np.exp(log_factor), 0.50, 1.80))

    # Para home vs away: invertemos o sinal do goal_diff para o away
    features_away = features.copy()
    features_away["goal_diff"] = -float(goal_diff)
    features_away["goal_diff_squared"] = float(goal_diff ** 2)
    features_away["goal_diff_x_late"] = -float(goal_diff) * late_game_val
    features_away["home_red_cards"] = float(away_reds)
    features_away["away_red_cards"] = float(home_reds)
    features_away["corner_share"] = -corner_share

    log_factor_away = 0.0
    for beta in coefs.momentum_betas:
        x_val = features_away.get(beta.name, 0.0)
        log_factor_away += beta.value * x_val

    factor_away = float(np.clip(np.exp(log_factor_away), 0.50, 1.80))

    reasons = [
        f"Momentum calibrado (MLE): home_factor={factor:.3f}, away_factor={factor_away:.3f}",
        f"  goal_diff={goal_diff}, late_game={late_game_val:.2f}, reds=({home_reds}/{away_reds})",
    ]

    return MomentumResult(
        home_factor=round(factor, 4),
        away_factor=round(factor_away, 4),
        reasons=reasons,
    )


def momentum_from_dict(data: dict[str, Any]) -> MomentumContext:
    """Constrói MomentumContext a partir de um dict (ex: JSON do frontend ou advice)."""
    events = []
    for ev in data.get("events", []):
        events.append(GameEvent(
            event_type=ev.get("event_type", "unknown"),
            minute=ev.get("minute", 0),
            team=ev.get("team", "home"),
            detail=ev.get("detail", ""),
        ))
    return MomentumContext(
        home_score=data.get("home_score", 0),
        away_score=data.get("away_score", 0),
        minute=data.get("minute", 0),
        match_minutes=data.get("match_minutes", 90),
        events=events,
    )
