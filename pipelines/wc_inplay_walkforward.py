"""Walk-forward in-play: avaliação de Brier por snapshot de minuto.

Para cada (jogo, minuto_snapshot), o modelo simula o restante do jogo
e prevê probabilidades 1X2. Compara com o resultado real para calcular
Brier score estratificado por minuto, mercado e placar parcial.

Spec: docs/specs/spec-fase-2-momentum-calibrado.md § 5.2
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from models.wc_inplay import simulate_inplay
from pipelines.wc_build_timeline import build_timeline_from_fixtures, SNAPSHOT_MINUTES


@dataclass
class WalkForwardResult:
    """Resultado completo do walk-forward in-play."""

    brier_overall: float = 0.0
    brier_by_minute: dict[int, float] = field(default_factory=dict)
    n_samples: int = 0
    n_games: int = 0
    eval_season: int = 0
    elapsed_seconds: float = 0.0
    predictions: list[dict] = field(default_factory=list)


def evaluate_inplay(
    *,
    eval_season: int = 2022,
    train_seasons: list[int] | None = None,
    snapshot_minutes: list[int] | None = None,
    n_simulations: int = 5000,
    use_momentum: bool = True,
    lambda_home_default: float = 1.35,
    lambda_away_default: float = 1.10,
    verbose: bool = False,
) -> WalkForwardResult:
    """Executa walk-forward in-play sobre a season de avaliação.

    Para cada snapshot (jogo, minuto), roda simulate_inplay e compara
    P(1), P(X), P(2) com o resultado real.

    Args:
        eval_season: Season de holdout (não usar no treino).
        train_seasons: Seasons para definir λ (não usado nesta versão —
            usa λ default do estilo Copa do Mundo).
        snapshot_minutes: Minutos a avaliar.
        n_simulations: Simulações Monte Carlo por snapshot.
        use_momentum: Se True, aplica momentum (com eventos simulados).
        lambda_home_default: λ_full_home default (média Copa).
        lambda_away_default: λ_full_away default (média Copa).
        verbose: Imprime progresso.

    Returns:
        WalkForwardResult com Brier por minuto e geral.
    """
    if snapshot_minutes is None:
        snapshot_minutes = SNAPSHOT_MINUTES

    start_time = time.time()

    # Construir timeline (filtrar eval_season)
    timeline = build_timeline_from_fixtures(
        min_season=eval_season, max_season=eval_season,
        snapshot_minutes=snapshot_minutes,
    )
    if timeline.empty:
        return WalkForwardResult(eval_season=eval_season)

    # Resultado real de cada jogo (para calcular Brier)
    predictions: list[dict] = []
    n_games = timeline["match_id"].nunique()

    for idx, row in timeline.iterrows():
        # Estado parcial no snapshot
        minute = int(row["minute"])
        hs_partial = int(row["home_score_partial"])
        as_partial = int(row["away_score_partial"])
        hs_final = int(row["home_score_final"])
        as_final = int(row["away_score_final"])

        # Resultado real (1/X/2) baseado no placar final
        if hs_final > as_final:
            y_true = "1"
        elif hs_final == as_final:
            y_true = "X"
        else:
            y_true = "2"

        # Simular in-play
        momentum_events = []
        if use_momentum:
            # Gerar eventos sintéticos com base nos dados parciais
            for _ in range(int(row.get("home_red_cards", 0))):
                momentum_events.append({
                    "event_type": "red_card",
                    "minute": minute - 10,
                    "team": "home",
                })
            for _ in range(int(row.get("away_red_cards", 0))):
                momentum_events.append({
                    "event_type": "red_card",
                    "minute": minute - 10,
                    "team": "away",
                })

        try:
            result = simulate_inplay(
                home_team=str(row["home_team"]),
                away_team=str(row["away_team"]),
                home_score=hs_partial,
                away_score=as_partial,
                minute=minute,
                lambda_full_home=lambda_home_default,
                lambda_full_away=lambda_away_default,
                n_simulations=n_simulations,
                momentum_events=momentum_events if momentum_events else None,
                home_corners=int(row.get("home_corners", 0)),
                away_corners=int(row.get("away_corners", 0)),
            )
        except Exception:
            continue

        prob_1 = result.prob_final_home
        prob_x = result.prob_final_draw
        prob_2 = result.prob_final_away

        predictions.append({
            "match_id": row["match_id"],
            "minute": minute,
            "prob_1": prob_1,
            "prob_x": prob_x,
            "prob_2": prob_2,
            "y_true": y_true,
            "home_score_partial": hs_partial,
            "away_score_partial": as_partial,
        })

    if not predictions:
        return WalkForwardResult(eval_season=eval_season)

    # Calcular Brier
    elapsed = time.time() - start_time
    brier_by_minute: dict[int, float] = {}

    for minute in snapshot_minutes:
        preds_min = [p for p in predictions if p["minute"] == minute]
        if not preds_min:
            continue
        brier_by_minute[minute] = _brier_1x2(preds_min)

    brier_overall = _brier_1x2(predictions)

    if verbose:
        print(f"Walk-forward in-play — season {eval_season}")
        print(f"  Jogos: {n_games} | Snapshots: {len(predictions)}")
        print(f"  Brier overall: {brier_overall:.4f}")
        for m, b in sorted(brier_by_minute.items()):
            n_m = sum(1 for p in predictions if p["minute"] == m)
            print(f"  min {m:2d}: Brier={b:.4f} (n={n_m})")
        print(f"  Tempo: {elapsed:.1f}s")

    return WalkForwardResult(
        brier_overall=round(brier_overall, 6),
        brier_by_minute=brier_by_minute,
        n_samples=len(predictions),
        n_games=n_games,
        eval_season=eval_season,
        elapsed_seconds=round(elapsed, 1),
        predictions=predictions,
    )


def _brier_1x2(predictions: list[dict]) -> float:
    """Brier score multiclasse para lista de predições 1X2."""
    n = len(predictions)
    if n == 0:
        return 0.0
    total = 0.0
    for p in predictions:
        y = p["y_true"]
        total += (p["prob_1"] - (1.0 if y == "1" else 0.0)) ** 2
        total += (p["prob_x"] - (1.0 if y == "X" else 0.0)) ** 2
        total += (p["prob_2"] - (1.0 if y == "2" else 0.0)) ** 2
    return total / (n * 3)
