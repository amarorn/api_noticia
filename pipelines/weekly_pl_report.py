"""Relatório semanal: P&L operacional vs Brier do modelo (Fase D)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from config import settings
from ingest.user_transactions.wallet_inbox import get_wallet_sync_status
from pipelines.model_benchmark_history import load_history
from pipelines.user_bet_analytics import compute_wallet_summary

REPORTS_DIR = settings.lake_root / "reports"


def _load_reconciliation_stats(user_id: str) -> dict[str, Any]:
    try:
        import pandas as pd

        from pipelines.user_bet_reconciliation import load_reconciliation

        df = load_reconciliation(user_id)
        if df is None or df.empty:
            return {"n_pairs": 0}
        conf = df["match_confidence"].fillna(0)
        brier = df["brier_contribution"].dropna()
        return {
            "n_pairs": int(len(df)),
            "n_high_confidence": int((conf >= 0.7).sum()),
            "match_rate_0_5": round(float((conf >= 0.5).mean()), 3),
            "brier_avg": round(float(brier.mean()), 4) if len(brier) else None,
            "pnl_reconciled": round(float(df["pnl"].fillna(0).sum()), 2),
            "hit_rate": round(float(df["won"].mean()), 3) if "won" in df.columns else None,
        }
    except Exception as exc:
        return {"error": str(exc)}


def _latest_benchmark() -> dict[str, Any]:
    history = load_history()
    snapshots = history.get("snapshots") or []
    if not snapshots:
        return {}
    latest = snapshots[-1]
    metrics = latest.get("metrics") or {}
    return {
        "run_id": latest.get("run_id"),
        "timestamp": latest.get("timestamp"),
        "wc_brier": (metrics.get("wc_pregame") or {}).get("benchmark_brier"),
        "inplay_brier_model": (metrics.get("inplay") or {}).get("live_brier_modelo"),
        "inplay_brier_market": (metrics.get("inplay") or {}).get("live_brier_mercado"),
        "inplay_delta": (metrics.get("inplay") or {}).get("live_delta_brier"),
    }


def _week_window(days: int = 7) -> tuple[str, str]:
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    return start.date().isoformat(), end.date().isoformat()


def build_weekly_report(user_id: str, *, days: int = 7) -> dict[str, Any]:
    """Monta relatório semanal operação × modelo."""
    period_start, period_end = _week_window(days)
    wallet = compute_wallet_summary(user_id)
    recon = _load_reconciliation_stats(user_id)
    benchmark = _latest_benchmark()
    sync = get_wallet_sync_status(user_id)

    daily = wallet.get("daily_pnl") or []
    week_rows = [d for d in daily if period_start <= (d.get("date") or "") <= period_end]
    week_pnl = round(sum(d.get("pnl", 0) for d in week_rows), 2)
    week_staked = round(sum(d.get("staked", 0) for d in week_rows), 2)
    week_bets = sum(d.get("n_bets", 0) for d in week_rows)

    model_edge_ok = None
    inplay_delta = benchmark.get("inplay_delta")
    if inplay_delta is not None:
        # Δ negativo = modelo melhor que mercado (Brier menor)
        model_edge_ok = float(inplay_delta) <= -0.015

    filter_backtest: dict[str, Any] = {}
    try:
        from pipelines.inplay_bet_filter_backtest import backtest_minute_filters

        filter_backtest = backtest_minute_filters(user_id)
    except Exception:
        filter_backtest = {}

    draw_picks: dict[str, Any] = {}
    try:
        pred_path = settings.lake_root / "reports" / "wc_2026_predictions_latest.json"
        if pred_path.exists():
            preds = json.loads(pred_path.read_text(encoding="utf-8"))
            if isinstance(preds, list):
                from collections import Counter

                counts = Counter(p.get("prediction") for p in preds)
                draw_picks = {
                    "n_matches": len(preds),
                    "n_draw": int(counts.get("X", 0)),
                    "n_home": int(counts.get("1", 0)),
                    "n_away": int(counts.get("2", 0)),
                }
    except Exception:
        draw_picks = {}

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "user_id": user_id,
        "period": {"start": period_start, "end": period_end, "days": days},
        "operational": {
            "pnl_total": wallet.get("pnl"),
            "roi": wallet.get("roi"),
            "hit_rate": wallet.get("hit_rate"),
            "n_bets_placed": wallet.get("n_bets_placed"),
            "total_staked": wallet.get("total_staked"),
            "week_pnl": week_pnl,
            "week_staked": week_staked,
            "week_bets": week_bets,
        },
        "reconciliation": recon,
        "model": benchmark,
        "wc_draw_picks": draw_picks,
        "filter_backtest": filter_backtest,
        "wallet_sync": {
            "stale": sync.get("stale"),
            "days_since_upload": sync.get("days_since_upload"),
            "n_pending_csv": sync.get("n_pending"),
        },
        "health": {
            "model_beats_market_inplay": model_edge_ok,
            "csv_sync_ok": not sync.get("stale") and sync.get("n_uploads", 0) > 0,
            "reconciliation_on_track": (recon.get("n_high_confidence") or 0) >= 100,
            "filter_improves_hit_rate": (
                (filter_backtest.get("hit_rate_delta_pp") or 0) > 0
                if filter_backtest
                else None
            ),
        },
    }


def save_weekly_report(report: dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d")
    path = REPORTS_DIR / f"weekly_pl_{ts}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    latest = REPORTS_DIR / "weekly_pl_latest.json"
    latest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Relatório semanal P&L vs Brier.")
    parser.add_argument("--user", default=settings.superbet_finalize_user_id)
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    report = build_weekly_report(args.user, days=args.days)
    path = save_weekly_report(report)

    op = report["operational"]
    model = report["model"]
    print(f"Relatório: {path}")
    print(f"  P&L total: R$ {op.get('pnl_total')} | semana: R$ {op.get('week_pnl')}")
    print(f"  Hit rate: {op.get('hit_rate')} | ROI: {op.get('roi')}")
    if model.get("inplay_brier_model") is not None:
        print(
            f"  Brier in-play: modelo {model.get('inplay_brier_model')} "
            f"vs mercado {model.get('inplay_brier_market')} "
            f"(Δ {model.get('inplay_delta')})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
