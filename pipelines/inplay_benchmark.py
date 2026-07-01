"""Benchmark de performance do modelo in-play.

Verifica se o modelo está melhorando comparando:
1. Walk-forward Brier com fixtures históricas (precisão preditiva)
2. Live ticks reais: modelo vs mercado (calibração contra odds)
3. Reconciliação de apostas reais (hit rate + P&L)

CLI: benchmark-inplay [--verbose] [--live-only] [--eval-season 2022]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from config import settings


# ---------------------------------------------------------------------------
# 1. Brier dos live ticks (modelo real vs resultado real)
# ---------------------------------------------------------------------------


def _load_live_ticks() -> pd.DataFrame:
    """Carrega live_ticks.parquet com dados de polls reais."""
    path = settings.bronze_path / "superbet" / "live_ticks.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _find_final_score_from_events(event_id: int) -> dict | None:
    """Compat: delega para pipelines.inplay_event_finals."""
    from pipelines.inplay_event_finals import find_event_final_score

    return find_event_final_score(event_id)


def compute_live_ticks_brier(verbose: bool = False) -> dict:
    """Calcula Brier do modelo nos live ticks reais (onde temos resultado final).

    Para cada tick (event_id, minute), compara prob_final_home/draw/away
    com o resultado real do jogo (1/X/2).
    """
    df = _load_live_ticks()
    if df.empty:
        return {"error": "Sem live_ticks.parquet", "n_ticks": 0}

    # Obter resultados finais por evento
    event_ids = df["event_id"].dropna().unique()
    finals: dict[int, dict] = {}
    for eid in event_ids:
        result = _find_final_score_from_events(int(eid))
        if result:
            finals[int(eid)] = result

    if not finals:
        return {
            "error": "Nenhum evento com resultado final encontrado",
            "n_events": len(event_ids),
            "n_ticks": len(df),
        }

    # Merge com resultado final
    df = df[df["event_id"].isin(finals.keys())].copy()
    df["home_score_final"] = df["event_id"].map(lambda x: finals.get(int(x), {}).get("home_score_final"))
    df["away_score_final"] = df["event_id"].map(lambda x: finals.get(int(x), {}).get("away_score_final"))

    # y_true baseado no resultado final
    df["y_true"] = "X"
    df.loc[df["home_score_final"] > df["away_score_final"], "y_true"] = "1"
    df.loc[df["home_score_final"] < df["away_score_final"], "y_true"] = "2"

    # Filtrar apenas ticks com probabilidades válidas
    prob_cols = ["prob_final_home", "prob_final_draw", "prob_final_away"]
    df = df.dropna(subset=prob_cols)
    if df.empty:
        return {"error": "Ticks sem probabilidades", "n_ticks": 0}

    # Brier score multiclasse
    def brier_row(row):
        p1 = row["prob_final_home"]
        px = row["prob_final_draw"]
        p2 = row["prob_final_away"]
        y = row["y_true"]
        return (
            (p1 - (1.0 if y == "1" else 0.0)) ** 2
            + (px - (1.0 if y == "X" else 0.0)) ** 2
            + (p2 - (1.0 if y == "2" else 0.0)) ** 2
        ) / 3

    df["brier"] = df.apply(brier_row, axis=1)

    # Brier por minuto bucket (0-15, 15-30, 30-45, 45-60, 60-75, 75-90)
    df["minute_bucket"] = pd.cut(
        df["minute"].fillna(0).astype(int),
        bins=[0, 15, 30, 45, 60, 75, 90, 999],
        labels=["0-15", "15-30", "30-45", "45-60", "60-75", "75-90", "90+"],
        include_lowest=True,
    )

    brier_overall = float(df["brier"].mean())
    brier_by_bucket = df.groupby("minute_bucket", observed=True)["brier"].agg(["mean", "count"]).to_dict("index")

    # Calibração: comparar prob modelo vs implied do mercado
    df["market_implied_1"] = 1 / df["h2h_odd_1"].replace(0, np.nan)
    df["market_implied_x"] = 1 / df["h2h_odd_x"].replace(0, np.nan)
    df["market_implied_2"] = 1 / df["h2h_odd_2"].replace(0, np.nan)

    # Brier do mercado (benchmark)
    def brier_market_row(row):
        total = (row.get("market_implied_1") or 0) + (row.get("market_implied_x") or 0) + (row.get("market_implied_2") or 0)
        if total <= 0:
            return np.nan
        p1 = row["market_implied_1"] / total
        px = row["market_implied_x"] / total
        p2 = row["market_implied_2"] / total
        y = row["y_true"]
        return (
            (p1 - (1.0 if y == "1" else 0.0)) ** 2
            + (px - (1.0 if y == "X" else 0.0)) ** 2
            + (p2 - (1.0 if y == "2" else 0.0)) ** 2
        ) / 3

    df["brier_market"] = df.apply(brier_market_row, axis=1)
    brier_market = float(df["brier_market"].dropna().mean()) if df["brier_market"].notna().any() else None

    # Accuracy (modelo acerta o outcome mais provável?)
    df["pred_outcome"] = "X"
    df.loc[
        (df["prob_final_home"] > df["prob_final_draw"]) & (df["prob_final_home"] > df["prob_final_away"]),
        "pred_outcome",
    ] = "1"
    df.loc[
        (df["prob_final_away"] > df["prob_final_draw"]) & (df["prob_final_away"] > df["prob_final_home"]),
        "pred_outcome",
    ] = "2"
    accuracy = float((df["pred_outcome"] == df["y_true"]).mean())

    report = {
        "n_events": len(finals),
        "n_ticks": len(df),
        "brier_modelo": round(brier_overall, 5),
        "brier_mercado": round(brier_market, 5) if brier_market else None,
        "delta_brier": round(brier_overall - brier_market, 5) if brier_market else None,
        "accuracy_modelo": round(accuracy, 4),
        "brier_by_minute_bucket": {
            k: {"brier": round(v["mean"], 5), "n": int(v["count"])}
            for k, v in brier_by_bucket.items()
        },
    }

    if verbose:
        print("\n=== BENCHMARK LIVE TICKS (modelo vs mercado) ===")
        print(f"  Eventos com resultado final: {report['n_events']}")
        print(f"  Ticks avaliados: {report['n_ticks']}")
        print(f"  Brier modelo:  {report['brier_modelo']:.5f}")
        if report["brier_mercado"]:
            print(f"  Brier mercado: {report['brier_mercado']:.5f}")
            delta = report["delta_brier"]
            sinal = "+" if delta > 0 else ""
            status = "PIOR que mercado" if delta > 0 else "MELHOR que mercado"
            print(f"  Delta:         {sinal}{delta:.5f} ({status})")
        print(f"  Accuracy (top outcome): {report['accuracy_modelo']:.1%}")
        print("\n  Brier por bucket de minuto:")
        for bucket, vals in sorted(report["brier_by_minute_bucket"].items()):
            print(f"    {bucket:>5s}: {vals['brier']:.5f} (n={vals['n']})")

    return report


# ---------------------------------------------------------------------------
# 2. Walk-forward com fixtures históricas
# ---------------------------------------------------------------------------


def compute_walkforward_brier(
    eval_season: int = 2022,
    n_simulations: int = 3000,
    verbose: bool = False,
    *,
    use_momentum: bool = True,
    use_calibrated_coefficients: bool | None = None,
) -> dict:
    """Roda walk-forward e retorna Brier overall + por minuto."""
    try:
        from pipelines.wc_inplay_walkforward import evaluate_inplay

        result = evaluate_inplay(
            eval_season=eval_season,
            n_simulations=n_simulations,
            use_momentum=use_momentum,
            use_calibrated_coefficients=use_calibrated_coefficients,
            verbose=verbose,
        )
        return {
            "eval_season": result.eval_season,
            "brier_overall": result.brier_overall,
            "brier_by_minute": result.brier_by_minute,
            "n_samples": result.n_samples,
            "n_games": result.n_games,
            "elapsed_seconds": result.elapsed_seconds,
            "use_momentum": use_momentum,
            "use_calibrated_coefficients": use_calibrated_coefficients,
            "error": result.error,
        }
    except Exception as e:
        return {"error": str(e)}


def compute_ab_momentum_report(
    eval_season: int = 2022,
    n_simulations: int = 2000,
    verbose: bool = False,
) -> dict:
    """Compara walk-forward: sem momentum vs default vs MLE calibrado."""
    scenarios = [
        ("sem_momentum", {"use_momentum": False, "use_calibrated_coefficients": False}),
        ("momentum_default", {"use_momentum": True, "use_calibrated_coefficients": False}),
        ("momentum_calibrado", {"use_momentum": True, "use_calibrated_coefficients": True}),
    ]
    out: dict[str, dict] = {}
    for name, kwargs in scenarios:
        out[name] = compute_walkforward_brier(
            eval_season=eval_season,
            n_simulations=n_simulations,
            verbose=False,
            **kwargs,
        )
    if verbose:
        print("\n=== A/B MOMENTUM (walk-forward fixtures) ===")
        for name, rep in out.items():
            if rep.get("error"):
                print(f"  {name}: ERRO — {rep['error']}")
                continue
            if rep.get("n_samples", 0) == 0:
                print(f"  {name:20s}: sem amostras (walk-forward falhou ou season vazia)")
                continue
            print(
                f"  {name:20s}: Brier={rep.get('brier_overall', 0):.5f} "
                f"(n={rep.get('n_samples', 0)})"
            )
        base = out.get("momentum_default", {}).get("brier_overall")
        cal = out.get("momentum_calibrado", {}).get("brier_overall")
        if base is not None and cal is not None and out.get("momentum_default", {}).get("n_samples"):
            print(f"  Ganho calibrado vs default: {base - cal:+.5f}")
    return out


def compute_ticks_dataset_summary(verbose: bool = False) -> dict:
    """Resume live_ticks disponíveis para calibração MLE."""
    from pipelines.wc_inplay_ticks_dataset import build_timeline_from_live_ticks

    timeline = build_timeline_from_live_ticks()
    if timeline.empty:
        return {"n_snapshots": 0, "n_events": 0, "ready_for_tune": False}
    summary = {
        "n_snapshots": len(timeline),
        "n_events": int(timeline["match_id"].nunique()),
        "minute_range": [
            int(timeline["minute"].min()),
            int(timeline["minute"].max()),
        ],
        "ready_for_tune": len(timeline) >= settings.inplay_tune_min_snapshots,
    }
    if verbose:
        print("\n=== LIVE TICKS (dataset MLE) ===")
        print(f"  Snapshots: {summary['n_snapshots']} | Eventos: {summary['n_events']}")
        print(f"  Minutos: {summary['minute_range'][0]}–{summary['minute_range'][1]}")
        print(
            f"  Pronto p/ tune-inplay --source ticks: "
            f"{'sim' if summary['ready_for_tune'] else 'não'}"
        )
    return summary


# ---------------------------------------------------------------------------
# 3. Reconciliação (se tiver CSV do usuário)
# ---------------------------------------------------------------------------


def compute_reconciliation_metrics(user_id: str = "jamarorn") -> dict:
    """Métricas da reconciliação aposta-modelo do usuário."""
    from pipelines.user_bet_reconciliation import load_reconciliation

    df = load_reconciliation(user_id)
    if df.empty:
        return {"error": "Sem dados de reconciliação (faça upload do CSV na /carteira)"}

    n_total = len(df)
    n_high = int((df["match_confidence"].fillna(0) >= 0.7).sum())
    n_matched = int((df["match_confidence"].fillna(0) >= 0.5).sum())
    match_rate = n_matched / n_total if n_total > 0 else 0
    high_conf_rate = n_high / n_total if n_total > 0 else 0

    matched = df[df["match_confidence"].fillna(0) >= 0.5].copy()
    if matched.empty:
        return {
            "user_id": user_id,
            "n_bets": n_total,
            "n_matched": 0,
            "n_high_confidence": 0,
            "match_rate": 0,
            "high_confidence_rate": 0,
        }

    n_won = int(matched["won"].sum()) if "won" in matched.columns else 0
    hit_rate = n_won / len(matched) if len(matched) > 0 else 0
    pnl = float(matched["won_amount"].sum() - matched["stake"].sum())

    brier_series = matched["brier_contribution"].dropna() if "brier_contribution" in matched.columns else pd.Series(dtype=float)
    brier_avg = float(brier_series.mean()) if not brier_series.empty else None

    return {
        "user_id": user_id,
        "n_bets": n_total,
        "n_matched": n_matched,
        "n_high_confidence": n_high,
        "match_rate": round(match_rate, 3),
        "high_confidence_rate": round(high_conf_rate, 3),
        "hit_rate": round(hit_rate, 3),
        "pnl": round(pnl, 2),
        "brier_avg": round(brier_avg, 5) if brier_avg is not None else None,
    }


# ---------------------------------------------------------------------------
# 4. Relatório consolidado
# ---------------------------------------------------------------------------


def full_benchmark_report(
    eval_season: int = 2022,
    verbose: bool = True,
    live_only: bool = False,
    *,
    ab_momentum: bool = False,
    include_ticks_summary: bool = True,
) -> dict:
    """Relatório completo de performance do modelo in-play.

    Combina:
    - Brier real (live ticks com resultado final)
    - Brier walk-forward (fixtures históricas)
    - Métricas de reconciliação (se disponível)
    """
    report: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Live ticks (sempre roda — é o dado mais real)
    if verbose:
        print("=" * 60)
        print("  BENCHMARK IN-PLAY — PERFORMANCE DO MODELO")
        print("=" * 60)

    report["live_ticks"] = compute_live_ticks_brier(verbose=verbose)

    if include_ticks_summary:
        report["ticks_dataset"] = compute_ticks_dataset_summary(verbose=verbose)

    # Walk-forward (somente se não --live-only)
    if not live_only:
        if verbose:
            print("\n\n=== WALK-FORWARD FIXTURES ===")
        report["walkforward"] = compute_walkforward_brier(
            eval_season=eval_season, verbose=verbose
        )
        if ab_momentum:
            report["ab_momentum"] = compute_ab_momentum_report(
                eval_season=eval_season,
                verbose=verbose,
            )

    # Reconciliação
    recon = compute_reconciliation_metrics()
    if "error" not in recon:
        report["reconciliation"] = recon
        if verbose:
            print("\n\n=== RECONCILIAÇÃO APOSTAS REAIS ===")
            print(f"  Bilhetes: {recon['n_bets']} | Matched: {recon['n_matched']} ({recon['match_rate']:.0%})")
            print(f"  Hit rate: {recon['hit_rate']:.1%}")
            print(f"  P&L: R$ {recon['pnl']:+.2f}")
            if recon.get("brier_avg"):
                print(f"  Brier médio (matched): {recon['brier_avg']:.5f}")

    # Interpretação final
    if verbose:
        print("\n\n" + "=" * 60)
        print("  INTERPRETAÇÃO")
        print("=" * 60)
        lt = report.get("live_ticks", {})
        if lt.get("brier_modelo"):
            brier = lt["brier_modelo"]
            if brier < 0.18:
                print(f"  Brier {brier:.4f} — EXCELENTE (< 0.18)")
            elif brier < 0.22:
                print(f"  Brier {brier:.4f} — BOM (< 0.22)")
            elif brier < 0.25:
                print(f"  Brier {brier:.4f} — RAZOÁVEL (< 0.25)")
            else:
                print(f"  Brier {brier:.4f} — PRECISA MELHORAR (>= 0.25)")

            if lt.get("delta_brier") is not None:
                d = lt["delta_brier"]
                if d < -0.005:
                    print(f"  vs Mercado: {d:+.4f} — Modelo SUPERA o mercado!")
                elif d > 0.005:
                    print(f"  vs Mercado: {d:+.4f} — Mercado ainda é melhor (normal)")
                else:
                    print(f"  vs Mercado: {d:+.4f} — Equiparado ao mercado")
        print()

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark de performance do modelo in-play"
    )
    parser.add_argument("--verbose", "-v", action="store_true", default=True)
    parser.add_argument("--live-only", action="store_true", help="Apenas live ticks (skip walkforward)")
    parser.add_argument("--eval-season", type=int, default=2022, help="Season para walk-forward")
    parser.add_argument(
        "--ab-momentum",
        action="store_true",
        help="Compara walk-forward sem/default/calibrado momentum",
    )
    parser.add_argument(
        "--tune-ticks",
        action="store_true",
        help="Roda tune-inplay --source both e salva coeficientes MLE",
    )
    parser.add_argument("--json", action="store_true", help="Saída em JSON (máquina)")
    args = parser.parse_args()

    verbose = not args.json and args.verbose
    tune_result = None
    if args.tune_ticks:
        from pipelines.wc_inplay_tune import run_inplay_tune

        if verbose:
            print("=== CALIBRAÇÃO MLE (fixtures + live_ticks) ===")
        try:
            coefs = run_inplay_tune(source="both", eval_season=args.eval_season, verbose=verbose)
            tune_result = {
                "n_observations": coefs.n_observations,
                "holdout_brier": coefs.holdout_brier,
                "holdout_brier_baseline": coefs.holdout_brier_baseline,
                "dataset_hash": coefs.dataset_hash,
            }
        except ValueError as exc:
            tune_result = {"error": str(exc)}
            if verbose:
                print(f"  Falha: {exc}")

    report = full_benchmark_report(
        eval_season=args.eval_season,
        verbose=verbose,
        live_only=args.live_only,
        ab_momentum=args.ab_momentum,
    )
    if tune_result is not None:
        report["tune_ticks"] = tune_result

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
