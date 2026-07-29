"""Guardrails operacionais beisebol (bloqueios de nova aposta)."""
from __future__ import annotations

from typing import Any

from models.baseball_game_phase import BaseballGamePhase


def build_baseball_bet_guardrails(
    *,
    game_phase: BaseballGamePhase,
    dead_markets: list[str],
) -> dict[str, Any]:
    block = game_phase.phase == "finished"
    block_reason: str | None = None
    if block:
        block_reason = "Jogo encerrado"
    elif game_phase.block_new_ft_aportes and game_phase.run_gap >= 6:
        block = True
        block_reason = f"Jogo decidido ({game_phase.run_gap} runs de diferença)"

    return {
        "block_new_bets": block,
        "block_reason": block_reason,
        "dead_markets": dead_markets,
        "allow_f5": not game_phase.block_f5,
        "allow_ft_totals": not game_phase.block_ft_totals,
        "extras_warning": game_phase.phase == "extras",
    }
