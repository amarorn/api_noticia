"""Persistência de coeficientes calibrados do modelo in-play.

Armazena os β's do momentum (estimados por MLE) e os pesos NHPP
calibrados em um arquivo JSON versionado. O módulo `wc_live_momentum`
e `wc_intensity_profile` carregam esses coeficientes em runtime;
se ausentes, usam as constantes default da Fase 1.

Spec: docs/specs/spec-fase-2-momentum-calibrado.md § 5.5
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import settings


# Localização padrão do arquivo de coeficientes
_DEFAULT_PATH = Path("data/lake/artifacts/inplay_coefficients.json")


@dataclass
class MomentumBeta:
    """Um coeficiente β do modelo de momentum com intervalo de confiança."""

    name: str
    value: float
    std_error: float
    z_score: float = 0.0
    significant: bool = False  # |z| > 1.96

    def __post_init__(self):
        if self.std_error > 0:
            self.z_score = round(self.value / self.std_error, 3)
            self.significant = abs(self.z_score) > 1.96


@dataclass
class NHPPWeight:
    """Peso estimado para um bucket temporal do perfil NHPP."""

    start_min: int
    end_min: int
    weight: float
    std_error: float = 0.0


@dataclass
class InPlayCoefficients:
    """Coeficientes calibrados do modelo in-play (momentum + NHPP).

    Persistidos em JSON. Carregados por wc_live_momentum e wc_intensity_profile
    em runtime. Se o arquivo não existir, os módulos usam constantes default.
    """

    # Coeficientes do momentum (log-linear sobre multiplicador de λ)
    momentum_betas: list[MomentumBeta] = field(default_factory=list)

    # Pesos NHPP calibrados (substituem os default da literatura)
    nhpp_weights: list[NHPPWeight] = field(default_factory=list)

    # Metadados do treinamento
    trained_at: str = ""
    train_seasons: list[int] = field(default_factory=list)
    n_observations: int = 0
    in_sample_loglik: float = 0.0
    holdout_brier: float = 0.0
    holdout_brier_baseline: float = 0.0  # Brier sem momentum (para comparação)
    dataset_hash: str = ""

    def __post_init__(self):
        if not self.trained_at:
            self.trained_at = datetime.now(UTC).isoformat()

    # ------------------------------------------------------------------
    # Acesso rápido por nome
    # ------------------------------------------------------------------

    def get_beta(self, name: str) -> float | None:
        """Retorna valor de um β pelo nome. None se não encontrado."""
        for b in self.momentum_betas:
            if b.name == name:
                return b.value
        return None

    def get_significant_betas(self) -> list[MomentumBeta]:
        """Retorna apenas os β's estatisticamente significativos (|z| > 1.96)."""
        return [b for b in self.momentum_betas if b.significant]

    def nhpp_weight_at(self, minute: int) -> float | None:
        """Retorna peso NHPP para um minuto específico. None se fora do range."""
        for w in self.nhpp_weights:
            if w.start_min <= minute < w.end_min:
                return w.weight
        return None

    # ------------------------------------------------------------------
    # Serialização
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serializa para dict (JSON-compatível)."""
        return {
            "momentum_betas": [asdict(b) for b in self.momentum_betas],
            "nhpp_weights": [asdict(w) for w in self.nhpp_weights],
            "trained_at": self.trained_at,
            "train_seasons": self.train_seasons,
            "n_observations": self.n_observations,
            "in_sample_loglik": self.in_sample_loglik,
            "holdout_brier": self.holdout_brier,
            "holdout_brier_baseline": self.holdout_brier_baseline,
            "dataset_hash": self.dataset_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InPlayCoefficients:
        """Reconstrói a partir de dict (lido do JSON)."""
        betas = [MomentumBeta(**b) for b in data.get("momentum_betas", [])]
        weights = [NHPPWeight(**w) for w in data.get("nhpp_weights", [])]
        return cls(
            momentum_betas=betas,
            nhpp_weights=weights,
            trained_at=data.get("trained_at", ""),
            train_seasons=data.get("train_seasons", []),
            n_observations=data.get("n_observations", 0),
            in_sample_loglik=data.get("in_sample_loglik", 0.0),
            holdout_brier=data.get("holdout_brier", 0.0),
            holdout_brier_baseline=data.get("holdout_brier_baseline", 0.0),
            dataset_hash=data.get("dataset_hash", ""),
        )


# ------------------------------------------------------------------
# I/O
# ------------------------------------------------------------------


def save_inplay_coefficients(
    coefficients: InPlayCoefficients,
    path: Path | None = None,
) -> Path:
    """Salva coeficientes em JSON."""
    if path is None:
        path = settings.lake_root / "artifacts" / "inplay_coefficients.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(coefficients.to_dict(), indent=2, ensure_ascii=False))
    return path


def load_inplay_coefficients(path: Path | None = None) -> InPlayCoefficients | None:
    """Carrega coeficientes do JSON. Retorna None se arquivo não existir."""
    if path is None:
        path = settings.lake_root / "artifacts" / "inplay_coefficients.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return InPlayCoefficients.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def compute_dataset_hash(timeline_path: Path) -> str:
    """Gera hash SHA-256 do dataset timeline para versionamento."""
    if not timeline_path.exists():
        return "missing"
    h = hashlib.sha256()
    for f in sorted(timeline_path.rglob("*.parquet")):
        h.update(f.name.encode())
        h.update(str(f.stat().st_size).encode())
    return h.hexdigest()[:16]
