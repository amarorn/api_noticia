"""Validação Fase 4: feedback loop aposta-modelo.

CLI: validate-inplay-phase4 [--user jamarorn] [--csv path.csv]
"""
from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from ingest.user_transactions.parser import parse_user_csv_file
from ingest.user_transactions.store import save_transactions_bronze
from pipelines.feedback_retrain import retrain_with_feedback
from pipelines.inplay_benchmark import compute_reconciliation_metrics
from pipelines.user_bet_analytics import compute_model_errors_heatmap, compute_wallet_summary
from pipelines.user_bet_reconciliation import (
    reconcile_user_transactions,
    save_reconciliation,
)


def run_phase4_validation(
    user_id: str = "default",
    *,
    csv_path: Path | None = None,
    run_retrain: bool = False,
    verbose: bool = True,
) -> dict:
    """Valida pipeline Fase 4: upload → reconcile → analytics → retreino opcional."""
    report: dict = {"user_id": user_id, "steps": {}}

    if csv_path is not None:
        if not csv_path.exists():
            report["error"] = f"CSV não encontrado: {csv_path}"
            return report
        upload_id = str(uuid.uuid4())
        rows = parse_user_csv_file(csv_path, user_id, upload_id)
        if not rows:
            report["error"] = "CSV sem linhas válidas"
            return report
        out = save_transactions_bronze(rows, user_id, upload_id)
        report["steps"]["upload"] = {
            "n_rows": len(rows),
            "n_inplay_placed": sum(1 for r in rows if r.is_inplay_bet and r.is_bet_placed),
            "path": str(out),
        }
        if verbose:
            print(f"  Upload: {len(rows)} linhas → {out}")

    summary = compute_wallet_summary(user_id)
    report["steps"]["wallet_summary"] = {
        "n_transactions": summary.get("n_transactions", 0),
        "n_bets_placed": summary.get("n_bets_placed", 0),
        "pnl": summary.get("pnl", 0),
    }
    if verbose:
        print(
            f"  Carteira: {summary.get('n_bets_placed', 0)} apostas, "
            f"P&L={summary.get('pnl', 0):.2f}"
        )

    if summary.get("n_bets_placed", 0) == 0:
        report["status"] = "skipped_no_transactions"
        if verbose:
            print("  ⚠️  Sem transações — faça upload do CSV Superbet")
        return report

    df = reconcile_user_transactions(user_id)
    if df.empty:
        report["status"] = "reconcile_empty"
        return report

    recon_path = save_reconciliation(df, user_id)
    metrics = compute_reconciliation_metrics(user_id)
    heatmap = compute_model_errors_heatmap(user_id)

    report["steps"]["reconciliation"] = {
        "n_pairs": len(df),
        "path": str(recon_path),
        **metrics,
    }
    report["steps"]["model_errors"] = {
        "n_buckets": len(heatmap.get("buckets", [])),
        "n_total_bets": heatmap.get("n_total_bets", 0),
    }

    if verbose:
        print(
            f"  Reconciliação: {metrics.get('n_matched', 0)}/{metrics.get('n_bets', 0)} "
            f"matched ({metrics.get('match_rate', 0):.1%}), "
            f"high_conf={metrics.get('high_confidence_rate', 0):.1%}"
        )
        if metrics.get("brier_avg") is not None:
            print(f"  Brier médio (proxy): {metrics['brier_avg']:.4f}")

    target_met = metrics.get("high_confidence_rate", 0) >= 0.6
    report["target_high_confidence_60pct"] = target_met

    if run_retrain:
        retrain = retrain_with_feedback(user_id=user_id)
        report["steps"]["retrain"] = {
            "n_feedback": retrain.n_feedback_examples,
            "brier_old": retrain.brier_old,
            "brier_new": retrain.brier_new,
            "accepted": retrain.accepted,
        }
        if verbose:
            print(
                f"  Retreino: feedback={retrain.n_feedback_examples} "
                f"accepted={retrain.accepted}"
            )

    report["status"] = "ok"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validação Fase 4 (feedback loop)")
    parser.add_argument("--user", default="default", help="user_id")
    parser.add_argument("--csv", type=Path, help="CSV Superbet para upload antes da validação")
    parser.add_argument("--retrain", action="store_true", help="tenta retrain-with-feedback")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    verbose = not args.json
    if verbose:
        print("=== VALIDAÇÃO FASE 4 — FEEDBACK LOOP ===")

    report = run_phase4_validation(
        args.user,
        csv_path=args.csv,
        run_retrain=args.retrain,
        verbose=verbose,
    )

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
