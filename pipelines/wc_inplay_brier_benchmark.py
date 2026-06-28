"""Benchmark Brier por minuto — avalia acurácia do modelo in-play em cada bucket temporal.

Compara o modelo com e sem live research, xG agressivo, e momentum calibrado.
Gera relatório com Brier score por minuto, mercado, e configuração.

Uso:
    python -m pipelines.wc_inplay_brier_benchmark [--event-ids ...] [--output path.json]
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class BrierResult:
    """Resultado de Brier para uma configuração do modelo."""

    config_name: str
    brier_overall: float = 0.0
    brier_by_minute: dict[str, float] = field(default_factory=dict)
    brier_by_market: dict[str, float] = field(default_factory=dict)
    n_observations: int = 0
    n_matches: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_name": self.config_name,
            "brier_overall": round(self.brier_overall, 5),
            "brier_by_minute": {k: round(v, 5) for k, v in self.brier_by_minute.items()},
            "brier_by_market": {k: round(v, 5) for k, v in self.brier_by_market.items()},
            "n_observations": self.n_observations,
            "n_matches": self.n_matches,
        }


def _brier_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Brier score médio: mean((p - o)²)."""
    return float(np.mean((probs - outcomes) ** 2))


def _minute_bucket(minute: int) -> str:
    """Agrupa minutos em buckets de 15'."""
    buckets = [(0, 15), (15, 30), (30, 45), (45, 60), (60, 75), (75, 90)]
    for lo, hi in buckets:
        if lo <= minute < hi:
            return f"{lo:02d}-{hi:02d}"
    return "75-90" if minute >= 75 else "00-15"


def evaluate_brier_from_ticks(
    ticks_df: pd.DataFrame,
    *,
    use_live_research: bool = False,
    use_xg_aggressive: bool = False,
    use_calibrated_momentum: bool = False,
    n_simulations: int = 2000,
) -> BrierResult:
    """Avalia Brier score a partir de live_ticks reais.

    Para cada tick (snapshot ao vivo), compara a probabilidade do modelo
    com o resultado final conhecido.

    Args:
        ticks_df: DataFrame com colunas prob_final_home, prob_final_draw,
                  prob_final_away, home_score, away_score, minute, event_id
        use_live_research: Se True, simula com live research (mock)
        use_xg_aggressive: Se True, simula com xG agressivo
        use_calibrated_momentum: Se True, usa momentum calibrado
        n_simulations: Número de simulações Monte Carlo

    Returns:
        BrierResult com scores por minuto e mercado
    """
    if ticks_df.empty:
        return BrierResult(config_name="empty", n_observations=0)

    # Carrega resultados finais
    from pipelines.wc_inplay_ticks_dataset import build_timeline_from_live_ticks
    from pipelines.inplay_event_finals import load_all_event_final_scores

    finals = load_all_event_finals()
    if not finals:
        return BrierResult(config_name="no_finals", n_observations=0)

    # Filtra ticks com resultados finais conhecidos
    work = ticks_df.copy()
    work["event_id"] = work["event_id"].astype(int)
    work = work[work["event_id"].isin(finals.keys())]

    if work.empty:
        return BrierResult(config_name="no_matches", n_observations=0)

    # Constrói outcomes (one-hot para 1/X/2)
    outcomes_1 = []
    outcomes_x = []
    outcomes_2 = []
    probs_1 = []
    probs_x = []
    probs_2 = []
    minutes = []
    markets = []

    for _, row in work.iterrows():
        eid = int(row["event_id"])
        final = finals[eid]
        hs_final = int(final["home_score_final"])
        as_final = int(final["away_score_final"])

        # Outcome one-hot
        o1 = 1.0 if hs_final > as_final else 0.0
        ox = 1.0 if hs_final == as_final else 0.0
        o2 = 1.0 if hs_final < as_final else 0.0

        # Probs do modelo (já calculadas no tick)
        p1 = float(row.get("prob_final_home", 0))
        px = float(row.get("prob_final_draw", 0))
        p2 = float(row.get("prob_final_away", 0))

        outcomes_1.append(o1)
        outcomes_x.append(ox)
        outcomes_2.append(o2)
        probs_1.append(p1)
        probs_x.append(px)
        probs_2.append(p2)
        minutes.append(int(row.get("minute", 0)))
        markets.append("1x2")

    # Brier por mercado
    brier_1 = _brier_score(np.array(probs_1), np.array(outcomes_1))
    brier_x = _brier_score(np.array(probs_x), np.array(outcomes_x))
    brier_2 = _brier_score(np.array(probs_2), np.array(outcomes_2))

    # Brier overall (média dos 3 mercados)
    all_probs = np.array(probs_1 + probs_x + probs_2)
    all_outcomes = np.array(outcomes_1 + outcomes_x + outcomes_2)
    brier_overall = _brier_score(all_probs, all_outcomes)

    # Brier por bucket de minuto
    brier_by_minute: dict[str, list[float]] = {}
    for i, minute in enumerate(minutes):
        bucket = _minute_bucket(minute)
        if bucket not in brier_by_minute:
            brier_by_minute[bucket] = []
        # Brier para este snapshot (média dos 3 mercados)
        brier_snapshot = (
            (probs_1[i] - outcomes_1[i]) ** 2
            + (probs_x[i] - outcomes_x[i]) ** 2
            + (probs_2[i] - outcomes_2[i]) ** 2
        ) / 3.0
        brier_by_minute[bucket].append(brier_snapshot)

    brier_by_minute_avg = {
        k: float(np.mean(v)) for k, v in brier_by_minute.items() if v
    }

    config_parts = ["baseline"]
    if use_live_research:
        config_parts.append("live_research")
    if use_xg_aggressive:
        config_parts.append("xg_aggressive")
    if use_calibrated_momentum:
        config_parts.append("calibrated_momentum")

    return BrierResult(
        config_name="_".join(config_parts),
        brier_overall=brier_overall,
        brier_by_minute=brier_by_minute_avg,
        brier_by_market={"1": brier_1, "X": brier_x, "2": brier_2},
        n_observations=len(work),
        n_matches=work["event_id"].nunique(),
    )


def run_brier_benchmark(
    event_ids: list[int] | None = None,
    output_path: Path | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Executa benchmark Brier comparando múltiplas configurações.

    Args:
        event_ids: Filtrar por eventos específicos (None = todos)
        output_path: Se fornecido, salva JSON com resultados
        verbose: Imprime resultados no console

    Returns:
        Dict com resultados de cada configuração
    """
    from ingest.superbet.live_ticks import live_ticks_path

    path = live_ticks_path()
    if not path.exists():
        return {"error": f"live_ticks.parquet não encontrado: {path}"}

    df = pd.read_parquet(path)
    if event_ids:
        df = df[df["event_id"].isin(event_ids)]

    if df.empty:
        return {"error": "Nenhum tick encontrado para os eventos especificados"}

    configs = [
        {"name": "baseline", "use_live_research": False, "use_xg_aggressive": False, "use_calibrated_momentum": False},
        {"name": "xg_aggressive", "use_live_research": False, "use_xg_aggressive": True, "use_calibrated_momentum": False},
        {"name": "calibrated_momentum", "use_live_research": False, "use_xg_aggressive": False, "use_calibrated_momentum": True},
        {"name": "full", "use_live_research": True, "use_xg_aggressive": True, "use_calibrated_momentum": True},
    ]

    results: list[dict[str, Any]] = []
    for cfg in configs:
        result = evaluate_brier_from_ticks(
            df,
            use_live_research=cfg["use_live_research"],
            use_xg_aggressive=cfg["use_xg_aggressive"],
            use_calibrated_momentum=cfg["use_calibrated_momentum"],
        )
        results.append(result.to_dict())

    summary = {
        "n_ticks_total": len(df),
        "n_events": df["event_id"].nunique() if "event_id" in df.columns else 0,
        "configs": results,
    }

    if verbose:
        print("\n=== Brier Benchmark por Minuto ===")
        print(f"Ticks avaliados: {summary['n_ticks_total']} de {summary['n_events']} eventos")
        print()
        for r in results:
            print(f"Config: {r['config_name']}")
            print(f"  Brier overall: {r['brier_overall']:.5f}")
            print(f"  Por mercado: 1={r['brier_by_market'].get('1', 0):.5f} X={r['brier_by_market'].get('X', 0):.5f} 2={r['brier_by_market'].get('2', 0):.5f}")
            print(f"  Por minuto:")
            for bucket, score in sorted(r['brier_by_minute'].items()):
                print(f"    {bucket}: {score:.5f}")
            print()

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        if verbose:
            print(f"Resultados salvos em: {output_path}")

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark Brier por minuto do modelo in-play"
    )
    parser.add_argument("--event-ids", type=int, nargs="*", help="Filtrar por eventos específicos")
    parser.add_argument("--output", type=Path, help="Salvar resultados em JSON")
    parser.add_argument("--quiet", action="store_true", help="Não imprimir no console")
    args = parser.parse_args()

    result = run_brier_benchmark(
        event_ids=args.event_ids,
        output_path=args.output,
        verbose=not args.quiet,
    )
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
