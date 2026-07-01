"""Ajuste H2H (head-to-head) em λ in-play.

Quando duas seleções têm histórico direto significativo (≥2 jogos), o modelo
in-play pode usar esse histórico como prior adicional — especialmente para:

1. **Comeback boost**: time com domínio histórico (ex: Brasil 3/3 vs Haiti)
   recebe nudge de λ quando está perdendo, pois o histórico sugere
   capacidade de reação.
2. **Over/under calibration**: média de gols H2H ajusta expectativa de
   mercados de total — H2H com média alta (ex: 5.0) aumenta λ residual.
3. **Draw suppression**: se H2H tem poucos empates e um time domina,
   prob_draw in-play é ligeiramente penalizada.

O ajuste é aplicado APÓS o Bayesian update e ANTES do score_diff adjust,
para que o histórico H2H atue como "âncora de confiança" no λ prior,
sem sobrepor a evidência ao vivo (gols, stats).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class H2HAdjust:
    """Resultado do ajuste H2H em λ in-play."""

    lambda_home_factor: float
    lambda_away_factor: float
    draw_penalty: float  # 0 = sem penalidade, >0 reduz prob_draw
    applied: bool
    reason: str


# ---------------------------------------------------------------------------
# Thresholds e fatores
# ---------------------------------------------------------------------------
_MIN_H2H_GAMES = 2
_DOMINANCE_WIN_RATE = 0.75  # ex: 3/3 = 1.0 → domínio total
_DOMINANCE_GOAL_DIFF_PER_GAME = 2.0  # ex: (15-1)/3 = 4.67 → domínio
_STRONG_DOMINANCE_GAMES = 3

# Fatores de ajuste λ quando time dominante está perdendo (comeback boost)
_COMEBACK_BOOST_MIN = 1.03
_COMEBACK_BOOST_MAX = 1.12
_COMEBACK_BOOST_CAP = 1.15  # hard cap para evitar overreaction

# Fatores de ajuste λ por média de gols H2H (over/under calibration)
_HIGH_GOALS_THRESHOLD = 3.5  # média total gols/jogo H2H
_HIGH_GOALS_BOOST = 1.06
_LOW_GOALS_THRESHOLD = 2.0
_LOW_GOALS_PENALTY = 0.95

# Penalidade em prob_draw quando H2H tem poucos empates
_DRAW_SUPPRESSION_RATE = 0.15  # se empate_rate < 15%, aplica
_DRAW_SUPPRESSION_FACTOR = 0.92


def _clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))


def parse_h2h_from_context(match_context: dict[str, Any] | None) -> dict[str, Any] | None:
    """Extrai dados H2H do match_context (formato TXT report ou ScoreAlarm)."""
    if not match_context:
        return None

    # Formato TXT report (carregado via scripts/load_*_context.py)
    h2h = match_context.get("h2h")
    if isinstance(h2h, dict) and h2h.get("total", 0) >= _MIN_H2H_GAMES:
        return {
            "home_team": h2h.get("home_team", ""),
            "away_team": h2h.get("away_team", ""),
            "total": h2h.get("total", 0),
            "home_wins": h2h.get("home_wins", 0),
            "draws": h2h.get("draws", 0),
            "away_wins": h2h.get("away_wins", 0),
            "home_goals": h2h.get("home_goals", 0),
            "away_goals": h2h.get("away_goals", 0),
            "avg_total_goals": h2h.get("avg_total_goals", 0.0),
        }

    # Formato ScoreAlarm (aninhado em context)
    scorealarm = match_context.get("scorealarm", {})
    if isinstance(scorealarm, dict):
        h2h = scorealarm.get("h2h", {})
        if isinstance(h2h, dict) and h2h.get("total", 0) >= _MIN_H2H_GAMES:
            return {
                "home_team": match_context.get("home_team", ""),
                "away_team": match_context.get("away_team", ""),
                "total": h2h.get("total", 0),
                "home_wins": h2h.get("home_wins", 0),
                "draws": h2h.get("draws", 0),
                "away_wins": h2h.get("away_wins", 0),
                "home_goals": 0,
                "away_goals": 0,
                "avg_total_goals": 0.0,
            }

    return None


def compute_h2h_adjust(
    h2h_data: dict[str, Any] | None,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    minute: int,
    lambda_full_home: float,
    lambda_full_away: float,
) -> H2HAdjust:
    """Computa ajuste H2H em λ in-play.

    Lógica principal:
    1. Se histórico muito curto (<2 jogos): sem ajuste.
    2. Se time A domina H2H (≥75% vitórias OU diff gols/jogo ≥2.0) e está
       perdendo: aplica comeback boost em λ do time A.
    3. Se média gols H2H é alta (>3.5): boost em ambos λ (jogo aberto).
    4. Se média gols H2H é baixa (<2.0): penaliza ambos λ (jogo fechado).
    5. Se taxa de empates H2H é muito baixa (<15%): aplica draw suppression.
    """
    if not h2h_data or h2h_data.get("total", 0) < _MIN_H2H_GAMES:
        return H2HAdjust(
            lambda_home_factor=1.0,
            lambda_away_factor=1.0,
            draw_penalty=0.0,
            applied=False,
            reason="histórico insuficiente",
        )

    total = h2h_data["total"]
    home_wins = h2h_data.get("home_wins", 0)
    away_wins = h2h_data.get("away_wins", 0)
    draws = h2h_data.get("draws", 0)
    home_goals = h2h_data.get("home_goals", 0)
    away_goals = h2h_data.get("away_goals", 0)
    avg_total_goals = h2h_data.get("avg_total_goals", 0.0)

    # --- Determinar domínio histórico ---
    home_win_rate = home_wins / total if total > 0 else 0.0
    away_win_rate = away_wins / total if total > 0 else 0.0
    draw_rate = draws / total if total > 0 else 0.0
    goal_diff_per_game = (home_goals - away_goals) / total if total > 0 else 0.0

    home_dominates = (
        home_win_rate >= _DOMINANCE_WIN_RATE
        or (total >= _STRONG_DOMINANCE_GAMES and goal_diff_per_game >= _DOMINANCE_GOAL_DIFF_PER_GAME)
    )
    away_dominates = (
        away_win_rate >= _DOMINANCE_WIN_RATE
        or (total >= _STRONG_DOMINANCE_GAMES and goal_diff_per_game <= -_DOMINANCE_GOAL_DIFF_PER_GAME)
    )

    # --- 1. Comeback boost: time dominante perdendo ---
    lambda_home_factor = 1.0
    lambda_away_factor = 1.0
    draw_penalty = 0.0
    reasons: list[str] = []

    score_diff = home_score - away_score

    if home_dominates and score_diff < 0:
        # Casa domina H2H mas está perdendo → boost casa
        abs_diff = min(abs(score_diff), 4)
        boost = _clamp(
            _COMEBACK_BOOST_MIN + (abs_diff - 1) * 0.03,
            _COMEBACK_BOOST_MIN,
            _COMEBACK_BOOST_MAX,
        )
        # Cap hard
        boost = min(boost, _COMEBACK_BOOST_CAP)
        lambda_home_factor = boost
        reasons.append(f"comeback boost {home_team} (domina H2H {home_wins}/{total}, perde {abs_diff}g)")

    if away_dominates and score_diff > 0:
        # Fora domina H2H mas está perdendo → boost fora
        abs_diff = min(abs(score_diff), 4)
        boost = _clamp(
            _COMEBACK_BOOST_MIN + (abs_diff - 1) * 0.03,
            _COMEBACK_BOOST_MIN,
            _COMEBACK_BOOST_MAX,
        )
        boost = min(boost, _COMEBACK_BOOST_CAP)
        lambda_away_factor = boost
        reasons.append(f"comeback boost {away_team} (domina H2H {away_wins}/{total}, perde {abs_diff}g)")

    # --- 2. Over/under calibration por média gols H2H ---
    if avg_total_goals > 0:
        if avg_total_goals >= _HIGH_GOALS_THRESHOLD:
            # Jogo aberto historicamente → boost leve em ambos
            lambda_home_factor *= _HIGH_GOALS_BOOST
            lambda_away_factor *= _HIGH_GOALS_BOOST
            reasons.append(f"H2H aberto (média {avg_total_goals:.1f} gols/jogo)")
        elif avg_total_goals <= _LOW_GOALS_THRESHOLD:
            # Jogo fechado historicamente → penaliza ambos
            lambda_home_factor *= _LOW_GOALS_PENALTY
            lambda_away_factor *= _LOW_GOALS_PENALTY
            reasons.append(f"H2H fechado (média {avg_total_goals:.1f} gols/jogo)")

    # --- 3. Draw suppression ---
    if draw_rate < _DRAW_SUPPRESSION_RATE and total >= 3:
        draw_penalty = 1.0 - _DRAW_SUPPRESSION_FACTOR  # ex: 0.08
        reasons.append(f"H2H sem empates ({draws}/{total}) → draw suppression")

    # --- 4. Decaimento temporal: H2H perde força conforme jogo avança ---
    # Após 60 min, H2H pesa 50%; após 80 min, pesa 25%
    if minute >= 60:
        decay = _clamp(1.0 - (minute - 60) / 40.0, 0.25, 1.0)
        # Aproxima fatores para 1.0 conforme decay
        lambda_home_factor = 1.0 + (lambda_home_factor - 1.0) * decay
        lambda_away_factor = 1.0 + (lambda_away_factor - 1.0) * decay
        reasons.append(f"decay H2H {decay:.0%} (min {minute})")

    applied = lambda_home_factor != 1.0 or lambda_away_factor != 1.0 or draw_penalty > 0.0

    return H2HAdjust(
        lambda_home_factor=round(lambda_home_factor, 4),
        lambda_away_factor=round(lambda_away_factor, 4),
        draw_penalty=round(draw_penalty, 4),
        applied=applied,
        reason="; ".join(reasons) if reasons else "sem ajuste",
    )


def apply_h2h_adjust(
    lambda_full_home: float,
    lambda_full_away: float,
    h2h_adjust: H2HAdjust,
) -> tuple[float, float, H2HAdjust]:
    """Aplica fatores H2H em λ_full."""
    if not h2h_adjust.applied:
        return lambda_full_home, lambda_full_away, h2h_adjust

    new_home = lambda_full_home * h2h_adjust.lambda_home_factor
    new_away = lambda_full_away * h2h_adjust.lambda_away_factor
    return new_home, new_away, h2h_adjust
