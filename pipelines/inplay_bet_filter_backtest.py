"""Backtest dos filtros de minuto/EV sobre apostas reconciliadas."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from config import settings


@dataclass
class FilterScenario:
    name: str
    label: str
    n_bets: int
    hit_rate: float | None
    pnl: float | None
    excluded: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _scenario_mask(minute: pd.Series, name: str) -> pd.Series:
    m = minute.fillna(-1)
    if name == "baseline":
        return pd.Series(True, index=minute.index)
    if name == "block_late":
        return m < settings.live_block_minute
    if name == "block_midgame":
        return m < settings.live_midgame_strict_minute
    if name == "only_first_half":
        return (m >= 0) & (m < 30)
    raise ValueError(f"Cenário desconhecido: {name}")


def backtest_minute_filters(user_id: str) -> dict[str, Any]:
    """Simula hit rate/P&L se só apostasse em janelas permitidas pelos filtros."""
    from pipelines.user_bet_reconciliation import load_reconciliation

    df = load_reconciliation(user_id)
    if df is None or df.empty:
        return {"user_id": user_id, "scenarios": [], "note": "reconciliação vazia"}

    matched = df[df["match_minute"].notna()].copy()
    scenarios: list[FilterScenario] = []
    scenario_names = ("baseline", "block_midgame", "block_late", "only_first_half")

    labels = {
        "baseline": "Todas reconciliadas (com minuto)",
        "block_midgame": f"Excluir ≥{settings.live_midgame_strict_minute}'",
        "block_late": f"Excluir ≥{settings.live_block_minute}'",
        "only_first_half": "Só 0–30'",
    }

    for name in scenario_names:
        mask = _scenario_mask(matched["match_minute"], name)
        sub = matched[mask]
        hit = float(sub["won"].mean()) if len(sub) and "won" in sub.columns else None
        pnl = float(sub["pnl"].fillna(0).sum()) if len(sub) and "pnl" in sub.columns else None
        scenarios.append(
            FilterScenario(
                name=name,
                label=labels[name],
                n_bets=int(len(sub)),
                hit_rate=round(hit, 4) if hit is not None else None,
                pnl=round(pnl, 2) if pnl is not None else None,
                excluded=int(len(matched) - len(sub)),
            )
        )

    baseline = next(s for s in scenarios if s.name == "baseline")
    best = max(
        (s for s in scenarios if s.name != "baseline" and s.hit_rate is not None),
        key=lambda s: s.hit_rate or 0,
        default=None,
    )

    return {
        "user_id": user_id,
        "n_reconciled": int(len(df)),
        "n_with_minute": int(len(matched)),
        "recommended_filter": "block_midgame",
        "baseline_hit_rate": baseline.hit_rate,
        "best_filter_hit_rate": best.hit_rate if best else None,
        "hit_rate_delta_pp": round((best.hit_rate - baseline.hit_rate) * 100, 1)
        if best and baseline.hit_rate is not None and best.hit_rate is not None
        else None,
        "scenarios": [s.to_dict() for s in scenarios],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest filtros in-play (minuto).")
    parser.add_argument("--user", default=settings.superbet_finalize_user_id)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = backtest_minute_filters(args.user)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Reconciliadas com minuto: {report['n_with_minute']}")
        for s in report["scenarios"]:
            print(
                f"  {s['label']}: n={s['n_bets']} hit={s['hit_rate']} "
                f"pnl={s['pnl']} (-{s['excluded']})"
            )
        if report.get("hit_rate_delta_pp") is not None:
            print(f"  Δ hit vs baseline: +{report['hit_rate_delta_pp']} pp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
