"""
Marco teórico aplicado ao pipeline de previsão.

- LGN: métricas e calibração só com amostra suficiente.
- Coase: custo de transação mínimo para apostas com EV+.
- Dixit-Stiglitz: agregador CES de modelos (substituição entre variedades).
"""

from __future__ import annotations

import numpy as np

from config import settings

LABELS = ("1", "X", "2")


def lgn_min_sample_warning(n: int, context: str, min_n: int | None = None) -> str | None:
    threshold = min_n if min_n is not None else settings.lgn_min_samples
    if n < threshold:
        return (
            f"LGN: {context} tem n={n} (< {threshold}). "
            "Métricas agregadas podem variar muito; prefira mais jogos ou bootstrap."
        )
    return None


def bootstrap_accuracy_ci(
    y_true: list[str],
    y_pred: list[str],
    n_bootstrap: int | None = None,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict:
    if len(y_true) < 5:
        return {"n": len(y_true), "mean": None, "ci_low": None, "ci_high": None}

    n_bootstrap = n_bootstrap or settings.lgn_bootstrap_samples
    rng = np.random.default_rng(seed)
    y_t = np.array(y_true)
    y_p = np.array(y_pred)
    n = len(y_t)
    scores = [
        float(np.mean(y_t[rng.integers(0, n, size=n)] == y_p[rng.integers(0, n, size=n)]))
        for _ in range(n_bootstrap)
    ]
    arr = np.array(scores)
    return {
        "n": n,
        "mean": float(arr.mean()),
        "ci_low": float(np.percentile(arr, 100 * alpha / 2)),
        "ci_high": float(np.percentile(arr, 100 * (1 - alpha / 2))),
        "bootstrap_samples": n_bootstrap,
    }


def calibration_by_predicted_class(
    y_true: list[str],
    predictions: list[str],
    confidences: list[float],
    n_bins: int = 5,
) -> list[dict]:
    """LGN: em muitos jogos, taxa de acerto por faixa de confiança ~ confiança média."""
    if not y_true:
        return []
    pairs = sorted(
        zip(confidences, [1.0 if a == p else 0.0 for a, p in zip(y_true, predictions, strict=True)]),
    )
    chunk = max(1, len(pairs) // n_bins)
    out = []
    for i in range(0, len(pairs), chunk):
        block = pairs[i : i + chunk]
        if not block:
            continue
        out.append({
            "mean_confidence": float(np.mean([b[0] for b in block])),
            "observed_hit_rate": float(np.mean([b[1] for b in block])),
            "n": len(block),
        })
    return out


def coase_effective_min_edge(
    base_min_edge: float | None = None,
    bookmaker_margin: float | None = None,
) -> float:
    base = base_min_edge if base_min_edge is not None else settings.ev_min_edge
    margin = bookmaker_margin if bookmaker_margin is not None else settings.coase_bookmaker_margin
    return base + margin + settings.coase_transaction_cost


def ces_blend_probabilities(
    models: dict[str, dict[str, float]],
    weights: dict[str, float] | None = None,
    sigma: float | None = None,
) -> dict[str, float]:
    if not models:
        return {k: 1.0 / 3 for k in LABELS}

    sigma = sigma if sigma is not None else settings.dixit_sigma
    w = weights or {name: 1.0 / len(models) for name in models}
    total_w = sum(w.values()) or 1.0
    w = {k: v / total_w for k, v in w.items()}

    rho = (sigma - 1.0) / sigma if abs(sigma) > 1e-9 else 1.0
    blended: dict[str, float] = {}

    for label in LABELS:
        terms = []
        for name, probs in models.items():
            p = max(float(probs.get(label, 0.0)), 1e-9)
            terms.append(w.get(name, 0.0) * (p**rho))
        s = sum(terms)
        blended[label] = s ** (1.0 / rho) if s > 0 else 1.0 / 3

    total = sum(blended.values()) or 1.0
    return {k: v / total for k, v in blended.items()}
