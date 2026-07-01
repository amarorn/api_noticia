"""Ajustes dinâmicos de λ in-play com dados ao vivo (ScoreAlarm / timeline)."""
from __future__ import annotations

from typing import Any

import numpy as np

from config import settings

# Tipos ScoreAlarm (overview live_events) — alinhado a ingest.superbet.scorealarm.ticker
_GOAL_EVENT_TYPE = 4
_CORNER_EVENT_TYPE = 14
_CARD_EVENT_TYPE = 1


def scorealarm_timeline_to_momentum_events(
    timeline: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Converte timeline ScoreAlarm em eventos para momentum / ajuste por placar."""
    events: list[dict[str, Any]] = []
    for ev in timeline or []:
        event_type = int(ev.get("type") or 0)
        side = int(ev.get("side") or 0)
        team = "home" if side == 1 else "away" if side == 2 else ""
        minute = int(ev.get("minute") or 0)
        if event_type == _GOAL_EVENT_TYPE:
            events.append(
                {
                    "event_type": "goal",
                    "minute": minute,
                    "team": team,
                    "detail": ev.get("label") or "gol",
                    "source": "scorealarm",
                }
            )
        elif event_type == _CORNER_EVENT_TYPE:
            events.append(
                {
                    "event_type": "corner",
                    "minute": minute,
                    "team": team,
                    "detail": "escanteio",
                    "source": "scorealarm",
                }
            )
        elif event_type == _CARD_EVENT_TYPE:
            subtype = int(ev.get("subtype") or 0)
            if subtype in (3, 4):
                events.append(
                    {
                        "event_type": "red_card",
                        "minute": minute,
                        "team": team,
                        "detail": "cartão vermelho",
                        "source": "scorealarm",
                    }
                )
            else:
                events.append(
                    {
                        "event_type": "yellow_card",
                        "minute": minute,
                        "team": team,
                        "detail": "cartão amarelo",
                        "source": "scorealarm",
                    }
                )
    return events


def has_scorealarm_momentum(momentum_events: list[dict] | None) -> bool:
    return any((ev or {}).get("source") == "scorealarm" for ev in (momentum_events or []))


def adjust_lambdas_from_live_stats(
    lambda_home: float,
    lambda_away: float,
    *,
    live_stats: dict[str, float] | None,
    max_shift: float | None = None,
) -> tuple[float, float, dict[str, Any]]:
    """Ajusta λ com posse e chutes no gol (ScoreAlarm overview/SSE)."""
    cap = max_shift if max_shift is not None else settings.inplay_live_stats_max_shift
    if not live_stats or cap <= 0:
        return lambda_home, lambda_away, {"applied": False}

    home_poss = live_stats.get("home_possession_pct")
    away_poss = live_stats.get("away_possession_pct")
    home_sot = live_stats.get("home_shots_on_target")
    away_sot = live_stats.get("away_shots_on_target")

    shift_h = 0.0
    shift_a = 0.0
    reasons: list[str] = []

    if home_poss is not None and away_poss is not None:
        poss_diff = float(home_poss) - float(away_poss)
        poss_factor = np.clip(poss_diff / 100.0 * 0.08, -cap * 0.6, cap * 0.6)
        shift_h += poss_factor
        shift_a -= poss_factor
        if abs(poss_diff) >= 8:
            reasons.append(f"posse {home_poss:.0f}%×{away_poss:.0f}%")

    if home_sot is not None and away_sot is not None:
        sot_diff = float(home_sot) - float(away_sot)
        sot_factor = np.clip(sot_diff * 0.03, -cap * 0.5, cap * 0.5)
        shift_h += sot_factor
        shift_a -= sot_factor
        if abs(sot_diff) >= 1:
            reasons.append(f"chutes no gol {int(home_sot)}×{int(away_sot)}")

    shift_h = float(np.clip(shift_h, -cap, cap))
    shift_a = float(np.clip(shift_a, -cap, cap))

    if abs(shift_h) < 0.005 and abs(shift_a) < 0.005:
        return lambda_home, lambda_away, {"applied": False}

    out_h = float(np.clip(lambda_home * (1.0 + shift_h), lambda_home * 0.85, lambda_home * 1.2))
    out_a = float(np.clip(lambda_away * (1.0 + shift_a), lambda_away * 0.85, lambda_away * 1.2))
    return out_h, out_a, {
        "applied": True,
        "source": "live_stats",
        "shift_home_pct": round(shift_h * 100, 2),
        "shift_away_pct": round(shift_a * 100, 2),
        "reasons": reasons,
    }


def apply_trailing_chase_boost(
    lam_remaining_home: float,
    lam_remaining_away: float,
    *,
    minute: int,
    home_score: int,
    away_score: int,
    timeline: list[dict[str, Any]] | None,
    window_minutes: int = 15,
    max_boost: float = 0.10,
) -> tuple[float, float, dict[str, Any] | None]:
    """Boost no λ restante do time que acabou de tomar gol (efeito reação)."""
    if not timeline or home_score == away_score:
        return lam_remaining_home, lam_remaining_away, None

    latest_goal_minute: int | None = None
    latest_goal_side: int | None = None
    for ev in timeline:
        if int(ev.get("type") or 0) != _GOAL_EVENT_TYPE:
            continue
        g_min = int(ev.get("minute") or 0)
        if latest_goal_minute is None or g_min > latest_goal_minute:
            latest_goal_minute = g_min
            latest_goal_side = int(ev.get("side") or 0)

    if latest_goal_minute is None or minute - latest_goal_minute > window_minutes:
        return lam_remaining_home, lam_remaining_away, None

    trailing_side = "home" if away_score > home_score else "away"
    scoring_side = 1 if home_score > away_score else 2
    if latest_goal_side != scoring_side:
        return lam_remaining_home, lam_remaining_away, None

    deficit = abs(home_score - away_score)
    boost = min(max_boost, 0.04 + deficit * 0.02)
    if trailing_side == "home":
        return (
            lam_remaining_home * (1.0 + boost),
            lam_remaining_away,
            {
                "applied": True,
                "source": "trailing_chase",
                "minute": latest_goal_minute,
                "boost_pct": round(boost * 100, 1),
                "team": "home",
            },
        )
    return (
        lam_remaining_home,
        lam_remaining_away * (1.0 + boost),
        {
            "applied": True,
            "source": "trailing_chase",
            "minute": latest_goal_minute,
            "boost_pct": round(boost * 100, 1),
            "team": "away",
        },
    )


def adjust_lambdas_from_xg(
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
    """Ajusta λ com xG acumulado ao vivo (Sofascore/ScoreAlarm).

    A ideia é comparar a taxa de gols esperada (xG) observada até o minuto
    atual com o λ pré-jogo. Quanto mais minutos decorridos, maior o peso da
    evidência ao vivo. O ajuste é suave e limitado para evitar overreaction.
    """
    cap = max_shift if max_shift is not None else settings.inplay_xg_max_shift
    w_max = weight_max if weight_max is not None else settings.inplay_xg_weight_max

    if minute <= 0 or match_minutes <= 0:
        return lambda_home, lambda_away, None
    if home_xg is None and away_xg is None:
        return lambda_home, lambda_away, None

    elapsed_fraction = minute / match_minutes

    # Peso da evidência ao vivo cresce com o tempo, limitado por w_max
    # Usar uma curva quadrática: aos 45' ~25%, aos 90' ~w_max
    live_weight = min(w_max, w_max * (elapsed_fraction ** 2) / 0.5)
    if live_weight <= 0.01:
        return lambda_home, lambda_away, None

    # λ observado via xG: se o ritmo de xG continuar pelo restante do jogo,
    # quantos gols esperaríamos em 90 min?
    lambda_obs_home = (home_xg or 0.0) / elapsed_fraction if home_xg is not None else lambda_home
    lambda_obs_away = (away_xg or 0.0) / elapsed_fraction if away_xg is not None else lambda_away

    # Blending com λ atual (que já inclui Bayesian update e live_stats)
    new_home = (1.0 - live_weight) * lambda_home + live_weight * lambda_obs_home
    new_away = (1.0 - live_weight) * lambda_away + live_weight * lambda_obs_away

    # Limitar shift em relação ao λ atual
    lower_h = lambda_home * (1.0 - cap)
    upper_h = lambda_home * (1.0 + cap)
    lower_a = lambda_away * (1.0 - cap)
    upper_a = lambda_away * (1.0 + cap)

    new_home = float(np.clip(new_home, lower_h, upper_h))
    new_away = float(np.clip(new_away, lower_a, upper_a))

    return new_home, new_away, {
        "applied": True,
        "source": "live_xg",
        "minute": minute,
        "elapsed_fraction": round(elapsed_fraction, 3),
        "live_weight": round(live_weight, 3),
        "home_xg": home_xg,
        "away_xg": away_xg,
        "lambda_obs_home": round(lambda_obs_home, 3),
        "lambda_obs_away": round(lambda_obs_away, 3),
        "shift_home_pct": round((new_home / lambda_home - 1.0) * 100, 2),
        "shift_away_pct": round((new_away / lambda_away - 1.0) * 100, 2),
    }


def build_lambda_adjustment_report(
    *,
    lambda_prior_home: float,
    lambda_prior_away: float,
    lambda_full_home: float,
    lambda_full_away: float,
    steps: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Resumo para API/frontend quando λ diverge do pré-jogo."""
    delta_h = lambda_full_home - lambda_prior_home
    delta_a = lambda_full_away - lambda_prior_away
    if abs(delta_h) < 0.02 and abs(delta_a) < 0.02 and not steps:
        return None
    return {
        "lambda_prior_home": round(lambda_prior_home, 3),
        "lambda_prior_away": round(lambda_prior_away, 3),
        "lambda_full_home": round(lambda_full_home, 3),
        "lambda_full_away": round(lambda_full_away, 3),
        "delta_home": round(delta_h, 3),
        "delta_away": round(delta_a, 3),
        "steps": steps,
    }


__all__ = [
    "adjust_lambdas_from_live_stats",
    "adjust_lambdas_from_xg",
    "apply_trailing_chase_boost",
    "build_lambda_adjustment_report",
    "has_scorealarm_momentum",
    "scorealarm_timeline_to_momentum_events",
]
