"""Framework de A/B test contínuo para modelos in-play.

Permite comparar variantes do ensemble (A=atual, B=novo) de forma determinística:
  - Atribuição por hash(event_id) → estável entre chamadas
  - Log de predições em JSONL para análise posterior
  - Análise de métricas por variante (Brier, EV accuracy, win rate)

Uso:
    # No advice endpoint:
    from models.wc_ab_test import ABTestRegistry, log_prediction

    variant = ABTestRegistry.get_active().assign_variant(event_id)
    # ... rodar modelo do variant ...
    log_prediction(experiment_name="ensemble_v2", event_id=event_id,
                   variant=variant, probs=probs, label=y_final)

    # Análise (CLI: analyze-ab-test):
    from pipelines.wc_ab_analysis import analyze_experiment
    report = analyze_experiment("ensemble_v2")
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from config import settings

logger = logging.getLogger(__name__)

_AB_LOG_PATH = settings.lake_root / "ab_test" / "predictions.jsonl"
_AB_CONFIG_PATH = settings.lake_root / "ab_test" / "experiments.json"
_log_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Variante
# ---------------------------------------------------------------------------

class ABVariant(str, Enum):
    A = "A"  # controle (modelo atual)
    B = "B"  # tratamento (modelo novo)


# ---------------------------------------------------------------------------
# Configuração de experimento
# ---------------------------------------------------------------------------

@dataclass
class ABExperiment:
    """Definição de um experimento A/B."""

    name: str
    description: str = ""
    traffic_fraction_b: float = 0.5   # fração de tráfego para variante B
    active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    config_a: dict[str, Any] = field(default_factory=dict)  # config do controle
    config_b: dict[str, Any] = field(default_factory=dict)  # config do tratamento

    def assign_variant(self, event_id: int) -> ABVariant:
        """Atribuição determinística por hash do event_id.

        Mesmo event_id sempre recebe a mesma variante (estável entre chamadas).
        """
        h = int(hashlib.md5(f"{self.name}:{event_id}".encode()).hexdigest(), 16)
        fraction = (h % 1000) / 1000.0
        return ABVariant.B if fraction < self.traffic_fraction_b else ABVariant.A

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ABExperiment":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Registro de experimentos
# ---------------------------------------------------------------------------

class ABTestRegistry:
    """Gerencia experimentos A/B ativos."""

    def __init__(self, experiments: list[ABExperiment] | None = None) -> None:
        self._experiments: list[ABExperiment] = experiments or []

    @property
    def active_experiments(self) -> list[ABExperiment]:
        return [e for e in self._experiments if e.active]

    def get(self, name: str) -> ABExperiment | None:
        return next((e for e in self._experiments if e.name == name), None)

    def add(self, experiment: ABExperiment) -> None:
        self._experiments = [e for e in self._experiments if e.name != experiment.name]
        self._experiments.append(experiment)

    def save(self, path: Path | None = None) -> Path:
        path = path or _AB_CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [e.to_dict() for e in self._experiments]
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "ABTestRegistry":
        path = path or _AB_CONFIG_PATH
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text())
            experiments = [ABExperiment.from_dict(d) for d in data]
            return cls(experiments=experiments)
        except Exception:
            return cls()

    @classmethod
    def get_active(cls, name: str = "default") -> ABExperiment:
        """Retorna experimento ativo pelo nome (cria padrão se não existir)."""
        registry = cls.load()
        exp = registry.get(name)
        if exp is None:
            exp = ABExperiment(
                name=name,
                description="Experimento padrão: ensemble atual (A) vs novo (B)",
                traffic_fraction_b=0.5,
            )
        return exp


# ---------------------------------------------------------------------------
# Logging de predições
# ---------------------------------------------------------------------------

def log_prediction(
    experiment_name: str,
    event_id: int,
    variant: ABVariant,
    probs: dict[str, float],
    minute: float = 0.0,
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Registra uma predição A/B em JSONL para análise posterior.

    Thread-safe. Falha silenciosa para não bloquear o advice endpoint.

    Args:
        experiment_name: nome do experimento.
        event_id: ID do evento Superbet.
        variant: A ou B.
        probs: {"1": p, "X": p, "2": p} do modelo.
        minute: minuto da predição.
        label: resultado real ("1", "X", "2") se já disponível.
        metadata: dados extras (confiança, bucket, etc.).
    """
    record = {
        "experiment": experiment_name,
        "event_id": event_id,
        "variant": str(variant),
        "probs": probs,
        "minute": minute,
        "label": label,
        "metadata": metadata or {},
        "logged_at": datetime.now(UTC).isoformat(),
    }
    try:
        _AB_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _log_lock:
            with open(_AB_LOG_PATH, "a") as f:
                f.write(json.dumps(record) + "\n")
    except Exception as exc:
        logger.debug("ab_log_falhou: %s", exc)


def load_ab_log(
    experiment_name: str | None = None,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Carrega todas as predições logadas, filtrando por experimento."""
    path = path or _AB_LOG_PATH
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with open(path) as f:
        for line in f:
            try:
                rec = json.loads(line)
                if experiment_name is None or rec.get("experiment") == experiment_name:
                    records.append(rec)
            except json.JSONDecodeError:
                continue
    return records
