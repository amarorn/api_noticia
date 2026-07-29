"""Fase do jogo beisebol (substituto do relógio do futebol)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import settings


@dataclass(frozen=True)
class BaseballGamePhase:
    phase: str  # early | f5_open | mid | late | extras | finished
    label: str
    extras_possible: bool
    block_f5: bool
    block_ft_totals: bool
    block_new_ft_aportes: bool
    run_gap: int
    lead_side: str | None  # home | away | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "label": self.label,
            "extras_possible": self.extras_possible,
            "block_f5": self.block_f5,
            "block_ft_totals": self.block_ft_totals,
            "block_new_ft_aportes": self.block_new_ft_aportes,
            "run_gap": self.run_gap,
            "lead_side": self.lead_side,
        }


def resolve_baseball_game_phase(
    *,
    inning: int,
    home_score: int,
    away_score: int,
    is_finished: bool,
    match_innings: int | None = None,
) -> BaseballGamePhase:
    """Deriva fase operacional sem depender de horário fixo."""
    match_innings = match_innings or settings.baseball_match_innings
    inning = max(1, inning)
    gap = abs(home_score - away_score)
    lead_side: str | None = None
    if home_score > away_score:
        lead_side = "home"
    elif away_score > home_score:
        lead_side = "away"

    if is_finished:
        return BaseballGamePhase(
            phase="finished",
            label="Jogo encerrado",
            extras_possible=False,
            block_f5=True,
            block_ft_totals=True,
            block_new_ft_aportes=True,
            run_gap=gap,
            lead_side=lead_side,
        )

    in_extras = inning > match_innings
    tied_late = home_score == away_score and inning >= match_innings
    blowout = gap >= 5 and inning >= settings.baseball_late_inning

    if in_extras or tied_late:
        return BaseballGamePhase(
            phase="extras",
            label="Entradas extras possíveis",
            extras_possible=True,
            block_f5=True,
            block_ft_totals=True,
            block_new_ft_aportes=False,
            run_gap=gap,
            lead_side=lead_side,
        )

    if inning >= match_innings:
        return BaseballGamePhase(
            phase="late",
            label=f"Entrada {inning} — reta final",
            extras_possible=tied_late,
            block_f5=True,
            block_ft_totals=blowout,
            block_new_ft_aportes=blowout,
            run_gap=gap,
            lead_side=lead_side,
        )

    if inning >= settings.baseball_late_inning:
        return BaseballGamePhase(
            phase="late",
            label=f"Entrada {inning} — reta final",
            extras_possible=True,
            block_f5=True,
            block_ft_totals=False,
            block_new_ft_aportes=blowout,
            run_gap=gap,
            lead_side=lead_side,
        )

    if inning > 5:
        return BaseballGamePhase(
            phase="mid",
            label=f"Entrada {inning} — meio de jogo",
            extras_possible=True,
            block_f5=True,
            block_ft_totals=False,
            block_new_ft_aportes=False,
            run_gap=gap,
            lead_side=lead_side,
        )

    return BaseballGamePhase(
        phase="f5_open",
        label=f"Entrada {inning} — F5 aberto",
        extras_possible=True,
        block_f5=False,
        block_ft_totals=False,
        block_new_ft_aportes=False,
        run_gap=gap,
        lead_side=lead_side,
    )
