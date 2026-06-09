"""Perfil de intensidade NHPP (Non-Homogeneous Poisson Process) para futebol.

Define pesos por bucket temporal que modulam a intensidade de gols ao longo
dos 90 minutos. Baseado em dados empíricos (Dixon & Robinson 1998; Baio &
Blangiardo 2010; Anderson & Sally 2013):

- Início do jogo (0-15'): intensidade abaixo da média (~0.85)
- Período central 1H (15-45'): próximo da média (~1.0)
- Início 2H (45-60'): leve acima (~1.05), substituições e ajustes
- 60-75': período com mais gols (~1.12), times abertos
- Reta final (75-90'): pico de intensidade (~1.20), urgência + acréscimos

A soma ponderada dos pesos × duração de cada bucket deve normalizar para
a duração total do jogo (constraint).

Spec: docs/specs/spec-fase-1-quickwins-inplay.md § 1b
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntensityBucket:
    """Um bucket temporal com peso de intensidade relativa."""

    start_min: int
    end_min: int
    weight: float

    @property
    def duration(self) -> int:
        return self.end_min - self.start_min


# Perfil padrão baseado em literatura (buckets de 15 min)
# Pesos relativos: média ponderada = 1.0 (normalizado)
_DEFAULT_PROFILE: list[IntensityBucket] = [
    IntensityBucket(start_min=0, end_min=15, weight=0.84),
    IntensityBucket(start_min=15, end_min=30, weight=0.96),
    IntensityBucket(start_min=30, end_min=45, weight=1.02),
    IntensityBucket(start_min=45, end_min=60, weight=1.05),
    IntensityBucket(start_min=60, end_min=75, weight=1.12),
    IntensityBucket(start_min=75, end_min=90, weight=1.20),
]


def default_intensity_profile() -> list[IntensityBucket]:
    """Retorna o perfil de intensidade padrão (6 buckets de 15 min)."""
    return list(_DEFAULT_PROFILE)


def compute_remaining_lambda(
    lambda_full: float,
    minute: int,
    match_minutes: int = 90,
    profile: list[IntensityBucket] | None = None,
) -> float:
    """Calcula λ_remaining usando perfil NHPP.

    Em vez de assumir intensidade constante (λ_full × fração_restante),
    integra os pesos do perfil sobre o tempo restante.

    Args:
        lambda_full: λ esperado para jogo completo (90 min).
        minute: minuto atual (0-90).
        match_minutes: duração total do jogo em minutos.
        profile: perfil de intensidade (default: literatura).

    Returns:
        λ restante ajustado pelo perfil NHPP.
    """
    if profile is None:
        profile = _DEFAULT_PROFILE

    if minute >= match_minutes or minute < 0:
        return 0.0
    if minute == 0:
        return lambda_full

    # Integral dos pesos sobre o jogo inteiro (para normalização)
    total_weighted = sum(b.weight * b.duration for b in profile)

    # Integral dos pesos sobre o tempo RESTANTE (minute → match_minutes)
    remaining_weighted = 0.0
    for b in profile:
        # Interseção do bucket com [minute, match_minutes]
        start = max(b.start_min, minute)
        end = min(b.end_min, match_minutes)
        if start < end:
            remaining_weighted += b.weight * (end - start)

    # λ_remaining = λ_full × (integral_restante / integral_total)
    return lambda_full * (remaining_weighted / total_weighted)


def compute_half_lambdas_nhpp(
    lambda_full: float,
    minute: int,
    match_minutes: int = 90,
    profile: list[IntensityBucket] | None = None,
) -> tuple[float, float]:
    """Calcula λ para 1H restante e 2H separadamente usando perfil NHPP.

    Returns:
        (lambda_remaining_1h, lambda_2h)
    """
    if profile is None:
        profile = _DEFAULT_PROFILE

    half = match_minutes // 2
    total_weighted = sum(b.weight * b.duration for b in profile)

    def integrate(from_min: int, to_min: int) -> float:
        w = 0.0
        for b in profile:
            start = max(b.start_min, from_min)
            end = min(b.end_min, to_min)
            if start < end:
                w += b.weight * (end - start)
        return w

    if minute <= half:
        lam_1h = lambda_full * integrate(minute, half) / total_weighted
        lam_2h = lambda_full * integrate(half, match_minutes) / total_weighted
    else:
        lam_1h = 0.0
        lam_2h = lambda_full * integrate(minute, match_minutes) / total_weighted

    return lam_1h, lam_2h


def intensity_at_minute(
    minute: int,
    profile: list[IntensityBucket] | None = None,
) -> float:
    """Retorna o peso de intensidade relativa em um minuto específico.

    Útil para visualizações e debug.
    """
    if profile is None:
        profile = _DEFAULT_PROFILE

    for b in profile:
        if b.start_min <= minute < b.end_min:
            return b.weight
    return 1.0  # fallback se fora do range


def validate_profile(profile: list[IntensityBucket], match_minutes: int = 90) -> bool:
    """Valida que o perfil cobre todo o jogo e tem média normalizada ~1.0."""
    total_duration = sum(b.duration for b in profile)
    if total_duration != match_minutes:
        return False

    total_weighted = sum(b.weight * b.duration for b in profile)
    avg_weight = total_weighted / match_minutes
    # Tolerância de 5% ao redor de 1.0
    return 0.95 <= avg_weight <= 1.05
