"""Ensemble dinâmico para probabilidades in-play.

Combina 4 fontes de probabilidade com pesos que variam por bucket temporal:
1. Poisson/Monte Carlo (modelo base, Fase 1)
2. Hawkes (clustering de gols, Fase 3.1)
3. GBM (features de estado, Fase 3.3)
4. Market (odds da casa, shrinkage)

Os pesos são ajustados por bucket de minuto (0–15, 15–30, 30–45, etc.)
porque cada modelo tem vantagens em momentos diferentes:
- Poisson: forte no início (antes de eventos mudar o cenário)
- Hawkes: forte após gols (captura retaliação)
- GBM: forte com muitas features (corners, reds, etc.)
- Market: forte com liquidez alta (pré-jogo e início)

Spec: docs/specs/spec-fase-3-modelo-avancado.md § 5.3
"""
from __future__ import annotations

from dataclasses import dataclass, field


# Buckets temporais (minuto inicial do bucket)
TIME_BUCKETS = [0, 15, 30, 45, 60, 75]
BUCKET_NAMES = ["0-15", "15-30", "30-45", "45-60", "60-75", "75-90"]


@dataclass
class EnsembleWeights:
    """Pesos do ensemble por componente e por bucket temporal.

    Formato: weights[bucket_idx] = (w_poisson, w_hawkes, w_gbm, w_market)
    """

    # Pesos por bucket [poisson, hawkes, gbm, market]
    # Default: início favorece Poisson+Market, final favorece Hawkes+GBM
    bucket_weights: list[list[float]] = field(default_factory=lambda: [
        [0.35, 0.10, 0.15, 0.40],  # 0–15 min: market forte, Poisson ok
        [0.30, 0.15, 0.20, 0.35],  # 15–30 min: GBM ganha peso
        [0.30, 0.20, 0.25, 0.25],  # 30–45 min: equilibrado
        [0.25, 0.25, 0.25, 0.25],  # 45–60 min: todos iguais
        [0.20, 0.30, 0.30, 0.20],  # 60–75 min: Hawkes+GBM dominam
        [0.15, 0.35, 0.35, 0.15],  # 75–90 min: modelos > market (liquidez cai)
    ])

    def get_weights(self, minute: float) -> tuple[float, float, float, float]:
        """Retorna pesos (poisson, hawkes, gbm, market) para o minuto dado."""
        bucket_idx = min(int(minute / 15), len(self.bucket_weights) - 1)
        bucket_idx = max(0, bucket_idx)
        w = self.bucket_weights[bucket_idx]
        return (w[0], w[1], w[2], w[3])

    def get_bucket_name(self, minute: float) -> str:
        """Nome do bucket para logging."""
        bucket_idx = min(int(minute / 15), len(BUCKET_NAMES) - 1)
        return BUCKET_NAMES[max(0, bucket_idx)]


@dataclass
class EnsembleInput:
    """Entrada para o ensemble: probabilidades de cada fonte."""

    minute: float

    # Probabilidades 1X2 de cada modelo
    poisson_probs: dict[str, float] | None = None   # {"1": p, "X": p, "2": p}
    hawkes_probs: dict[str, float] | None = None
    gbm_probs: dict[str, float] | None = None
    market_probs: dict[str, float] | None = None

    # Flag de disponibilidade (modelo pode não ter dados)
    poisson_available: bool = True
    hawkes_available: bool = True
    gbm_available: bool = True
    market_available: bool = True


@dataclass
class EnsembleResult:
    """Resultado do ensemble com breakdown por componente."""

    probs: dict[str, float]             # {"1": p, "X": p, "2": p} final
    weights_used: tuple[float, ...]     # pesos efetivos (após redistribuição)
    bucket: str                         # "60-75"
    components_used: list[str]          # ["poisson", "hawkes", "gbm", "market"]
    raw_contributions: dict[str, dict[str, float]]  # por componente

    @property
    def prob_home(self) -> float:
        return self.probs.get("1", 0.0)

    @property
    def prob_draw(self) -> float:
        return self.probs.get("X", 0.0)

    @property
    def prob_away(self) -> float:
        return self.probs.get("2", 0.0)


def blend_ensemble(
    inputs: EnsembleInput,
    weights: EnsembleWeights | None = None,
) -> EnsembleResult:
    """Combina probabilidades de múltiplos modelos com pesos dinâmicos.

    Fluxo:
    1. Tenta usar o meta-learner (StackedEnsemble) se disponível.
    2. Fallback: média ponderada com pesos manuais por bucket temporal.
    3. Se market_probs disponível, aplica shrinkage final em prob space.

    Args:
        inputs: probabilidades de cada fonte + metadata.
        weights: configuração de pesos manuais (fallback).

    Returns:
        EnsembleResult com probabilidades finais e breakdown.
    """
    if weights is None:
        weights = EnsembleWeights()

    bucket_name = weights.get_bucket_name(inputs.minute)
    raw_contributions: dict[str, dict[str, float]] = {}

    # --- Tentar meta-learner (Item 2: stacking aprendido) ---
    try:
        from models.wc_ensemble_stack import build_meta_features, get_stack

        stack = get_stack()
        if stack is not None:
            meta = build_meta_features(
                poisson_probs=inputs.poisson_probs,
                hawkes_probs=inputs.hawkes_probs,
                gbm_probs=inputs.gbm_probs,
                market_probs=inputs.market_probs,
                minute=inputs.minute,
            )
            stacked_probs = stack.predict(meta)
            for name, probs in [
                ("poisson", inputs.poisson_probs),
                ("hawkes", inputs.hawkes_probs),
                ("gbm", inputs.gbm_probs),
                ("market", inputs.market_probs),
            ]:
                if probs:
                    raw_contributions[name] = probs
            return EnsembleResult(
                probs=stacked_probs,
                weights_used=(0.0, 0.0, 0.0, 0.0),
                bucket=bucket_name,
                components_used=list(raw_contributions.keys()),
                raw_contributions=raw_contributions,
            )
    except Exception:
        pass  # fallback silencioso para pesos manuais

    # --- Fallback: pesos manuais por bucket (comportamento original) ---
    w_poisson, w_hawkes, w_gbm, w_market = weights.get_weights(inputs.minute)

    sources: list[tuple[str, dict[str, float], float]] = []
    if inputs.poisson_available and inputs.poisson_probs:
        sources.append(("poisson", inputs.poisson_probs, w_poisson))
    if inputs.hawkes_available and inputs.hawkes_probs:
        sources.append(("hawkes", inputs.hawkes_probs, w_hawkes))
    if inputs.gbm_available and inputs.gbm_probs:
        sources.append(("gbm", inputs.gbm_probs, w_gbm))
    if inputs.market_available and inputs.market_probs:
        sources.append(("market", inputs.market_probs, w_market))

    if not sources:
        return EnsembleResult(
            probs={"1": 1 / 3, "X": 1 / 3, "2": 1 / 3},
            weights_used=(0.0, 0.0, 0.0, 0.0),
            bucket=bucket_name,
            components_used=[],
            raw_contributions={},
        )

    total_weight = sum(w for _, _, w in sources)
    if total_weight <= 0:
        total_weight = len(sources)

    normalized_sources = [(name, probs, w / total_weight) for name, probs, w in sources]

    # Blend via média ponderada (excluindo market do blend para evitar dupla contagem)
    model_sources = [(n, p, w) for n, p, w in normalized_sources if n != "market"]
    market_entry = next(((p, w) for n, p, w in normalized_sources if n == "market"), None)

    if model_sources:
        model_total_w = sum(w for _, _, w in model_sources)
        model_renorm = [(n, p, w / model_total_w) for n, p, w in model_sources] if model_total_w > 0 else model_sources

        final_probs = {"1": 0.0, "X": 0.0, "2": 0.0}
        for name, probs, w in model_renorm:
            raw_contributions[name] = probs
            for key in final_probs:
                final_probs[key] += w * probs.get(key, 0.0)

        # Normalizar probs dos modelos
        tot = sum(final_probs.values())
        if tot > 0:
            final_probs = {k: v / tot for k, v in final_probs.items()}

        # Aplicar shrinkage em prob space (Item 4) se market disponível
        if market_entry is not None:
            market_p, _ = market_entry
            raw_contributions["market"] = market_p
            try:
                from models.wc_market_shrinkage import shrink_probs_1x2
                final_probs = shrink_probs_1x2(final_probs, market_p, int(inputs.minute))
            except Exception:
                # fallback: blend direto como antes
                for key in final_probs:
                    final_probs[key] = (
                        final_probs[key] * (1 - w_market) + market_p.get(key, 1 / 3) * w_market
                    )
                tot2 = sum(final_probs.values())
                if tot2 > 0:
                    final_probs = {k: v / tot2 for k, v in final_probs.items()}
    else:
        # Só market disponível
        final_probs = dict(inputs.market_probs or {"1": 1/3, "X": 1/3, "2": 1/3})
        raw_contributions["market"] = final_probs

    weights_used = tuple(w for _, _, w in normalized_sources)
    return EnsembleResult(
        probs=final_probs,
        weights_used=weights_used,
        bucket=bucket_name,
        components_used=[name for name, _, _ in normalized_sources],
        raw_contributions=raw_contributions,
    )


def gbm_probs_to_1x2(
    prob_no_goal: float,
    prob_goal_home: float,
    prob_goal_away: float,
    current_home_score: int,
    current_away_score: int,
) -> dict[str, float]:
    """Converte probabilidades GBM (next goal window) em 1X2 final.

    Heurística: se gol home, home_score sobe → mais chance de vitória home.
    Se gol away, away_score sobe. Se sem gol, resultado atual se mantém.

    Esta é uma aproximação simplificada — o ensemble real usa Monte Carlo.
    """
    # Se sem gol: resultado segue o placar atual
    if current_home_score > current_away_score:
        p_1_no = 0.70
        p_x_no = 0.20
        p_2_no = 0.10
    elif current_home_score == current_away_score:
        p_1_no = 0.30
        p_x_no = 0.40
        p_2_no = 0.30
    else:
        p_1_no = 0.10
        p_x_no = 0.20
        p_2_no = 0.70

    # Se gol home: home vence mais provável
    p_1_gh = 0.80
    p_x_gh = 0.15
    p_2_gh = 0.05

    # Se gol away: away vence mais provável
    p_1_ga = 0.05
    p_x_ga = 0.15
    p_2_ga = 0.80

    # Combinar
    p1 = prob_no_goal * p_1_no + prob_goal_home * p_1_gh + prob_goal_away * p_1_ga
    px = prob_no_goal * p_x_no + prob_goal_home * p_x_gh + prob_goal_away * p_x_ga
    p2 = prob_no_goal * p_2_no + prob_goal_home * p_2_gh + prob_goal_away * p_2_ga

    # Normalizar
    total = p1 + px + p2
    return {"1": p1 / total, "X": px / total, "2": p2 / total}
