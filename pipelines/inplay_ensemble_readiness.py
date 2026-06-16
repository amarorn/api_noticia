"""Avalia prontidão para promover ensemble GBM de shadow → produção."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import settings


@dataclass
class EnsembleReadiness:
    """Status de promoção do stack Poisson+GBM."""

    mode: str  # shadow | canary | production
    ready_for_production: bool
    shadow_mode_active: bool
    n_feedback_high_confidence: int
    n_reconcile_pairs: int
    n_tick_examples: int
    inplay_delta_brier: float | None
    feedback_gbm_accepted: bool
    checks: dict[str, bool]
    missing: list[str]
    recommendation: str
    assessed_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _latest_feedback_manifest() -> dict[str, Any]:
    root = Path(settings.lake_root) / "artifacts"
    manifests = sorted(root.glob("inplay_gbm_feedback_v*.json"), reverse=True)
    if not manifests:
        return {}
    try:
        return json.loads(manifests[0].read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _inplay_delta_from_benchmark() -> float | None:
    try:
        from pipelines.model_benchmark_history import load_history

        history = load_history()
        latest = (history.get("snapshots") or [])[-1] if history.get("snapshots") else None
        if not latest:
            return None
        return (latest.get("metrics") or {}).get("inplay", {}).get("live_delta_brier")
    except Exception:
        return None


def assess_ensemble_readiness(user_id: str = "jamarorn") -> EnsembleReadiness:
    """Calcula gate para desligar ``inplay_ensemble_shadow_mode``."""
    from pipelines.inplay_synthetic_feedback import count_synthetic_examples
    from pipelines.user_bet_reconciliation import load_reconciliation

    df = load_reconciliation(user_id)
    n_pairs = len(df)
    n_hi = int((df["match_confidence"].fillna(0) >= 0.7).sum()) if not df.empty else 0
    n_ticks = count_synthetic_examples()
    delta = _inplay_delta_from_benchmark()
    fb = _latest_feedback_manifest()
    fb_accepted = bool(fb.get("brier_delta", 0) >= 0.002) if fb else False

    min_hi = settings.inplay_ensemble_min_feedback_hi
    min_ticks = settings.inplay_ensemble_min_tick_examples
    min_delta = settings.inplay_ensemble_min_inplay_delta
    prod_hi = settings.inplay_ensemble_prod_feedback_hi

    checks = {
        "feedback_hi": n_hi >= min_hi,
        "tick_examples": n_ticks >= min_ticks,
        "inplay_beats_market": delta is not None and float(delta) <= -min_delta,
        "feedback_gbm_promoted": fb_accepted,
        "production_volume": n_hi >= prod_hi,
    }

    missing = [k for k, ok in checks.items() if not ok]

    if checks["production_volume"] and checks["inplay_beats_market"] and (
        checks["feedback_gbm_promoted"] or checks["tick_examples"]
    ):
        mode = "production"
        ready = True
        rec = (
            "Critérios atingidos. Defina INPLAY_ENSEMBLE_SHADOW_MODE=false no .env "
            "e reinicie a API."
        )
    elif checks["feedback_hi"] and checks["tick_examples"] and checks["inplay_beats_market"]:
        mode = "canary"
        ready = False
        rec = (
            f"Canary: faltam {max(0, prod_hi - n_hi)} exemplos alta confiança "
            f"(meta {prod_hi}) ou promoção GBM feedback."
        )
    else:
        mode = "shadow"
        ready = False
        rec = (
            f"Shadow ativo. Acumule CSV+poll: {n_hi}/{min_hi} alta confiança, "
            f"{n_ticks}/{min_ticks} ticks rotulados."
        )

    return EnsembleReadiness(
        mode=mode,
        ready_for_production=ready,
        shadow_mode_active=settings.inplay_ensemble_shadow_mode,
        n_feedback_high_confidence=n_hi,
        n_reconcile_pairs=n_pairs,
        n_tick_examples=n_ticks,
        inplay_delta_brier=float(delta) if delta is not None else None,
        feedback_gbm_accepted=fb_accepted,
        checks=checks,
        missing=missing,
        recommendation=rec,
        assessed_at=datetime.now(UTC).isoformat(),
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Verifica prontidão do ensemble in-play GBM.")
    parser.add_argument("--user", default=settings.superbet_finalize_user_id)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = assess_ensemble_readiness(args.user)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Modo: {report.mode} | shadow={report.shadow_mode_active}")
        print(f"Feedback alta conf: {report.n_feedback_high_confidence}")
        print(f"Ticks rotulados: {report.n_tick_examples}")
        print(f"Δ Brier in-play: {report.inplay_delta_brier}")
        print(report.recommendation)
    return 0 if report.ready_for_production else 0


if __name__ == "__main__":
    raise SystemExit(main())
