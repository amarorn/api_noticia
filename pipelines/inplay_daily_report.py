"""Relatório diário de validação in-play (Workstream 1).

Orquestra benchmarks existentes, persiste JSON diário e append em
``metrics_history.parquet`` para drift/regressão.

CLI: inplay-daily-report [--date YYYY-MM-DD] [--user-id ID] [--json]
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from config import settings
from pipelines.inplay_benchmark import (
    compute_reconciliation_metrics,
    full_benchmark_report,
)
from pipelines.user_bet_analytics import compute_wallet_summary
from pipelines.wc_inplay_brier_benchmark import run_brier_benchmark

REPORTS_DIR = settings.lake_root / "reports"
METRICS_HISTORY_PATH = settings.lake_root / "metrics_history.parquet"
BASELINE_PATH = REPORTS_DIR / "inplay_baseline.json"


def _report_path_for(day: date) -> Path:
    return REPORTS_DIR / f"inplay_daily_{day.strftime('%Y%m%d')}.json"


def _load_live_ticks() -> pd.DataFrame:
    from ingest.superbet.live_ticks import live_ticks_path

    path = live_ticks_path()
    if not path.is_file():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    if "captured_at" in df.columns:
        df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True, errors="coerce")
    return df


def compute_operational_metrics(*, lookback_hours: int = 24) -> dict[str, Any]:
    """Métricas operacionais a partir dos ticks recentes."""
    df = _load_live_ticks()
    if df.empty:
        return {
            "n_ticks_total": 0,
            "n_ticks_recent": 0,
            "staleness_pct": None,
            "sofascore_coverage_pct": None,
            "gbm_availability_pct": None,
            "avg_lambda_delta_pct": None,
        }

    recent = df
    if "captured_at" in df.columns and df["captured_at"].notna().any():
        cutoff = datetime.now(UTC) - timedelta(hours=lookback_hours)
        recent = df[df["captured_at"] >= cutoff]
        if recent.empty:
            recent = df.tail(500)

    n = len(recent)
    prob_cols = ["prob_final_home", "prob_final_draw", "prob_final_away"]
    has_probs = recent[prob_cols].notna().all(axis=1) if all(c in recent.columns for c in prob_cols) else pd.Series([False] * n)
    stale_pct = round(float((~has_probs).mean()) * 100, 2) if n else None

    if "n_sofascore_events" in recent.columns:
        cov = recent["n_sofascore_events"].fillna(0) > 0
    elif "home_xg" in recent.columns:
        cov = recent["home_xg"].notna() | recent["away_xg"].notna()
    else:
        cov = pd.Series([False] * n)
    sofascore_pct = round(float(cov.mean()) * 100, 2) if n else None

    if "ens_prob_l1_delta" in recent.columns:
        gbm = recent["ens_prob_l1_delta"].notna()
        gbm_pct = round(float(gbm.mean()) * 100, 2) if n else None
    else:
        gbm_pct = None

    lam_delta = None
    if "ens_prob_l1_delta" in recent.columns and gbm.any():
        lam_delta = round(float(recent.loc[gbm, "ens_prob_l1_delta"].abs().mean()) * 100, 2)

    return {
        "n_ticks_total": int(len(df)),
        "n_ticks_recent": int(n),
        "lookback_hours": lookback_hours,
        "staleness_pct": stale_pct,
        "sofascore_coverage_pct": sofascore_pct,
        "gbm_availability_pct": gbm_pct,
        "avg_lambda_delta_pct": lam_delta,
    }


def compute_wallet_hit_pnl(user_id: str) -> dict[str, Any]:
    """Hit rate e P&L da carteira (transações CSV + reconciliação modelo)."""
    wallet = compute_wallet_summary(user_id)
    recon = compute_reconciliation_metrics(user_id=user_id)
    return {
        "user_id": user_id,
        "wallet_hit_rate": wallet.get("hit_rate"),
        "wallet_pnl": wallet.get("pnl"),
        "wallet_roi": wallet.get("roi"),
        "wallet_n_bets": wallet.get("n_bets_placed"),
        "recon_hit_rate": recon.get("hit_rate"),
        "recon_pnl": recon.get("pnl"),
        "recon_n_bets": recon.get("n_bets"),
        "recon_brier_avg": recon.get("brier_avg"),
        "recon_error": recon.get("error"),
    }


def build_daily_report(
    *,
    report_date: date | None = None,
    user_id: str = "jamarorn",
    include_ab_momentum: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """Monta relatório consolidado do dia."""
    day = report_date or datetime.now(UTC).date()
    ts = datetime.now(UTC).isoformat()

    inplay = full_benchmark_report(
        live_only=True,
        verbose=verbose,
        ab_momentum=include_ab_momentum,
        include_ticks_summary=True,
    )
    brier_stratified = run_brier_benchmark(verbose=False)
    operational = compute_operational_metrics()
    wallet = compute_wallet_hit_pnl(user_id)

    live = inplay.get("live_ticks") or {}
    ticks_ds = inplay.get("ticks_dataset") or {}
    brier_configs = brier_stratified.get("configs") or []
    baseline_cfg = next((c for c in brier_configs if c.get("config_name") == "baseline"), None)

    report: dict[str, Any] = {
        "schema_version": 1,
        "report_date": str(day),
        "generated_at": ts,
        "user_id": user_id,
        "live_ticks": live,
        "ticks_dataset": ticks_ds,
        "brier_stratified": brier_stratified,
        "operational": operational,
        "wallet": wallet,
        "reconciliation": inplay.get("reconciliation"),
        "summary": {
            "brier_modelo": live.get("brier_modelo"),
            "brier_mercado": live.get("brier_mercado"),
            "delta_brier": live.get("delta_brier"),
            "brier_stratified_baseline": baseline_cfg.get("brier_overall") if baseline_cfg else None,
            "n_events": live.get("n_events"),
            "n_ticks": live.get("n_ticks"),
            "hit_rate_wallet": wallet.get("wallet_hit_rate"),
            "pnl_wallet": wallet.get("wallet_pnl"),
            "hit_rate_recon": wallet.get("recon_hit_rate"),
            "gbm_availability_pct": operational.get("gbm_availability_pct"),
            "staleness_pct": operational.get("staleness_pct"),
        },
    }
    return report


def _metrics_row_from_report(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") or {}
    op = report.get("operational") or {}
    wallet = report.get("wallet") or {}
    live = report.get("live_ticks") or {}
    brier_buckets = live.get("brier_by_minute_bucket") or {}

    row: dict[str, Any] = {
        "report_kind": "daily",
        "report_date": report.get("report_date"),
        "generated_at": report.get("generated_at"),
        "brier_modelo": summary.get("brier_modelo"),
        "brier_mercado": summary.get("brier_mercado"),
        "delta_brier": summary.get("delta_brier"),
        "brier_stratified_baseline": summary.get("brier_stratified_baseline"),
        "n_events": summary.get("n_events"),
        "n_ticks": summary.get("n_ticks"),
        "accuracy_modelo": live.get("accuracy_modelo"),
        "hit_rate_wallet": wallet.get("wallet_hit_rate"),
        "pnl_wallet": wallet.get("wallet_pnl"),
        "roi_wallet": wallet.get("wallet_roi"),
        "hit_rate_recon": wallet.get("recon_hit_rate"),
        "pnl_recon": wallet.get("recon_pnl"),
        "gbm_availability_pct": op.get("gbm_availability_pct"),
        "staleness_pct": op.get("staleness_pct"),
        "sofascore_coverage_pct": op.get("sofascore_coverage_pct"),
        "brier_buckets_json": json.dumps(brier_buckets, ensure_ascii=False),
    }
    for bucket in ("0-15", "15-30", "30-45", "45-60", "60-75", "75-90", "90+"):
        vals = brier_buckets.get(bucket) or {}
        row[f"brier_{bucket.replace('-', '_')}"] = vals.get("brier")
    return row


def append_metrics_row(row: dict[str, Any], *, dedupe_col: str = "report_date") -> Path:
    """Append ou substitui linha em metrics_history.parquet."""
    kind = row.get("report_kind", "daily")
    dedupe_val = str(row.get(dedupe_col, ""))
    new_df = pd.DataFrame([row])
    METRICS_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    if METRICS_HISTORY_PATH.is_file():
        existing = pd.read_parquet(METRICS_HISTORY_PATH)
        if "report_kind" not in existing.columns:
            existing["report_kind"] = "daily"
        mask = existing[dedupe_col].astype(str) == dedupe_val
        if "report_kind" in row:
            mask &= existing["report_kind"].astype(str) == str(kind)
        existing = existing[~mask]
        out = pd.concat([existing, new_df], ignore_index=True)
    else:
        out = new_df

    out = out.sort_values(["report_kind", dedupe_col]).reset_index(drop=True)
    out.to_parquet(METRICS_HISTORY_PATH, index=False)
    return METRICS_HISTORY_PATH


def append_metrics_history(report: dict[str, Any]) -> Path:
    """Append uma linha diária em metrics_history.parquet (dedupe por report_date)."""
    return append_metrics_row(_metrics_row_from_report(report))


def save_daily_report(report: dict[str, Any], *, overwrite: bool = True) -> Path:
    """Grava JSON diário em data/lake/reports/."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = _report_path_for(date.fromisoformat(str(report["report_date"])))
    if path.exists() and not overwrite:
        return path
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def seed_baseline_if_missing(report: dict[str, Any], *, min_ticks: int = 50) -> bool:
    """Congela baseline na primeira execução com dados suficientes."""
    if BASELINE_PATH.is_file():
        return False
    summary = report.get("summary") or {}
    n_ticks = summary.get("n_ticks") or 0
    brier = summary.get("brier_modelo")
    if n_ticks < min_ticks or brier is None:
        return False
    payload = {
        "created_at": report.get("generated_at"),
        "report_date": report.get("report_date"),
        "brier_modelo": brier,
        "brier_mercado": summary.get("brier_mercado"),
        "gbm_availability_pct": summary.get("gbm_availability_pct"),
        "note": "Baseline congelado automaticamente na primeira execução com dados suficientes.",
    }
    BASELINE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def run_daily_report(
    *,
    report_date: date | None = None,
    user_id: str = "jamarorn",
    verbose: bool = False,
    write_json: bool = True,
    append_history: bool = True,
) -> dict[str, Any]:
    """Executa pipeline completo e persiste artefatos."""
    report = build_daily_report(
        report_date=report_date,
        user_id=user_id,
        verbose=verbose,
    )
    if write_json:
        save_daily_report(report)
    if append_history:
        append_metrics_history(report)
    seed_baseline_if_missing(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Relatório diário de validação in-play")
    parser.add_argument("--date", type=str, help="Data do relatório (YYYY-MM-DD, padrão: hoje UTC)")
    parser.add_argument("--user-id", default="jamarorn", help="Usuário para P&L / reconciliação")
    parser.add_argument("--json", action="store_true", help="Imprimir relatório em JSON")
    parser.add_argument("--quiet", action="store_true", help="Sem logs humanos")
    parser.add_argument("--no-history", action="store_true", help="Não append em metrics_history.parquet")
    parser.add_argument("--ab-momentum", action="store_true", help="Inclui A/B momentum (mais lento)")
    args = parser.parse_args()

    report_day = date.fromisoformat(args.date) if args.date else None
    verbose = not args.quiet and not args.json

    report = build_daily_report(
        report_date=report_day,
        user_id=args.user_id,
        include_ab_momentum=args.ab_momentum,
        verbose=verbose,
    )
    save_daily_report(report)
    if not args.no_history:
        append_metrics_history(report)
    seeded = seed_baseline_if_missing(report)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    elif not args.quiet:
        s = report.get("summary") or {}
        print(f"Relatório: {_report_path_for(date.fromisoformat(str(report['report_date'])))}")
        print(f"  Brier modelo: {s.get('brier_modelo')} | ticks: {s.get('n_ticks')} | eventos: {s.get('n_events')}")
        print(f"  Histórico: {METRICS_HISTORY_PATH}")
        if seeded:
            print(f"  Baseline congelado: {BASELINE_PATH}")

    live_err = (report.get("live_ticks") or {}).get("error")
    if live_err and (report.get("summary") or {}).get("n_ticks", 0) == 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
