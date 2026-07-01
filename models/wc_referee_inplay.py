"""Ajustes in-play baseados no perfil do árbitro (cartões, faltas, pênaltis).

Integra dados de análise pré-jogo (ex: relatórios txt, Sofascore, FIFA) ao modelo
in-play para ajustar probabilidades de mercados relacionados a disciplina.

Fontes de dados esperadas no match_context:
- referee_name: str
- referee_nationality: str
- referee_card_lambda: float (média de cartões/jogo do árbitro)
- referee_foul_lambda: float (média de faltas/jogo)
- referee_penalty_rate: float (taxa de pênaltis/jogo, 0-1)
- referee_red_card_rate: float (taxa de vermelhos/jogo, 0-1)
- referee_profile: str ("punitivista", "pacificador", "equilibrado")
- referee_stats_source: str ("relatorio", "sofascore", "fifa", etc.)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class RefereeProfile:
    """Perfil estatístico de um árbitro para ajustes in-play."""

    name: str
    nationality: str | None = None
    card_lambda: float | None = None  # média cartões amarelos/jogo
    foul_lambda: float | None = None  # média faltas/jogo
    penalty_rate: float | None = None  # probabilidade de pênalti/jogo
    red_card_rate: float | None = None  # probabilidade de vermelho/jogo
    profile: str = "equilibrado"  # punitivista | pacificador | equilibrado
    source: str | None = None
    games_officiated: int | None = None

    # Thresholds para classificação automática
    _PUNITIVISTA_CARD_THRESHOLD = 5.0
    _PUNITIVISTA_FOUL_THRESHOLD = 23.0
    _PUNITIVISTA_CARD_FOUL_RATIO = 0.22  # cartões/faltas
    _PACIFICADOR_CARD_THRESHOLD = 3.5

    def __post_init__(self):
        if self.profile == "equilibrado" and self.card_lambda is not None:
            self._auto_classify()

    def _auto_classify(self) -> None:
        """Classifica perfil baseado em estatísticas se não explícito."""
        cards = self.card_lambda
        fouls = self.foul_lambda or 20.0

        if cards >= self._PUNITIVISTA_CARD_THRESHOLD:
            self.profile = "punitivista"
        elif fouls >= self._PUNITIVISTA_FOUL_THRESHOLD and cards / fouls >= self._PUNITIVISTA_CARD_FOUL_RATIO:
            self.profile = "punitivista"
        elif cards <= self._PACIFICADOR_CARD_THRESHOLD:
            self.profile = "pacificador"

    @property
    def is_punitivista(self) -> bool:
        return self.profile == "punitivista"

    @property
    def is_pacificador(self) -> bool:
        return self.profile == "pacificador"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "nationality": self.nationality,
            "card_lambda": self.card_lambda,
            "foul_lambda": self.foul_lambda,
            "penalty_rate": self.penalty_rate,
            "red_card_rate": self.red_card_rate,
            "profile": self.profile,
            "source": self.source,
            "games_officiated": self.games_officiated,
        }


def parse_referee_from_match_context(match_context: dict[str, Any] | None) -> RefereeProfile | None:
    """Extrai perfil do árbitro do match_context.

    Suporta múltiplos formatos de entrada:
    - referee_card_lambda (float)
    - referee_name (str)
    - referee_profile (str)
    - referee_stats (dict com campos detalhados)
    """
    if not match_context:
        return None

    # Formato flat (usado atualmente no advice.py)
    if "referee_card_lambda" in match_context or "referee_name" in match_context:
        return RefereeProfile(
            name=match_context.get("referee_name", "Desconhecido"),
            nationality=match_context.get("referee_nationality"),
            card_lambda=match_context.get("referee_card_lambda"),
            foul_lambda=match_context.get("referee_foul_lambda"),
            penalty_rate=match_context.get("referee_penalty_rate"),
            red_card_rate=match_context.get("referee_red_card_rate"),
            profile=match_context.get("referee_profile", "equilibrado"),
            source=match_context.get("referee_stats_source", "match_context"),
            games_officiated=match_context.get("referee_games_officiated"),
        )

    # Formato aninhado
    ref_data = match_context.get("referee") or match_context.get("arbitro")
    if ref_data and isinstance(ref_data, dict):
        return RefereeProfile(
            name=ref_data.get("name", ref_data.get("nome", "Desconhecido")),
            nationality=ref_data.get("nationality", ref_data.get("nacionalidade")),
            card_lambda=_extract_float(ref_data, ["card_lambda", "cartoes_media", "cards_per_game", "media_cartoes"]),
            foul_lambda=_extract_float(ref_data, ["foul_lambda", "faltas_media", "fouls_per_game", "media_faltas"]),
            penalty_rate=_extract_float(ref_data, ["penalty_rate", "penaltis_media", "penalties_per_game"]),
            red_card_rate=_extract_float(ref_data, ["red_card_rate", "vermelhos_media", "red_cards_per_game"]),
            profile=ref_data.get("profile", ref_data.get("perfil", "equilibrado")),
            source=ref_data.get("source", "relatorio"),
            games_officiated=ref_data.get("games_officiated", ref_data.get("jogos_apitados")),
        )

    return None


def _extract_float(data: dict, keys: list[str]) -> float | None:
    """Tenta extrair um float de múltiplas chaves possíveis."""
    for key in keys:
        val = data.get(key)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
    return None


# ---------------------------------------------------------------------------
# Ajustes de λ para mercados de cartões
# ---------------------------------------------------------------------------

# Baselines de cartões por jogo (médias globais da Copa do Mundo)
_BASELINE_YELLOW_CARDS_PER_GAME = 3.8
_BASELINE_FOULS_PER_GAME = 22.0
_BASELINE_PENALTY_RATE = 0.28
_BASELINE_RED_CARD_RATE = 0.08

# Fatores de ajuste por perfil de árbitro
_REFEREE_CARD_MULTIPLIERS = {
    "punitivista": 1.35,   # +35% cartões
    "equilibrado": 1.0,    # baseline
    "pacificador": 0.78,   # -22% cartões
}

_REFEREE_FOUL_MULTIPLIERS = {
    "punitivista": 1.15,   # +15% faltas marcadas
    "equilibrado": 1.0,
    "pacificador": 0.90,   # -10% faltas
}

_REFEREE_PENALTY_MULTIPLIERS = {
    "punitivista": 1.25,   # +25% pênaltis
    "equilibrado": 1.0,
    "pacificador": 0.85,   # -15% pênaltis
}

_REFEREE_RED_CARD_MULTIPLIERS = {
    "punitivista": 1.40,   # +40% vermelhos
    "equilibrado": 1.0,
    "pacificador": 0.70,   # -30% vermelhos
}


def referee_card_lambda_adjusted(referee: RefereeProfile | None) -> float:
    """λ ajustado de cartões amarelos com base no perfil do árbitro.

    Se não houver dados do árbitro, retorna baseline global.
    """
    if referee is None or referee.card_lambda is None:
        return _BASELINE_YELLOW_CARDS_PER_GAME

    mult = _REFEREE_CARD_MULTIPLIERS.get(referee.profile, 1.0)
    return referee.card_lambda * mult


def referee_foul_lambda_adjusted(referee: RefereeProfile | None) -> float:
    """λ ajustado de faltas com base no perfil do árbitro."""
    if referee is None or referee.foul_lambda is None:
        return _BASELINE_FOULS_PER_GAME

    mult = _REFEREE_FOUL_MULTIPLIERS.get(referee.profile, 1.0)
    return referee.foul_lambda * mult


def referee_penalty_prob_adjusted(referee: RefereeProfile | None) -> float:
    """Probabilidade ajustada de pênalti com base no perfil do árbitro."""
    if referee is None or referee.penalty_rate is None:
        return _BASELINE_PENALTY_RATE

    mult = _REFEREE_PENALTY_MULTIPLIERS.get(referee.profile, 1.0)
    return min(referee.penalty_rate * mult, 0.85)  # cap em 85%


def referee_red_card_prob_adjusted(referee: RefereeProfile | None) -> float:
    """Probabilidade ajustada de cartão vermelho com base no perfil do árbitro."""
    if referee is None or referee.red_card_rate is None:
        return _BASELINE_RED_CARD_RATE

    mult = _REFEREE_RED_CARD_MULTIPLIERS.get(referee.profile, 1.0)
    return min(referee.red_card_rate * mult, 0.35)  # cap em 35%


# ---------------------------------------------------------------------------
# Ajustes dinâmicos ao vivo (in-play)
# ---------------------------------------------------------------------------

def adjust_card_prob_for_minute(
    base_prob: float,
    minute: int,
    match_minutes: int = 90,
    referee: RefereeProfile | None = None,
) -> float:
    """Ajusta probabilidade de cartão considerando tempo decorrido e árbitro.

    Lógica: se o árbitro é punitivista e já passou muito tempo sem cartões,
    a probabilidade de cartões no tempo restante aumenta ("acumulação de tensão").
    """
    if minute <= 0 or match_minutes <= 0:
        return base_prob

    remaining = match_minutes - minute
    fraction_remaining = remaining / match_minutes

    # Probabilidade base proporcional ao tempo restante
    prob = base_prob * fraction_remaining

    # Ajuste do árbitro: punitivistas "aceleram" cartões no 2º tempo
    if referee and referee.is_punitivista and minute > 45:
        # Já deveria ter visto cartões; se não viu, aumenta a pressão
        expected_by_now = referee.card_lambda * (minute / match_minutes) if referee.card_lambda else 1.9
        # Fator de aceleração: quanto mais abaixo da expectativa, mais provável
        acceleration = 1.0 + max(0, (expected_by_now - 1.0) * 0.15)
        prob *= min(acceleration, 1.5)  # max +50%

    # Pacificadores diminuem probabilidade no final
    if referee and referee.is_pacificador and minute > 75:
        prob *= 0.85  # -15% no final

    return min(prob, 0.95)


def referee_card_market_probs(
    referee: RefereeProfile | None = None,
    minute: int = 0,
    match_minutes: int = 90,
    current_yellow_cards: int = 0,
) -> dict[str, float]:
    """Calcula probabilidades para mercados de cartões ao vivo.

    Retorna dict com keys:
    - over_3_5_yellow: prob de over 3.5 cartões amarelos no jogo
    - over_4_5_yellow: prob de over 4.5
    - over_5_5_yellow: prob de over 5.5
    - over_6_5_yellow: prob de over 6.5
    - red_card_yes: prob de cartão vermelho no jogo
    - penalty_yes: prob de pênalti no jogo
    """
    card_lambda = referee_card_lambda_adjusted(referee)
    foul_lambda = referee_foul_lambda_adjusted(referee)
    penalty_prob = referee_penalty_prob_adjusted(referee)
    red_prob = referee_red_card_prob_adjusted(referee)

    # Ajuste pelo tempo decorrido
    card_lambda_remaining = adjust_card_prob_for_minute(
        card_lambda, minute, match_minutes, referee
    )

    # Modelo Poisson para cartões restantes
    # Se já vimos cartões, subtraímos do esperado total, mas não deixamos ir abaixo de 0
    expected_total = card_lambda_remaining
    expected_remaining = max(0.5, expected_total - current_yellow_cards)  # mínimo 0.5 para não zerar

    # Probabilidades acumuladas (Poisson CDF)
    from scipy import stats as scipy_stats

    probs = {}
    for line in [3.5, 4.5, 5.5, 6.5]:
        # Prob de total > line = 1 - CDF(line - current)
        # Se já passamos da linha, prob = 1.0
        if current_yellow_cards > line:
            prob_over = 1.0
        else:
            remaining_needed = line - current_yellow_cards
            if expected_remaining > 0:
                prob_over = 1.0 - scipy_stats.poisson.cdf(int(remaining_needed), expected_remaining)
            else:
                prob_over = 0.0
        key = f"over_{line:.1f}_yellow".replace(".", "_")
        probs[key] = float(np.clip(prob_over, 0.0, 1.0))

    # Red card e penalty: probabilidade independente (Bernoulli)
    # Ajuste pelo tempo restante
    remaining_fraction = max(0, match_minutes - minute) / match_minutes if match_minutes > 0 else 1.0
    probs["red_card_yes"] = float(np.clip(red_prob * remaining_fraction, 0.0, 1.0))
    probs["penalty_yes"] = float(np.clip(penalty_prob * remaining_fraction, 0.0, 1.0))

    # Faltas: usamos lambda total do jogo (não depende do tempo decorrido)
    # pois faltas são acumulativas e não sabemos quantas já ocorreram
    for line in [20.5, 25.5, 30.5]:
        prob_over = 1.0 - scipy_stats.poisson.cdf(int(line), foul_lambda)
        key = f"over_{line:.1f}_fouls".replace(".", "_")
        probs[key] = float(np.clip(prob_over, 0.0, 1.0))

    # Metadados
    probs["_referee"] = referee.name if referee else "baseline"
    probs["_referee_profile"] = referee.profile if referee else "baseline"
    probs["_card_lambda"] = round(card_lambda, 2)
    probs["_expected_remaining"] = round(expected_remaining, 2)

    return probs


# ---------------------------------------------------------------------------
# Integração com o modelo in-play principal
# ---------------------------------------------------------------------------

def apply_referee_to_inplay_result(
    inplay_result: Any,
    referee: RefereeProfile | None = None,
    snapshot: Any | None = None,
) -> dict[str, Any]:
    """Adiciona probabilidades de cartões ao resultado in-play existente.

    Usado no advice.py para enriquecer o payload com mercados de disciplina.
    """
    if inplay_result is None:
        return {}

    minute = getattr(inplay_result, "minute", 0)
    match_minutes = getattr(inplay_result, "match_minutes", 90)

    # Cartões atuais do snapshot
    current_yellow = 0
    if snapshot and hasattr(snapshot, "inplay") and snapshot.inplay:
        current_yellow = (snapshot.inplay.home_yellow_cards or 0) + (snapshot.inplay.away_yellow_cards or 0)

    card_probs = referee_card_market_probs(
        referee=referee,
        minute=minute,
        match_minutes=match_minutes,
        current_yellow_cards=current_yellow,
    )

    return {
        "referee_markets": card_probs,
        "referee_profile": referee.to_dict() if referee else None,
    }
