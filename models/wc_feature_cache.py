"""Cache de matriz de features para retreino WC (evita recomputar ~5k jogos)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from config import settings

CACHE_NAME = "logistic_features_cache.json"


def _fingerprint(train_df: pd.DataFrame) -> str:
    payload = {
        "rows": len(train_df),
        "max_date": str(train_df["match_date"].max()) if not train_df.empty else "",
        "min_date": str(train_df["match_date"].min()) if not train_df.empty else "",
        "labels_copa_only": settings.wc_train_labels_copa_only,
        "holdout_mode": settings.wc_holdout_mode,
        "train_split_ratio": settings.wc_train_split_ratio,
        "val_split_ratio": settings.wc_val_split_ratio,
        "test_split_ratio": settings.wc_test_split_ratio,
    }
    raw = json.dumps(payload, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def cache_path() -> Path:
    return settings.wc_artifact_dir / CACHE_NAME


def load_cached_features(
    train_df: pd.DataFrame,
) -> tuple[list[list[float]], list[str]] | None:
    path = cache_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("fingerprint") != _fingerprint(train_df):
            return None
        return data["x_rows"], data["y_rows"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def save_cached_features(
    train_df: pd.DataFrame,
    x_rows: list[list[float]],
    y_rows: list[str],
) -> None:
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "fingerprint": _fingerprint(train_df),
                "train_size": len(y_rows),
                "x_rows": x_rows,
                "y_rows": y_rows,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
