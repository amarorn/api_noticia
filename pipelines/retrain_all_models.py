"""Orquestra o retreino de todos os modelos preditivos do projeto.

Ordem recomendada (dados → in-play → pré-jogo → palpites → avaliação):

1. Sincronizar placares FIFA + Parquet de fixtures
2. Reconciliar apostas reais (carteira → silver)
3. Hawkes in-play
4. Coeficientes momentum/NHPP
5. GBM in-play (walk-forward)
6. GBM com feedback das apostas reais
7. Predictor WC pré-jogo (ensemble Dixon-Coles + logística + KXL)
8. Palpites para jogos sem placar (sem vazamento temporal)
9. Benchmark in-play (opcional)
10. Walk-forward histórico WC (opcional)
11. LM bolão Brasileirão (opcional; requer GPU/Unsloth)

CLI: ``retrain-all-models``
Shell: ``./scripts/retrain-all-models.sh``
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from config import settings
from pipelines.retrain_wc_today import (
    DEFAULT_ROUND,
    predict_upcoming_matches,
    retrain_inplay_models,
    retrain_pregame_predictor,
    sync_training_data,
)
from pipelines.wc_full_improvement import _inventory, _step_reconcile

log = structlog.get_logger()


@dataclass
class RetrainAllReport:
    started_at: str
    inventory: dict[str, Any] = field(default_factory=dict)
    data_sync: dict[str, Any] = field(default_factory=dict)
    reconcile: dict[str, Any] = field(default_factory=dict)
    inplay: dict[str, Any] = field(default_factory=dict)
    pregame: dict[str, Any] = field(default_factory=dict)
    predictions: dict[str, Any] | None = None
    benchmark: dict[str, Any] | None = None
    walkforward: dict[str, Any] | None = None
    bolao_lm: dict[str, Any] | None = None
    finished_at: str | None = None
    errors: list[str] = field(default_factory=list)


def _step_benchmark(*, live_only: bool = False) -> dict[str, Any]:
    from pipelines.inplay_benchmark import full_benchmark_report

    return full_benchmark_report(eval_season=2022, live_only=live_only, verbose=False)


def _step_walkforward(*, max_editions: int = 6) -> dict[str, Any]:
    from pipelines.wc_walkforward import run_walkforward

    return run_walkforward(max_editions=max_editions)


def _step_bolao_lm(*, use_unsloth: bool = False) -> dict[str, Any]:
    """Exporta gold → JSONL e treina LM de bolão (lento; opcional)."""
    from models.train import train

    dataset = Path("data/training/bolao_train.jsonl")
    output_dir = Path("models/checkpoints/bolao-unsloth")
    train(
        dataset_path=dataset,
        output_dir=output_dir,
        use_unsloth=use_unsloth,
    )
    return {
        "dataset": str(dataset),
        "output_dir": str(output_dir),
        "use_unsloth": use_unsloth,
    }


def run_retrain_all_models(
    *,
    user_id: str = "jamarorn",
    min_confidence: float = 0.7,
    round_file: Path = DEFAULT_ROUND,
    force_fifa_refresh: bool = True,
    skip_inventory: bool = False,
    skip_data_sync: bool = False,
    skip_reconcile: bool = False,
    skip_inplay: bool = False,
    skip_feedback: bool = False,
    skip_hawkes: bool = False,
    skip_pregame: bool = False,
    skip_predictions: bool = False,
    skip_benchmark: bool = True,
    skip_walkforward: bool = True,
    skip_bolao_lm: bool = True,
    bolao_unsloth: bool = False,
    walkforward_editions: int = 6,
) -> RetrainAllReport:
    """Executa o pipeline completo de retreino."""
    report = RetrainAllReport(started_at=datetime.now(UTC).isoformat())
    total_steps = 7
    if not skip_benchmark:
        total_steps += 1
    if not skip_walkforward:
        total_steps += 1
    if not skip_bolao_lm:
        total_steps += 1

    step = 1

    if not skip_inventory:
        print(f"\n=== {step}/{total_steps} Inventário do lake ===")
        try:
            report.inventory = _inventory()
            print(json.dumps(report.inventory, indent=2, ensure_ascii=False, default=str))
        except Exception as exc:
            log.exception("inventory_failed", error=str(exc))
            report.errors.append(f"inventory: {exc}")
            print(f"AVISO inventário: {exc}")
        step += 1

    if not skip_data_sync:
        print(f"\n=== {step}/{total_steps} Sincronizar dados de treino ===")
        try:
            report.data_sync = sync_training_data(force_fifa_refresh=force_fifa_refresh)
            print(json.dumps(report.data_sync, indent=2, ensure_ascii=False, default=str))
        except Exception as exc:
            log.exception("data_sync_failed", error=str(exc))
            report.errors.append(f"data_sync: {exc}")
            print(f"ERRO sync: {exc}")
        step += 1

    if not skip_reconcile:
        print(f"\n=== {step}/{total_steps} Reconciliar apostas ({user_id}) ===")
        try:
            report.reconcile = _step_reconcile(user_id)
            print(json.dumps(report.reconcile, indent=2, ensure_ascii=False, default=str))
        except Exception as exc:
            log.exception("reconcile_failed", error=str(exc))
            report.errors.append(f"reconcile: {exc}")
            print(f"ERRO reconciliação: {exc}")
        step += 1

    if not skip_inplay:
        print(f"\n=== {step}/{total_steps} Retreino in-play (Hawkes + coefs + GBM + feedback) ===")
        try:
            report.inplay = retrain_inplay_models(
                user_id=user_id,
                min_confidence=min_confidence,
                skip_feedback=skip_feedback,
                skip_hawkes=skip_hawkes,
            )
            print(json.dumps(report.inplay, indent=2, ensure_ascii=False, default=str))
        except Exception as exc:
            log.exception("inplay_retrain_failed", error=str(exc))
            report.errors.append(f"inplay: {exc}")
            print(f"ERRO in-play: {exc}")
        step += 1

    if not skip_pregame:
        print(f"\n=== {step}/{total_steps} Retreino predictor pré-jogo (train-wc) ===")
        try:
            report.pregame = retrain_pregame_predictor()
            print(json.dumps(report.pregame, indent=2, ensure_ascii=False, default=str))
        except Exception as exc:
            log.exception("pregame_retrain_failed", error=str(exc))
            report.errors.append(f"pregame: {exc}")
            print(f"ERRO pré-jogo: {exc}")
        step += 1

    if not skip_predictions:
        print(f"\n=== {step}/{total_steps} Palpites jogos restantes (sem vazamento) ===")
        try:
            report.predictions = predict_upcoming_matches(round_file)
            print(json.dumps(report.predictions, indent=2, ensure_ascii=False, default=str))
        except Exception as exc:
            log.exception("predictions_failed", error=str(exc))
            report.errors.append(f"predictions: {exc}")
            print(f"ERRO palpites: {exc}")
        step += 1

    if not skip_benchmark:
        print(f"\n=== {step}/{total_steps} Benchmark in-play ===")
        try:
            report.benchmark = _step_benchmark(live_only=False)
            lt = report.benchmark.get("live_ticks", {})
            if lt.get("brier_modelo"):
                print(f"  Brier live ticks: {lt['brier_modelo']:.4f}")
            print(json.dumps(report.benchmark, indent=2, ensure_ascii=False, default=str))
        except Exception as exc:
            log.exception("benchmark_failed", error=str(exc))
            report.errors.append(f"benchmark: {exc}")
            print(f"ERRO benchmark: {exc}")
        step += 1

    if not skip_walkforward:
        print(f"\n=== {step}/{total_steps} Walk-forward WC ({walkforward_editions} edições) ===")
        try:
            report.walkforward = _step_walkforward(max_editions=walkforward_editions)
            print(json.dumps(report.walkforward, indent=2, ensure_ascii=False, default=str))
        except Exception as exc:
            log.exception("walkforward_failed", error=str(exc))
            report.errors.append(f"walkforward: {exc}")
            print(f"ERRO walkforward: {exc}")
        step += 1

    if not skip_bolao_lm:
        print(f"\n=== {step}/{total_steps} Treino LM bolão Brasileirão ===")
        try:
            report.bolao_lm = _step_bolao_lm(use_unsloth=bolao_unsloth)
            print(json.dumps(report.bolao_lm, indent=2, ensure_ascii=False, default=str))
        except Exception as exc:
            log.exception("bolao_lm_failed", error=str(exc))
            report.errors.append(f"bolao_lm: {exc}")
            print(f"ERRO bolão LM: {exc}")

    report.finished_at = datetime.now(UTC).isoformat()
    out_dir = settings.lake_root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = out_dir / f"retrain_all_models_{ts}.json"
    report_path.write_text(
        json.dumps(asdict(report), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print(f"\nRelatório: {report_path}")
    if report.errors:
        print(f"Concluído com {len(report.errors)} erro(s).")
        for err in report.errors:
            print(f"  - {err}")
    else:
        print("Retreino completo. Reinicie a API para carregar os novos artefatos.")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Retreina todos os modelos (WC pré-jogo, in-play, feedback, palpites)"
    )
    parser.add_argument("--user", default="jamarorn", help="user_id da carteira Superbet")
    parser.add_argument("--min-confidence", type=float, default=0.7)
    parser.add_argument("--round-file", type=Path, default=DEFAULT_ROUND)
    parser.add_argument("--no-fifa-refresh", action="store_true", help="Usa cache FIFA local")

    parser.add_argument("--skip-inventory", action="store_true")
    parser.add_argument("--skip-data-sync", action="store_true")
    parser.add_argument("--skip-reconcile", action="store_true")
    parser.add_argument("--skip-inplay", action="store_true", help="Pula Hawkes, coefs, GBM e feedback")
    parser.add_argument("--skip-feedback", action="store_true")
    parser.add_argument("--skip-hawkes", action="store_true")
    parser.add_argument("--skip-pregame", action="store_true", help="Pula train-wc (~5–15 min)")
    parser.add_argument("--skip-predictions", action="store_true")

    parser.add_argument(
        "--with-benchmark",
        action="store_true",
        help="Roda benchmark in-play ao final (~2–5 min)",
    )
    parser.add_argument(
        "--with-walkforward",
        action="store_true",
        help="Roda walk-forward histórico WC (~10–20 min)",
    )
    parser.add_argument("--walkforward-editions", type=int, default=6)
    parser.add_argument(
        "--with-bolao-lm",
        action="store_true",
        help="Treina LM bolão (lento; use --bolao-unsloth se tiver GPU)",
    )
    parser.add_argument("--bolao-unsloth", action="store_true")

    args = parser.parse_args()

    report = run_retrain_all_models(
        user_id=args.user,
        min_confidence=args.min_confidence,
        round_file=args.round_file,
        force_fifa_refresh=not args.no_fifa_refresh,
        skip_inventory=args.skip_inventory,
        skip_data_sync=args.skip_data_sync,
        skip_reconcile=args.skip_reconcile,
        skip_inplay=args.skip_inplay,
        skip_feedback=args.skip_feedback,
        skip_hawkes=args.skip_hawkes,
        skip_pregame=args.skip_pregame,
        skip_predictions=args.skip_predictions,
        skip_benchmark=not args.with_benchmark,
        skip_walkforward=not args.with_walkforward,
        skip_bolao_lm=not args.with_bolao_lm,
        bolao_unsloth=args.bolao_unsloth,
        walkforward_editions=args.walkforward_editions,
    )
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
