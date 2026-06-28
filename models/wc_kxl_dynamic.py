"""KXL dinâmico ao vivo — colisões setoriais reativas a eventos.

Versão simplificada do KXL pré-jogo (pipelines/wc_kxl_collision.py) que reage
a eventos ao vivo (gol, cartão, substituição) ajustando vetores de ataque/defesa.

Diferenças do KXL pré-jogo:
- Não recalcula escalações completas (usamos FEPT cacheado)
- Reage a eventos em tempo real com ajustes incrementais
- Output: fatores de ajuste para λ (não probabilidades diretas)

Uso:
    kxl_dynamic = KXLDynamic.from_match_context(match_context)
    kxl_dynamic.apply_event("goal", team="home", minute=23)
    kxl_dynamic.apply_event("red_card", team="away", minute=38)
    factors = kxl_dynamic.compute_factors(minute=45)
    # factors = {"home_attack": 1.12, "away_defense": 0.85, ...}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class KXLState:
    """Estado dinâmico do KXL para um time."""

    attack_factor: float = 1.0  # multiplicador de λ ataque
    defense_factor: float = 1.0  # multiplicador de λ defesa (adversário)
    energy: float = 1.0  # energia relativa (0.5-1.5)
    morale: float = 1.0  # moral (0.5-1.5)
    structure: float = 1.0  # estrutura tática (0.7-1.3)


@dataclass
class KXLDynamic:
    """KXL dinâmico que reage a eventos ao vivo."""

    home_state: KXLState = field(default_factory=KXLState)
    away_state: KXLState = field(default_factory=KXLState)
    events: list[dict[str, Any]] = field(default_factory=list)

    # Constantes de ajuste (calibráveis)
    GOAL_ATTACK_BOOST: float = 0.08  # gol aumenta ataque em 8%
    GOAL_DEFENSE_PENALTY: float = 0.05  # gol sofrido reduz defesa em 5%
    RED_CARD_ATTACK_PENALTY: float = 0.20  # cartão vermelho reduz ataque em 20%
    RED_CARD_DEFENSE_BOOST: float = 0.15  # cartão vermelho adversário aumenta defesa em 15%
    SUB_OFFENSIVE_BOOST: float = 0.06  # sub ofensiva aumenta ataque em 6%
    SUB_DEFENSIVE_BOOST: float = 0.05  # sub defensiva aumenta defesa em 5%
    LATE_GAME_ENERGY_DECAY: float = 0.02  # perda de energia por minuto após 70'
    MORALE_GOAL_BOOST: float = 0.10  # gol aumenta moral em 10%
    MORALE_GOAL_PENALTY: float = 0.08  # gol sofrido reduz moral em 8%

    @classmethod
    def from_match_context(cls, match_context: dict[str, Any] | None) -> "KXLDynamic":
        """Inicializa KXL dinâmico a partir do contexto pré-jogo."""
        kxl = cls()
        if not match_context:
            return kxl

        # Carrega fatores KXL pré-jogo se disponíveis
        kxl_pre = match_context.get("kxl_factors")
        if kxl_pre:
            kxl.home_state.attack_factor = kxl_pre.get("home_attack", 1.0)
            kxl.home_state.defense_factor = kxl_pre.get("home_defense", 1.0)
            kxl.away_state.attack_factor = kxl_pre.get("away_attack", 1.0)
            kxl.away_state.defense_factor = kxl_pre.get("away_defense", 1.0)

        # Energia inicial baseada em escalações
        home_energy = match_context.get("home_energy", 1.0)
        away_energy = match_context.get("away_energy", 1.0)
        if home_energy:
            kxl.home_state.energy = float(home_energy)
        if away_energy:
            kxl.away_state.energy = float(away_energy)

        return kxl

    def apply_event(
        self,
        event_type: str,
        *,
        team: str,
        minute: int,
        detail: str = "",
    ) -> None:
        """Aplica um evento ao vivo, ajustando estados.

        Args:
            event_type: "goal", "red_card", "yellow_card", "substitution",
                       "injury", "corner", "penalty"
            team: "home" ou "away"
            minute: minuto do evento
            detail: detalhes adicionais (ex: "offensive", "defensive")
        """
        self.events.append({
            "type": event_type,
            "team": team,
            "minute": minute,
            "detail": detail,
        })

        state = self.home_state if team == "home" else self.away_state
        opp_state = self.away_state if team == "home" else self.home_state

        if event_type == "goal":
            # Time que marcou: ataque + moral
            state.attack_factor *= (1 + self.GOAL_ATTACK_BOOST)
            state.morale *= (1 + self.MORALE_GOAL_BOOST)
            # Time que sofreu: defesa - moral
            opp_state.defense_factor *= (1 - self.GOAL_DEFENSE_PENALTY)
            opp_state.morale *= (1 - self.MORALE_GOAL_PENALTY)

        elif event_type == "red_card":
            # Time que tomou: ataque -, defesa -
            state.attack_factor *= (1 - self.RED_CARD_ATTACK_PENALTY)
            state.defense_factor *= (1 - self.RED_CARD_DEFENSE_BOOST)
            # Adversário: ataque + (aproveita vantagem)
            opp_state.attack_factor *= (1 + self.RED_CARD_DEFENSE_BOOST * 0.5)

        elif event_type == "substitution":
            if "offensive" in detail.lower():
                state.attack_factor *= (1 + self.SUB_OFFENSIVE_BOOST)
            elif "defensive" in detail.lower():
                state.defense_factor *= (1 + self.SUB_DEFENSIVE_BOOST)

        elif event_type == "injury":
            # Lesão de jogador chave: penalidade similar a cartão amarelo
            state.attack_factor *= 0.95
            state.defense_factor *= 0.95

        elif event_type == "penalty":
            # Pênalti marcado: boost de ataque
            state.attack_factor *= 1.05
            state.morale *= 1.08

        # Clamp para evitar valores absurdos
        self._clamp_states()

    def apply_time_decay(self, minute: int) -> None:
        """Aplica decaimento de energia ao longo do tempo."""
        if minute > 70:
            decay = 1.0 - (minute - 70) * self.LATE_GAME_ENERGY_DECAY / 100
            self.home_state.energy *= max(0.7, decay)
            self.away_state.energy *= max(0.7, decay)
            self._clamp_states()

    def compute_factors(self, minute: int) -> dict[str, float]:
        """Calcula fatores finais de ajuste para λ.

        Returns:
            Dict com home_attack, home_defense, away_attack, away_defense
            Estes fatores multiplicam λ_home e λ_away no modelo in-play.

            home_attack = home_state.attack_factor × home_state.energy × home_state.morale
            home_defense = home_state.defense_factor × home_state.energy
            (defesa não depende de moral — estrutura tática sim)
        """
        self.apply_time_decay(minute)

        home_attack = (
            self.home_state.attack_factor
            * self.home_state.energy
            * self.home_state.morale
            * self.home_state.structure
        )
        home_defense = (
            self.home_state.defense_factor
            * self.home_state.energy
            * self.home_state.structure
        )
        away_attack = (
            self.away_state.attack_factor
            * self.away_state.energy
            * self.away_state.morale
            * self.away_state.structure
        )
        away_defense = (
            self.away_state.defense_factor
            * self.away_state.energy
            * self.away_state.structure
        )

        return {
            "home_attack": round(float(np.clip(home_attack, 0.5, 2.0)), 4),
            "home_defense": round(float(np.clip(home_defense, 0.5, 2.0)), 4),
            "away_attack": round(float(np.clip(away_attack, 0.5, 2.0)), 4),
            "away_defense": round(float(np.clip(away_defense, 0.5, 2.0)), 4),
            "home_energy": round(self.home_state.energy, 4),
            "away_energy": round(self.away_state.energy, 4),
            "home_morale": round(self.home_state.morale, 4),
            "away_morale": round(self.away_state.morale, 4),
            "n_events": len(self.events),
        }

    def _clamp_states(self) -> None:
        """Garante que todos os fatores permanecem em ranges razoáveis."""
        for state in (self.home_state, self.away_state):
            state.attack_factor = float(np.clip(state.attack_factor, 0.5, 2.0))
            state.defense_factor = float(np.clip(state.defense_factor, 0.5, 2.0))
            state.energy = float(np.clip(state.energy, 0.5, 1.5))
            state.morale = float(np.clip(state.morale, 0.5, 1.5))
            state.structure = float(np.clip(state.structure, 0.7, 1.3))


def apply_kxl_dynamic_to_lambda(
    lambda_home: float,
    lambda_away: float,
    kxl_factors: dict[str, float],
) -> tuple[float, float, dict[str, Any]]:
    """Aplica fatores KXL dinâmico aos lambdas do modelo.

    Lógica:
    - λ_home ajustado = λ_home × home_attack / away_defense
      (ataque home × defesa away fraca = mais gols home)
    - λ_away ajustado = λ_away × away_attack / home_defense
      (ataque away × defesa home fraca = mais gols away)

    Returns:
        (lambda_home_ajustado, lambda_away_ajustado, meta)
    """
    home_attack = kxl_factors.get("home_attack", 1.0)
    home_defense = kxl_factors.get("home_defense", 1.0)
    away_attack = kxl_factors.get("away_attack", 1.0)
    away_defense = kxl_factors.get("away_defense", 1.0)

    # λ_home = gols que home marca = ataque home / defesa away
    new_home = lambda_home * (home_attack / away_defense)
    # λ_away = gols que away marca = ataque away / defesa home
    new_away = lambda_away * (away_attack / home_defense)

    # Clamp de segurança
    new_home = float(np.clip(new_home, lambda_home * 0.5, lambda_home * 2.0))
    new_away = float(np.clip(new_away, lambda_away * 0.5, lambda_away * 2.0))

    meta = {
        "applied": True,
        "source": "kxl_dynamic",
        "home_attack": home_attack,
        "away_defense": away_defense,
        "away_attack": away_attack,
        "home_defense": home_defense,
        "shift_home_pct": round((new_home / lambda_home - 1.0) * 100, 2),
        "shift_away_pct": round((new_away / lambda_away - 1.0) * 100, 2),
    }

    return new_home, new_away, meta
