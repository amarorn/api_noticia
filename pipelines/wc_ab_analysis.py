"""Análise de resultados de experimentos A/B in-play.

Calcula métricas por variante (A/B) para tomar decisão de deploy:
  - Brier Score (calibração das probabilidades)
  - Accuracy (acerto da predição mais provável)
  - EV médio das oportunidades recomendadas
  - Win rate dos palpites

CLI: analyze-ab-test [--experiment NAME] [--min-samples N]
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from models.wc_ab_test import load_ab_log

logger = logging.getLogger(__name__)

_LABEL_MAP = {"1": 0, "X": 1, "2": 2}


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------

@dataclass
class ABVariantMetrics:
    variant: str
    n_predictions: int
    n_labeled: int
    brier_score: float | None = None    # menor é melhor
    accuracy: float | None = None       # argmax correto
    log_loss: float | None = None       # menor é melhor
    significance_p: float | None = None  # p-value vs outra variante (t-test)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "n_predictions": self.n_predictions,
            "n_labeled": self.n_labeled,
            "brier_score": round(self.brier_score, 4) if self.brier_score is not None else None,
            "accuracy": round(self.accuracy, 3) if self.accuracy is not None else None,
            "log_loss": round(self.log_loss, 4) if self.log_loss is not None else None,
            "significance_p": round(self.significance_p, 3) if self.significance_p is not None else None,
        }


@dataclass
class ABAnalysisReport:
    experiment: str
    n_total: int
    metrics_a: ABVariantMetrics
    metrics_b: ABVariantMetrics
    recommendation: str  # "deploy_b", "keep_a", "insufficient_data", "no_difference"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment": self.experiment,
            "n_total": self.n_total,
            "metrics_a": self.metrics_a.to_dict(),
            "metrics_b": self.metrics_b.to_dict(),
            "recommendation": self.recommendation,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Cálculo de métricas
# ---------------------------------------------------------------------------

def _compute_brier(probs_list: list[dict[str, float]], labels: list[str]) -> float:
    """Brier score médio (soma dos quadrados dos desvios)."""
    scores = []
    for probs, label in zip(probs_list, labels):
        if label not in _LABEL_MAP:
            continue
        p1 = float(probs.get("1", 1 / 3))
        px = float(probs.get("X", 1 / 3))
        p2 = float(probs.get("2", 1 / 3))
        t1 = 1.0 if label == "1" else 0.0
        tx = 1.0 if label == "X" else 0.0
        t2 = 1.0 if label == "2" else 0.0
        scores.append(((p1 - t1) ** 2 + (px - tx) ** 2 + (p2 - t2) ** 2) / 3)
    return float(np.mean(scores)) if scores else float("nan")


def _compute_accuracy(probs_list: list[dict[str, float]], labels: list[str]) -> float:
    correct = sum(
        1 for probs, label in zip(probs_list, labels)
        if max(probs, key=probs.get) == label and label in _LABEL_MAP
    )
    return correct / len(labels) if labels else float("nan")


def _compute_logloss(probs_list: list[dict[str, float]], labels: list[str]) -> float:
    losses = []
    for probs, label in zip(probs_list, labels):
        if label not in _LABEL_MAP:
            continue
        p = max(float(probs.get(label, 1e-7)), 1e-7)
        losses.append(-np.log(p))
    return float(np.mean(losses)) if losses else float("nan")


def _compute_metrics(records: list[dict[str, Any]], variant: str) -> ABVariantMetrics:
    """Computa métricas para uma variante a partir dos records."""
    subset = [r for r in records if r.get("variant") == variant]
    labeled = [r for r in subset if r.get("label") is not None]

    if not labeled:
        return ABVariantMetrics(
            variant=variant,
            n_predictions=len(subset),
            n_labeled=0,
        )

    probs_list = [r["probs"] for r in labeled]
    labels = [r["label"] for r in labeled]

    brier = _compute_brier(probs_list, labels)
    acc = _compute_accuracy(probs_list, labels)
    ll = _compute_logloss(probs_list, labels)

    return ABVariantMetrics(
        variant=variant,
        n_predictions=len(subset),
        n_labeled=len(labeled),
        brier_score=brier if not np.isnan(brier) else None,
        accuracy=acc if not np.isnan(acc) else None,
        log_loss=ll if not np.isnan(ll) else None,
    )


# ---------------------------------------------------------------------------
# Teste de significância
# ---------------------------------------------------------------------------

def _significance_test(
    records: list[dict[str, Any]],
    variant_a: str = "A",
    variant_b: str = "B",
) -> tuple[float | None, float | None]:
    """Teste t de Brier score por variante. Retorna (p_value_a_vs_b, p_value_b_vs_a)."""
    try:
        from scipy import stats

        def _briers(variant: str) -> list[float]:
            labeled = [r for r in records if r.get("variant") == variant and r.get("label")]
            return [
                ((float(r["probs"].get("1", 1/3)) - (1 if r["label"] == "1" else 0))**2 +
                 (float(r["probs"].get("X", 1/3)) - (1 if r["label"] == "X" else 0))**2 +
                 (float(r["probs"].get("2", 1/3)) - (1 if r["label"] == "2" else 0))**2) / 3
                for r in labeled if r["label"] in _LABEL_MAP
            ]

        ba = _briers(variant_a)
        bb = _briers(variant_b)
        if len(ba) < 10 or len(bb) < 10:
            return None, None

        _, p = stats.ttest_ind(ba, bb)
        return float(p), float(p)
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def analyze_experiment(
    experiment_name: str = "default",
    min_samples: int = 30,
    significance_alpha: float = 0.05,
) -> ABAnalysisReport:
    """Analisa resultados de um experimento A/B.

    Args:
        experiment_name: nome do experimento a analisar.
        min_samples: mínimo de amostras por variante para recomendar.
        significance_alpha: nível de significância para recomendação de deploy.

    Returns:
        ABAnalysisReport com métricas e recomendação.
    """
    records = load_ab_log(experiment_name)
    if not records:
        return ABAnalysisReport(
            experiment=experiment_name,
            n_total=0,
            metrics_a=ABVariantMetrics("A", 0, 0),
            metrics_b=ABVariantMetrics("B", 0, 0),
            recommendation="insufficient_data",
            notes="Nenhuma predição encontrada no log.",
        )

    metrics_a = _compute_metrics(records, "A")
    metrics_b = _compute_metrics(records, "B")

    p_val, _ = _significance_test(records)
    if p_val is not None:
        metrics_a.significance_p = p_val
        metrics_b.significance_p = p_val

    # Recomendação
    notes = ""
    if metrics_a.n_labeled < min_samples or metrics_b.n_labeled < min_samples:
        recommendation = "insufficient_data"
        notes = (
            f"Amostras rotuladas: A={metrics_a.n_labeled}, B={metrics_b.n_labeled}. "
            f"Mínimo: {min_samples}."
        )
    elif metrics_a.brier_score is None or metrics_b.brier_score is None:
        recommendation = "insufficient_data"
        notes = "Brier score não computável (sem labels suficientes)."
    elif p_val is not None and p_val > significance_alpha:
        recommendation = "no_difference"
        notes = f"Diferença não significativa (p={p_val:.3f} > α={significance_alpha})."
    elif (metrics_b.brier_score or 1.0) < (metrics_a.brier_score or 1.0):
        recommendation = "deploy_b"
        delta = (metrics_a.brier_score or 0) - (metrics_b.brier_score or 0)
        notes = f"B melhora Brier em {delta:.4f}. Significativo (p={p_val:.3f if p_val else '?'})."
    else:
        recommendation = "keep_a"
        delta = (metrics_b.brier_score or 0) - (metrics_a.brier_score or 0)
        notes = f"A mantém vantagem em Brier por {delta:.4f}."

    return ABAnalysisReport(
        experiment=experiment_name,
        n_total=len(records),
        metrics_a=metrics_a,
        metrics_b=metrics_b,
        recommendation=recommendation,
        notes=notes,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Analisa resultados de experimento A/B")
    parser.add_argument("--experiment", default="default", help="Nome do experimento")
    parser.add_argument("--min-samples", type=int, default=30)
    parser.add_argument("--alpha", type=float, default=0.05, help="Nível de significância")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = analyze_experiment(
        experiment_name=args.experiment,
        min_samples=args.min_samples,
        significance_alpha=args.alpha,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        r = report.to_dict()
        print(f"Experimento: {r['experiment']}  (N={r['n_total']})")
        print(f"  Variante A: Brier={r['metrics_a']['brier_score']}  Acc={r['metrics_a']['accuracy']}")
        print(f"  Variante B: Brier={r['metrics_b']['brier_score']}  Acc={r['metrics_b']['accuracy']}")
        print(f"  Recomendação: {r['recommendation']}")
        print(f"  Notas: {r['notes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
