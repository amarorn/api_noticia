"""Otimizador de bilhetes: monta combos por EV, odds e probabilidade de concretização.

Separa bilhetes por período (1º tempo, 2º tempo, tempo total) e mistos (1T+2T),
com validação anti-anulação via guardrails existentes.

Fluxo:
1. Recebe market_scan (oportunidades com EV, prob, odd)
2. Filtra por período (1h / 2h / ft)
3. Aplica guardrails anti-anulação (over 1T morto, pernas incompatíveis, etc.)
4. Gera combinações válidas de 2-4 pernas
5. Calcula EV combinado ajustado por correlação narrativa
6. Ordena por score composto (EV × prob_conjunta × odd)
7. Retorna top-K bilhetes por período com stake sugerida
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from config import settings
from models.bet_decision import compute_conservative_stake
from models.inplay_bet_builder_guard import validate_bet_builder
from models.inplay_leg_compatibility import (
    combo_legs_compatible,
    is_superbet_bet_builder_market,
    period_of_market,
)


@dataclass(frozen=True)
class Leg:
    """Perna de um bilhete."""

    market: str
    outcome: str
    label: str
    model_prob: float
    market_odd: float
    expected_value: float
    edge_pp: float
    kelly_quarter: float
    classification: str

    @property
    def period(self) -> str:
        return period_of_market(self.market)

    @property
    def implied_prob(self) -> float:
        return 1.0 / self.market_odd if self.market_odd > 1.0 else 1.0


@dataclass
class Ticket:
    """Bilhete (combo de pernas)."""

    legs: list[Leg]
    combined_odd: float = 1.0
    combined_prob: float = 1.0
    combined_ev: float = 0.0
    correlation_penalty: float = 0.0
    score: float = 0.0
    stake_brl: float = 0.0
    stake_pct: float = 0.0
    validation: dict[str, Any] = field(default_factory=dict)
    period_mix: str = "ft"  # "1h" | "2h" | "ft" | "mixed"

    @property
    def n_legs(self) -> int:
        return len(self.legs)

    @property
    def is_valid(self) -> bool:
        return self.validation.get("valid", False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "legs": [
                {
                    "market": leg.market,
                    "outcome": leg.outcome,
                    "label": leg.label,
                    "model_prob": round(leg.model_prob, 4),
                    "market_odd": round(leg.market_odd, 2),
                    "expected_value": round(leg.expected_value, 4),
                    "edge_pp": round(leg.edge_pp, 2),
                    "kelly_quarter": round(leg.kelly_quarter, 4),
                    "classification": leg.classification,
                }
                for leg in self.legs
            ],
            "combined_odd": round(self.combined_odd, 2),
            "combined_prob": round(self.combined_prob, 4),
            "combined_ev": round(self.combined_ev, 4),
            "correlation_penalty": round(self.correlation_penalty, 4),
            "score": round(self.score, 4),
            "stake_brl": round(self.stake_brl, 2),
            "stake_pct": round(self.stake_pct, 2),
            "period_mix": self.period_mix,
            "n_legs": self.n_legs,
            "valid": self.is_valid,
            "validation": self.validation,
        }


# ---------------------------------------------------------------------------
# Filtros e utilidades
# ---------------------------------------------------------------------------

def _is_bet_builder_leg(leg: Leg) -> bool:
    """Apenas mercados aceitos no Criar Aposta Superbet."""
    return is_superbet_bet_builder_market(leg.market)


def _leg_from_dict(row: dict[str, Any]) -> Leg | None:
    """Converte dict do market_scan em Leg."""
    market = str(row.get("market") or row.get("market_key") or "")
    if not market:
        return None
    odd = float(row.get("market_odd") or row.get("odd") or 0.0)
    if odd <= 1.0:
        return None
    prob = float(row.get("model_prob") or row.get("prob") or 0.0)
    if prob <= 0:
        return None
    ev = float(row.get("expected_value") or row.get("ev") or 0.0)
    edge = float(row.get("edge_pp") or row.get("edge") or 0.0)
    kq = float(row.get("kelly_quarter") or 0.0)
    cls = str(row.get("classification") or "watch")
    label = str(row.get("label") or row.get("market") or market)
    outcome = str(row.get("outcome") or row.get("selection") or "yes")
    return Leg(
        market=market,
        outcome=outcome,
        label=label,
        model_prob=prob,
        market_odd=odd,
        expected_value=ev,
        edge_pp=edge,
        kelly_quarter=kq,
        classification=cls,
    )


def _filter_by_period(legs: list[Leg], period: str) -> list[Leg]:
    """Filtra pernas por período ('1h', '2h', 'ft')."""
    return [leg for leg in legs if leg.period == period]


def _filter_alive(legs: list[Leg], *, minute: int | None = None) -> list[Leg]:
    """Remove mercados mortos pelo tempo de jogo.

    Nota: FT não é bloqueado aqui — o guardrails (bet_guardrails.py) já
    aplica live_block_minute. O otimizador precisa de liberdade para montar
    bilhetes FT até o hard_stop.
    """
    if minute is None:
        return legs
    out: list[Leg] = []
    for leg in legs:
        # 1T encerrado após 45'
        if leg.period == "1h" and minute > 45:
            continue
        # 2T bloqueado após live_block_2h_minute
        if leg.period == "2h" and minute >= settings.live_block_2h_minute:
            continue
        # FT: só bloqueia após hard_stop (o guardrails já cuida do resto)
        if leg.period == "ft" and minute >= settings.live_hard_stop_minute:
            continue
        out.append(leg)
    return out


def _narrative_correlation_penalty(legs: list[Leg]) -> float:
    """Penalidade por pernas que contam a mesma história (mesmo time/período).

    Retorna fator multiplicativo para a probabilidade conjunta.
    1.0 = independente, 0.7 = correlacionado, 0.5 = fortemente correlacionado.
    """
    from collections import defaultdict

    groups: dict[tuple[str, str], list[Leg]] = defaultdict(list)
    for leg in legs:
        # Inferir lado ofensivo
        side = _infer_offense_side(leg)
        if side:
            groups[(leg.period, side)].append(leg)

    penalty = 1.0
    for (_period, _side), items in groups.items():
        if len(items) >= 3:
            penalty *= 0.5  # Fortemente correlacionado
        elif len(items) == 2:
            penalty *= 0.75  # Moderadamente correlacionado
    return penalty


def _infer_offense_side(leg: Leg) -> str | None:
    """Inferir se a perna favorece home, away ou neutro."""
    market = leg.market.lower()
    outcome = leg.outcome.lower()
    if market == "next_goal":
        return {"home": "home", "away": "away"}.get(outcome)
    if market.startswith("combo_home"):
        return "home"
    if market.startswith("combo_away"):
        return "away"
    if market.endswith("_h2h") or market == "h2h":
        return {"1": "home", "2": "away", "x": None, "draw": None}.get(outcome)
    if "home_over_" in market and outcome in {"yes", "sim", "over"}:
        return "home"
    if "away_over_" in market and outcome in {"yes", "sim", "over"}:
        return "away"
    if market.startswith("ft_home_over_") or market.startswith("1h_home_over_") or market.startswith("2h_home_over_"):
        return "home"
    if market.startswith("ft_away_over_") or market.startswith("1h_away_over_") or market.startswith("2h_away_over_"):
        return "away"
    return None


def _compute_combined_prob(legs: list[Leg]) -> float:
    """Probabilidade conjunta ajustada por correlação narrativa."""
    raw_prob = math.prod(leg.model_prob for leg in legs)
    penalty = _narrative_correlation_penalty(legs)
    return raw_prob * penalty


def _compute_combined_ev(legs: list[Leg], combined_odd: float) -> float:
    """EV combinado = prob_conjunta × odd_combinada − 1."""
    prob = _compute_combined_prob(legs)
    return prob * combined_odd - 1.0


def _score_ticket(legs: list[Leg], combined_ev: float, combined_odd: float) -> float:
    """Score composto para ranquear bilhetes.

    Fórmula: EV × sqrt(prob_conjunta) × log(odd_combinada)
    Isso favorece:
    - EV positivo (obrigatório)
    - Probabilidade de concretização razoável
    - Odds atrativas (mas não extremas)
    """
    if combined_ev <= 0:
        return 0.0
    prob = _compute_combined_prob(legs)
    odd_factor = math.log(max(combined_odd, 1.01))
    return combined_ev * math.sqrt(prob) * odd_factor


def _validate_ticket(
    legs: list[Leg],
    *,
    minute: int | None = None,
    home_score: int = 0,
    away_score: int = 0,
    ht_home: int | None = None,
    ht_away: int | None = None,
) -> dict[str, Any]:
    """Valida bilhete via guardrails existentes."""
    leg_dicts = [
        {
            "market": leg.market,
            "outcome": leg.outcome,
            "label": leg.label,
        }
        for leg in legs
    ]
    combined_odd = math.prod(leg.market_odd for leg in legs)
    return validate_bet_builder(
        leg_dicts,
        minute=minute,
        home_score=home_score,
        away_score=away_score,
        ht_home=ht_home,
        ht_away=ht_away,
        combined_odd=combined_odd,
    )


def _stake_for_ticket(legs: list[Leg], bankroll: float = 1000.0) -> tuple[float, float]:
    """Stake sugerida para o bilhete (conservador para combos)."""
    min_kq = min(leg.kelly_quarter for leg in legs) if legs else 0.0
    # Para combos, usamos Kelly mais conservador (mínimo das pernas × 0.55)
    combo_kelly = min_kq * 0.55
    stake_brl, stake_pct = compute_conservative_stake(
        bankroll=bankroll,
        kelly_quarter=combo_kelly,
        classification="value_bet",  # Forçamos value_bet para combos com EV > 0
        use_kelly=True,
    )
    return stake_brl, stake_pct


def _period_mix(legs: list[Leg]) -> str:
    """Determina o tipo de mix de período do bilhete."""
    periods = {leg.period for leg in legs}
    if len(periods) == 1:
        return list(periods)[0]
    if periods == {"1h", "2h"}:
        return "mixed"
    if "1h" in periods and "2h" not in periods:
        return "1h"  # Predominante 1h com ft
    if "2h" in periods and "1h" not in periods:
        return "2h"  # Predominante 2h com ft
    return "mixed"


# ---------------------------------------------------------------------------
# Geração de combinações
# ---------------------------------------------------------------------------

def _generate_combinations(
    legs: list[Leg],
    max_legs: int = 4,
    min_legs: int = 2,
) -> list[list[Leg]]:
    """Gera combinações válidas de pernas (2 a max_legs)."""
    from itertools import combinations

    combos: list[list[Leg]] = []
    for r in range(min_legs, min(max_legs + 1, len(legs) + 1)):
        for combo in combinations(legs, r):
            # Valida compatibilidade par a par
            pairs = [(leg.market, leg.outcome) for leg in combo]
            if combo_legs_compatible(pairs):
                combos.append(list(combo))
    return combos


def _build_ticket(
    legs: list[Leg],
    *,
    minute: int | None = None,
    home_score: int = 0,
    away_score: int = 0,
    ht_home: int | None = None,
    ht_away: int | None = None,
    bankroll: float = 1000.0,
) -> Ticket:
    """Constrói um Ticket a partir de uma lista de Legs compatíveis."""
    combined_odd = math.prod(leg.market_odd for leg in legs)
    combined_prob = _compute_combined_prob(legs)
    combined_ev = _compute_combined_ev(legs, combined_odd)
    penalty = _narrative_correlation_penalty(legs)
    score = _score_ticket(legs, combined_ev, combined_odd)
    validation = _validate_ticket(
        legs,
        minute=minute,
        home_score=home_score,
        away_score=away_score,
        ht_home=ht_home,
        ht_away=ht_away,
    )
    stake_brl, stake_pct = _stake_for_ticket(legs, bankroll)
    period_mix = _period_mix(legs)

    return Ticket(
        legs=legs,
        combined_odd=combined_odd,
        combined_prob=combined_prob,
        combined_ev=combined_ev,
        correlation_penalty=1.0 - penalty,
        score=score,
        stake_brl=stake_brl,
        stake_pct=stake_pct,
        validation=validation,
        period_mix=period_mix,
    )


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def build_optimized_tickets(
    market_scan: list[dict[str, Any]],
    *,
    minute: int | None = None,
    home_score: int = 0,
    away_score: int = 0,
    ht_home: int | None = None,
    ht_away: int | None = None,
    bankroll: float = 1000.0,
    max_legs: int = 4,
    min_legs: int = 2,
    top_k: int = 5,
    min_ev: float = 0.0,
    min_combined_odd: float = 1.5,
    max_combined_odd: float = 20.0,
) -> dict[str, list[Ticket]]:
    """Monta bilhetes otimizados separados por período.

    Args:
        market_scan: Lista de oportunidades (dicts com market, outcome, prob, odd, ev, etc.)
        minute: Minuto atual do jogo (para guardrails temporais)
        home_score, away_score: Placar atual
        ht_home, ht_away: Placar do intervalo (se conhecido)
        bankroll: Banca disponível
        max_legs: Máximo de pernas por bilhete
        min_legs: Mínimo de pernas por bilhete
        top_k: Quantos bilhetes retornar por categoria
        min_ev: EV mínimo combinado
        min_combined_odd: Odd mínima combinada
        max_combined_odd: Odd máxima combinada

    Returns:
        Dict com chaves '1h', '2h', 'ft', 'mixed', cada uma com lista de Tickets ordenados.
    """
    # 1. Converter e filtrar pernas
    all_legs = [_leg_from_dict(row) for row in market_scan]
    all_legs = [leg for leg in all_legs if leg is not None]
    all_legs = [leg for leg in all_legs if _is_bet_builder_leg(leg)]
    all_legs = _filter_alive(all_legs, minute=minute)

    # 2. Separar por período
    legs_1h = _filter_by_period(all_legs, "1h")
    legs_2h = _filter_by_period(all_legs, "2h")
    legs_ft = _filter_by_period(all_legs, "ft")

    # 3. Ordenar por EV decrescente (para greedy melhor)
    legs_1h.sort(key=lambda leg: leg.expected_value, reverse=True)
    legs_2h.sort(key=lambda leg: leg.expected_value, reverse=True)
    legs_ft.sort(key=lambda leg: leg.expected_value, reverse=True)

    # 4. Limitar pool para performance (top-N por período)
    pool_size = settings.combo_optimizer_pool_size if hasattr(settings, "combo_optimizer_pool_size") else 12
    legs_1h = legs_1h[:pool_size]
    legs_2h = legs_2h[:pool_size]
    legs_ft = legs_ft[:pool_size]

    # 5. Gerar combinações por categoria
    tickets_1h: list[Ticket] = []
    tickets_2h: list[Ticket] = []
    tickets_ft: list[Ticket] = []
    tickets_mixed: list[Ticket] = []

    # Bilhetes 1T (apenas 1h)
    for combo in _generate_combinations(legs_1h, max_legs=max_legs, min_legs=min_legs):
        ticket = _build_ticket(
            combo,
            minute=minute,
            home_score=home_score,
            away_score=away_score,
            ht_home=ht_home,
            ht_away=ht_away,
            bankroll=bankroll,
        )
        if ticket.is_valid and ticket.combined_ev >= min_ev:
            if min_combined_odd <= ticket.combined_odd <= max_combined_odd:
                tickets_1h.append(ticket)

    # Bilhetes 2T (apenas 2h)
    for combo in _generate_combinations(legs_2h, max_legs=max_legs, min_legs=min_legs):
        ticket = _build_ticket(
            combo,
            minute=minute,
            home_score=home_score,
            away_score=away_score,
            ht_home=ht_home,
            ht_away=ht_away,
            bankroll=bankroll,
        )
        if ticket.is_valid and ticket.combined_ev >= min_ev:
            if min_combined_odd <= ticket.combined_odd <= max_combined_odd:
                tickets_2h.append(ticket)

    # Bilhetes FT (apenas ft)
    for combo in _generate_combinations(legs_ft, max_legs=max_legs, min_legs=min_legs):
        ticket = _build_ticket(
            combo,
            minute=minute,
            home_score=home_score,
            away_score=away_score,
            ht_home=ht_home,
            ht_away=ht_away,
            bankroll=bankroll,
        )
        if ticket.is_valid and ticket.combined_ev >= min_ev:
            if min_combined_odd <= ticket.combined_odd <= max_combined_odd:
                tickets_ft.append(ticket)

    # Bilhetes mistos (1h + 2h) — só até minuto 45
    if minute is None or minute <= 45:
        mixed_legs = legs_1h[:6] + legs_2h[:6]
        mixed_legs.sort(key=lambda leg: leg.expected_value, reverse=True)
        for combo in _generate_combinations(mixed_legs, max_legs=max_legs, min_legs=min_legs):
            # Garantir que tem pelo menos uma perna de cada período
            periods = {leg.period for leg in combo}
            if not ("1h" in periods and "2h" in periods):
                continue
            ticket = _build_ticket(
                combo,
                minute=minute,
                home_score=home_score,
                away_score=away_score,
                ht_home=ht_home,
                ht_away=ht_away,
                bankroll=bankroll,
            )
            if ticket.is_valid and ticket.combined_ev >= min_ev:
                if min_combined_odd <= ticket.combined_odd <= max_combined_odd:
                    tickets_mixed.append(ticket)

    # 6. Ordenar por score e deduplicar
    def _dedup_and_sort(tickets: list[Ticket]) -> list[Ticket]:
        seen: set[str] = set()
        out: list[Ticket] = []
        for t in sorted(tickets, key=lambda x: x.score, reverse=True):
            key = "|".join(sorted(f"{leg.market}:{leg.outcome}" for leg in t.legs))
            if key in seen:
                continue
            seen.add(key)
            out.append(t)
        return out

    tickets_1h = _dedup_and_sort(tickets_1h)[:top_k]
    tickets_2h = _dedup_and_sort(tickets_2h)[:top_k]
    tickets_ft = _dedup_and_sort(tickets_ft)[:top_k]
    tickets_mixed = _dedup_and_sort(tickets_mixed)[:top_k]

    return {
        "1h": tickets_1h,
        "2h": tickets_2h,
        "ft": tickets_ft,
        "mixed": tickets_mixed,
    }


def tickets_to_dict(tickets_by_period: dict[str, list[Ticket]]) -> dict[str, list[dict[str, Any]]]:
    """Converte resultado em dict serializável."""
    return {
        period: [ticket.to_dict() for ticket in tickets]
        for period, tickets in tickets_by_period.items()
    }


__all__ = [
    "Leg",
    "Ticket",
    "build_optimized_tickets",
    "tickets_to_dict",
]
