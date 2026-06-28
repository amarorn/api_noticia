"""Dependências compartilhadas do live_service (FastAPI Depends).

Expõe o WcPredictor via singleton thread-safe para uso em todos os routers
sem acoplamento direto a api/main.py.
"""
from __future__ import annotations

import threading
from typing import Annotated, Any

from fastapi import Depends, HTTPException

_predictor: Any = None
_predictor_lock = threading.Lock()


def get_predictor() -> "Any":
    """Retorna WcPredictor singleton, inicializando se necessário."""
    global _predictor
    if _predictor is None:
        with _predictor_lock:
            if _predictor is None:
                from models.wc_artifact import load_or_train_wc_predictor
                try:
                    _predictor, _ = load_or_train_wc_predictor()
                except Exception as exc:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Modelo WC não disponível: {exc}",
                    ) from exc
    return _predictor


def invalidate_predictor() -> None:
    """Força recarga do predictor na próxima chamada."""
    global _predictor
    with _predictor_lock:
        _predictor = None


# FastAPI Depends
PredictorDep = Annotated[Any, Depends(get_predictor)]
