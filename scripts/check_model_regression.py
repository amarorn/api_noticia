#!/usr/bin/env python3
"""Gate de regressão do modelo in-play (Workstream 1).

Compara métricas recentes contra baseline congelado e média móvel 7d.
Exit 0 = OK; exit 1 = regressão detectada.

Uso:
  python scripts/check_model_regression.py
  python scripts/check_model_regression.py --report path/to/inplay_daily.json
  python scripts/check_model_regression.py --simulate-degrade 0.06
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings  # noqa: E402

REPORTS_DIR = settings.lake_root / "reports"
METRICS_HISTORY_PATH = settings.lake_root / "metrics_history.parquet"
BASELINE_PATH = REPORTS_DIR / "inplay_baseline.json"

DEFAULT_MAX_BRIER_DEGRADATION = 0.05
DEFAULT_MIN_GBM_AVAILABILITY = 90.0
DEFAULT_ROLLING_DAYS = 7


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_daily_report() -> Path | None:
    candidates = sorted(REPORTS_DIR.glob("inplay_daily_*.json"))
    return candidates[-1] if candidates else None


def _load_report(path: Path | None) -> dict:
    target = path or _latest_daily_report()
    if target is None or not target.is_file():
        raise FileNotFoundError(
            f"Nenhum relatório diário em {REPORTS_DIR}. Rode: inplay-daily-report"
        )
    return _load_json(target)


def _rolling_mean_brier(*, exclude_date: str | None, days: int) -> float | None:
    if not METRICS_HISTORY_PATH.is_file():
        return None
    import pandas as pd

    df = pd.read_parquet(METRICS_HISTORY_PATH)
    if df.empty or "brier_modelo" not in df.columns:
        return None
    df = df.dropna(subset=["brier_modelo"]).copy()
    if exclude_date is not None:
        df = df[df["report_date"].astype(str) != str(exclude_date)]
    if df.empty:
        return None
    df = df.sort_values("report_date").tail(days)
    if df.empty:
        return None
    return float(df["brier_modelo"].mean())


def check_regression(
    report: dict,
    *,
    max_brier_degradation: float = DEFAULT_MAX_BRIER_DEGRADATION,
    min_gbm_availability: float = DEFAULT_MIN_GBM_AVAILABILITY,
    rolling_days: int = DEFAULT_ROLLING_DAYS,
    simulate_degrade: float | None = None,
) -> tuple[bool, list[str]]:
    """Retorna (ok, mensagens)."""
    messages: list[str] = []
    failures: list[str] = []

    summary = report.get("summary") or {}
    brier = summary.get("brier_modelo")
    gbm = summary.get("gbm_availability_pct")
    report_date = str(report.get("report_date", ""))

    if brier is None:
        messages.append("Aviso: brier_modelo ausente (sem ticks finalizados?) — gate de Brier ignorado.")
    else:
        brier_val = float(brier)
        if simulate_degrade is not None:
            brier_val = brier_val * (1.0 + simulate_degrade)
            messages.append(f"Simulação: brier ajustado para {brier_val:.5f} (+{simulate_degrade:.0%})")

        refs: list[tuple[str, float]] = []
        if BASELINE_PATH.is_file():
            baseline = _load_json(BASELINE_PATH)
            base_brier = baseline.get("brier_modelo")
            if base_brier is not None:
                refs.append(("baseline", float(base_brier)))

        rolling = _rolling_mean_brier(exclude_date=report_date, days=rolling_days)
        if rolling is not None:
            refs.append((f"média_{rolling_days}d", rolling))

        for label, ref in refs:
            if ref <= 0:
                continue
            rel = (brier_val - ref) / ref
            messages.append(f"Brier {brier_val:.5f} vs {label} {ref:.5f} (Δ {rel:+.1%})")
            if rel > max_brier_degradation:
                failures.append(
                    f"Brier piorou {rel:.1%} vs {label} (limite +{max_brier_degradation:.0%})"
                )

        for bucket, vals in (report.get("live_ticks") or {}).get("brier_by_minute_bucket", {}).items():
            if not isinstance(vals, dict):
                continue
            b = vals.get("brier")
            n = vals.get("n") or 0
            if b is None or n < 10 or rolling is None:
                continue
            rel_bucket = (float(b) - rolling) / rolling
            if rel_bucket > max_brier_degradation:
                failures.append(
                    f"Bucket {bucket}: Brier {float(b):.5f} pior que média {rolling:.5f} "
                    f"(+{rel_bucket:.1%})"
                )

    if gbm is not None:
        gbm_val = float(gbm)
        messages.append(f"GBM availability: {gbm_val:.1f}%")
        if gbm_val == 0.0:
            messages.append(
                "Aviso: GBM não instrumentado nos ticks (ens_prob_l1_delta vazio) — gate GBM ignorado"
            )
        elif gbm_val < min_gbm_availability:
            failures.append(
                f"GBM availability {gbm_val:.1f}% < mínimo {min_gbm_availability:.0f}%"
            )
    else:
        messages.append("GBM availability: N/A (coluna ens_prob_l1_delta ausente nos ticks)")

    staleness = summary.get("staleness_pct")
    if staleness is not None and float(staleness) > 5.0:
        messages.append(f"Aviso: staleness {float(staleness):.1f}% > 5%")

    ok = len(failures) == 0
    if failures:
        messages.extend([f"FALHA: {f}" for f in failures])
    else:
        messages.append("OK: nenhuma regressão detectada.")
    return ok, messages


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate de regressão in-play")
    parser.add_argument("--report", type=Path, help="JSON do inplay-daily-report")
    parser.add_argument(
        "--max-brier-degradation",
        type=float,
        default=DEFAULT_MAX_BRIER_DEGRADATION,
        help="Degradação relativa máxima do Brier (padrão 0.05 = 5%%)",
    )
    parser.add_argument(
        "--min-gbm-availability",
        type=float,
        default=DEFAULT_MIN_GBM_AVAILABILITY,
        help="Disponibilidade mínima do GBM nos ticks (%%)",
    )
    parser.add_argument(
        "--simulate-degrade",
        type=float,
        default=None,
        metavar="FRAC",
        help="Simula piora artificial do Brier (ex.: 0.06 = +6%%) para testar o gate",
    )
    parser.add_argument("--json", action="store_true", help="Saída JSON")
    args = parser.parse_args()

    try:
        report = _load_report(args.report)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    ok, messages = check_regression(
        report,
        max_brier_degradation=args.max_brier_degradation,
        min_gbm_availability=args.min_gbm_availability,
        simulate_degrade=args.simulate_degrade,
    )

    payload = {
        "ok": ok,
        "report_date": report.get("report_date"),
        "messages": messages,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for line in messages:
            print(line)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
