"""Ajuste xG ao vivo mais agressivo — aumenta peso e reduz limitações.

Este módulo estende o ajuste xG padrão (wc_inplay_live_adjust.py) com:
1. Peso máximo maior (default 0.40 → 0.65)
2. Curva de peso mais rápida (quadrática → linear após 30')
3. Cap de shift maior (0.25 → 0.40)
4. Ajuste por minuto decorrido (mais minutos = mais confiança na evidência xG)

A configuração é controlada por novas settings:
  - inplay_xg_aggressive_enabled: ativa modo agressivo
  - inplay_xg_aggressive_weight_max: peso máximo (default 0.65)
  - inplay_xg_aggressive_cap: max shift (default 0.40)
"""
from __future__ import annotations

from typing import Any

import numpy as np

from config import settings


def adjust_lambdas_from_xg_aggressive(
    lambda_home: float,
    lambda_away: float,
    *,
    home_xg: float | None,
    away_xg: float | None,
    minute: int,
    match_minutes: int = 90,
    max_shift: float | None = None,
    weight_max: float | None = None,
) -> tuple[float, float, dict[str, Any] | None]:
    """Ajusta λ com xG acumulado ao vivo — versão agressiva.

    Diferenças do modo padrão:
    - Peso máximo: 0.65 (vs 0.40 padrão)
    - Curva: linear após 30' (vs quadrática pura)
    - Cap: 0.40 (vs 0.25 padrão)
    - Ajuste por minuto: aos 30' ~30% do peso, aos 60' ~60%, aos 90' ~100%

    Args:
        lambda_home, lambda_away: λ atuais (após Bayesian, live_stats, etc.)
        home_xg, away_xg: xG acumulado observado ao vivo
        minute: minuto atual
        match_minutes: duração total (default 90)
        max_shift: cap máximo de shift (default settings.inplay_xg_aggressive_cap)
        weight_max: peso máximo da evidência xG (default settings.inplay_xg_aggressive_weight_max)

    Returns:
        (lambda_home_novo, lambda_away_novo, meta_dict)
    """
    cap = max_shift if max_shift is not None else getattr(
        settings, "inplay_xg_aggressive_cap", 0.40
    )
    w_max = weight_max if weight_max is not None else getattr(
        settings, "inplay_xg_aggressive_weight_max", 0.65
    )

    if minute <= 0 or match_minutes <= 0:
        return lambda_home, lambda_away, None
    if home_xg is None and away_xg is None:
        return lambda_home, lambda_away, None

    elapsed_fraction = minute / match_minutes
    remaining_fraction = max(0.0, 1.0 - elapsed_fraction)

    # Curva de peso: linear pura (mais agressiva que quadrática)
    # Aos 30' → 33% do w_max, aos 60' → 67%, aos 90' → 100%
    live_weight = min(w_max, w_max * elapsed_fraction)

    # Boost adicional se muitos chutes no gol (indicador de dominância)
    # Não implementado aqui — deixado para live_stats adjust

    if live_weight <= 0.01:
        return lambda_home, lambda_away, None

    # λ observado via xG: projetado para 90 min
    lambda_obs_home = (home_xg or 0.0) / elapsed_fraction if home_xg is not None else lambda_home
    lambda_obs_away = (away_xg or 0.0) / elapsed_fraction if away_xg is not None else lambda_away

    # Blending com λ atual
    new_home = (1.0 - live_weight) * lambda_home + live_weight * lambda_obs_home
    new_away = (1.0 - live_weight) * lambda_away + live_weight * lambda_obs_away

    # Limitar shift em relação ao λ atual (cap mais permissivo)
    lower_h = lambda_home * (1.0 - cap)
    upper_h = lambda_home * (1.0 + cap)
    lower_a = lambda_away * (1.0 - cap)
    upper_a = lambda_away * (1.0 + cap)

    new_home = float(np.clip(new_home, lower_h, upper_h))
    new_away = float(np.clip(new_away, lower_a, upper_a))

    return new_home, new_away, {
        "applied": True,
        "source": "live_xg_aggressive",
        "minute": minute,
        "elapsed_fraction": round(elapsed_fraction, 3),
        "live_weight": round(live_weight, 3),
        "home_xg": home_xg,
        "away_xg": away_xg,
        "lambda_obs_home": round(lambda_obs_home, 3),
        "lambda_obs_away": round(lambda_obs_away, 3),
        "shift_home_pct": round((new_home / lambda_home - 1.0) * 100, 2),
        "shift_away_pct": round((new_away / lambda_away - 1.0) * 100, 2),
        "mode": "aggressive",
    }


def should_use_aggressive_xg(minute: int, live_stats: dict[str, float] | None) -> bool:
    """Decide se deve usar xG agressivo baseado em heurísticas.

    Critérios:
    - Minuto ≥ 20 (evita overreaction no início)
    - xG disponível para pelo menos um time
    - Se posse de bola disponível, requer diferença ≥ 15% (dominância clara)
    """
    if minute < 20:
        return False
    if not live_stats:
        return False
    has_xg = live_stats.get("home_xg") is not None or live_stats.get("away_xg") is not None
    if not has_xg:
        return False

    # Se posse disponível, só ativa se há dominância clara
    home_poss = live_stats.get("home_possession_pct")
    away_poss = live_stats.get("away_possession_pct")
    if home_poss is not None and away_poss is not None:
        poss_diff = abs(home_poss - away_poss)
        if poss_diff < 15:
            return False  # Jogo equilibrado, não forçar xG agressivo

    return True
