"""Estado compartilhado e dependências da API.

Centraliza o predictor WC e metadados de treino para evitar
estado global espalhado pelo main.py.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.wc_predictor import WcPredictor

from config import settings

_wc_models_ready: bool = False
_wc_predictor: "WcPredictor | None" = None
_wc_artifact_meta: dict = {}
_wc_train_lock = threading.Lock()
_wc_train_thread: threading.Thread | None = None


def get_wc_predictor(*, force: bool = False) -> "WcPredictor":
    global _wc_predictor, _wc_artifact_meta
    from models.wc_artifact import load_or_train_wc_predictor

    if force or _wc_predictor is None:
        _wc_predictor, _wc_artifact_meta = load_or_train_wc_predictor(
            force=force or settings.wc_artifact_force_retrain,
            allow_train=force or settings.wc_artifact_force_retrain,
        )
    return _wc_predictor


def is_models_ready() -> bool:
    return _wc_models_ready


def get_artifact_meta() -> dict:
    return _wc_artifact_meta
