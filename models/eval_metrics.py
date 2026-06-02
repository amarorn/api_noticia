from __future__ import annotations

import numpy as np

LABELS = ("1", "X", "2")


def brier_score(y_true: list[str], probs: np.ndarray, classes: list[str] | None = None) -> float:
    classes = list(classes or LABELS)
    total = 0.0
    for idx, y in enumerate(y_true):
        for c_idx, c in enumerate(classes):
            target = 1.0 if y == c else 0.0
            total += float((probs[idx, c_idx] - target) ** 2)
    return total / (len(y_true) * len(classes))


def log_loss_score(
    y_true: list[str],
    probs: np.ndarray,
    classes: list[str] | None = None,
    eps: float = 1e-12,
) -> float:
    classes = list(classes or LABELS)
    class_to_idx = {c: i for i, c in enumerate(classes)}
    total = 0.0
    for idx, y in enumerate(y_true):
        p = float(probs[idx, class_to_idx[y]])
        p = min(max(p, eps), 1.0 - eps)
        total += -np.log(p)
    return total / len(y_true)


def classification_metrics(y_true: list[str], probs: np.ndarray) -> dict:
    from sklearn.metrics import accuracy_score

    classes = list(LABELS)
    preds = [classes[int(np.argmax(p))] for p in probs]
    return {
        "accuracy": float(accuracy_score(y_true, preds)),
        "brier": float(brier_score(y_true, probs, classes)),
        "log_loss": float(log_loss_score(y_true, probs, classes)),
    }
