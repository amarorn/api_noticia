"""
Persistência do WcPredictor (Sprint 2): evita retreino de ~45s a cada restart da API.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pickle
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import structlog

from config import settings
from models.wc_predictor import WcPredictor, train_wc_predictor
from pipelines.wc_squad_features import squads_fingerprint
from pipelines.wc_stats import FEATURE_NAMES

logger = structlog.get_logger()

ARTIFACT_VERSION = 2


def fixtures_fingerprint() -> str:
    paths = sorted(settings.fixtures_path.glob("world_cup_*.parquet"))
    if not paths:
        return "empty"
    parts = [f"{p.name}:{p.stat().st_mtime_ns}:{p.stat().st_size}" for p in paths]
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return digest[:16]


def _manifest_path() -> Path:
    return settings.wc_artifact_dir / "manifest.json"


def _bundle_path() -> Path:
    return settings.wc_artifact_dir / "predictor.pkl"


def read_manifest() -> dict | None:
    path = _manifest_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_is_valid(manifest: dict | None = None) -> bool:
    manifest = manifest or read_manifest()
    if not manifest or not _bundle_path().exists():
        return False
    if manifest.get("artifact_version") != ARTIFACT_VERSION:
        return False
    if manifest.get("fixtures_fingerprint") != fixtures_fingerprint():
        return False
    if manifest.get("squads_fingerprint") != squads_fingerprint():
        return False
    if manifest.get("feature_names") != FEATURE_NAMES:
        return False
    return True


def save_artifact(predictor: WcPredictor) -> dict:
    settings.wc_artifact_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "logistic": predictor.logistic,
        "dixon_coles": predictor.dixon_coles,
        "collaborative": predictor.collaborative,
        "_metrics": predictor._metrics,
        "_dc_metrics": predictor._dc_metrics,
    }
    _bundle_path().write_bytes(pickle.dumps(bundle, protocol=pickle.HIGHEST_PROTOCOL))

    manifest = {
        "artifact_version": ARTIFACT_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "fixtures_fingerprint": fixtures_fingerprint(),
        "squads_fingerprint": squads_fingerprint(),
        "feature_names": FEATURE_NAMES,
        "fixture_rows": int(len(predictor.fixtures)),
        "training_metrics": predictor.training_metrics,
        "collab_metrics": (
            asdict(predictor.collab_metrics) if predictor.collab_metrics else {}
        ),
        "ensemble_weights": {
            "dixon_coles": predictor.collaborative.dixon_coles_weight,
            "logistic": predictor.collaborative.logistic_weight,
        },
    }
    _manifest_path().write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("wc_artifact_saved", path=str(settings.wc_artifact_dir))
    return manifest


def load_artifact() -> WcPredictor | None:
    if not artifact_is_valid():
        return None
    from ingest.fixtures.world_cup import load_wc_fixtures

    bundle = pickle.loads(_bundle_path().read_bytes())
    fixtures = load_wc_fixtures()
    if fixtures.empty:
        return None

    predictor = WcPredictor.__new__(WcPredictor)
    predictor.fixtures = fixtures
    predictor.logistic = bundle["logistic"]
    predictor.dixon_coles = bundle["dixon_coles"]
    predictor.collaborative = bundle["collaborative"]
    predictor._metrics = bundle["_metrics"]
    predictor._dc_metrics = bundle["_dc_metrics"]
    predictor.collab_metrics = predictor.collaborative.metrics
    return predictor


def load_or_train_wc_predictor(*, force: bool = False) -> tuple[WcPredictor, dict]:
    if not force:
        loaded = load_artifact()
        if loaded is not None:
            manifest = read_manifest() or {}
            manifest["loaded_from_cache"] = True
            logger.info("wc_artifact_loaded", created_at=manifest.get("created_at"))
            return loaded, manifest

    predictor = train_wc_predictor()
    manifest = save_artifact(predictor)
    manifest["loaded_from_cache"] = False
    return predictor, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Treina e persiste o modelo da Copa do Mundo")
    parser.add_argument("--force", action="store_true", help="Ignora artefato em cache e retreina")
    args = parser.parse_args()
    predictor, manifest = load_or_train_wc_predictor(force=args.force)
    print(f"Artefato: {settings.wc_artifact_dir}")
    print(f"Jogos no lake: {len(predictor.fixtures)}")
    print(f"Holdout acurácia: {manifest.get('training_metrics', {}).get('holdout_accuracy')}")
    print(f"Ensemble Brier: {manifest.get('collab_metrics', {}).get('brier_score')}")
    print(f"Pesos: {manifest.get('ensemble_weights')}")


if __name__ == "__main__":
    main()
