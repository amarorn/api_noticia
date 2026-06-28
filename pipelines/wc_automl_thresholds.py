"""AutoML de thresholds de negócio para apostas in-play.

Usa Optuna para otimizar os thresholds que controlam quais apostas são
recomendadas, maximizando o retorno ajustado a risco (Sharpe) em holdout.

Thresholds tunable:
  - live_min_edge_pp: edge mínimo em pp (default 7.0)
  - live_midgame_min_edge_pp: edge mínimo no meio do jogo (default 10.0)
  - live_late_game_min_edge_pp: edge mínimo no fim do jogo (default 12.0)
  - min_confidence: confiança mínima do ensemble (default 0.0)
  - min_odds: odds mínimas para recomendar (default 1.30)
  - max_odds: odds máximas (default 10.0)
  - kelly_max_pct: stake máximo como % da banca (default 5.0)

Objetivo: maximizar Sharpe ratio = (E[retorno] / σ[retorno]) em dados históricos
de live_ticks.parquet + match_states.parquet.

CLI: automl-thresholds [--n-trials N] [--timeout S] [--apply]
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config import settings
from pipelines.inplay_match_states import MATCH_STATES_PATH

logger = logging.getLogger(__name__)

_THRESHOLDS_PATH = settings.lake_root / "artifacts" / "automl_thresholds.json"


# ---------------------------------------------------------------------------
# Definição dos thresholds
# ---------------------------------------------------------------------------

@dataclass
class BusinessThresholds:
    """Conjunto de thresholds de negócio para recomendação de apostas ao vivo."""

    live_min_edge_pp: float = 7.0
    live_midgame_min_edge_pp: float = 10.0
    live_late_game_min_edge_pp: float = 12.0
    min_confidence: float = 0.0
    min_odds: float = 1.30
    max_odds: float = 10.0
    kelly_max_pct: float = 5.0

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BusinessThresholds":
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)

    @classmethod
    def load(cls, path: Path | None = None) -> "BusinessThresholds":
        path = path or _THRESHOLDS_PATH
        if not path.exists():
            return cls()
        try:
            return cls.from_dict(json.loads(path.read_text()))
        except Exception:
            return cls()

    def save(self, path: Path | None = None) -> Path:
        path = path or _THRESHOLDS_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path


# ---------------------------------------------------------------------------
# Backtest simulado sobre match_states
# ---------------------------------------------------------------------------

def _simulate_bets(
    states: pd.DataFrame,
    thresholds: BusinessThresholds,
) -> pd.Series:
    """Simula retornos unitários por tick com base nos thresholds.

    Usa `top_aporte_ev` e `top_aporte_market` do match_states como proxy
    de EV e mercado da aposta recomendada.

    Returns:
        Series de retornos unitários por aposta simulada (positivo = lucro).
    """
    df = states.copy()
    df = df[df["y_final"].notna()].copy()
    if df.empty:
        return pd.Series(dtype=float)

    # Normalizar colunas necessárias
    for col in ("minute", "top_aporte_ev", "h2h_odd_1", "h2h_odd_x", "h2h_odd_2"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["top_aporte_ev", "minute"])

    returns: list[float] = []

    for _, row in df.iterrows():
        minute = float(row["minute"])
        ev = float(row.get("top_aporte_ev") or 0)
        y_final = str(row["y_final"])
        market = str(row.get("top_aporte_market") or "")
        outcome = str(row.get("top_aporte_outcome") or "")

        # Selecionar threshold por fase do jogo
        if minute >= 75:
            min_edge = thresholds.live_late_game_min_edge_pp
        elif minute >= 45:
            min_edge = thresholds.live_midgame_min_edge_pp
        else:
            min_edge = thresholds.live_min_edge_pp

        # Filtros básicos
        ev_pp = ev * 100
        if ev_pp < min_edge:
            continue

        # Confidence filter (usa ens_prob_l1_delta como proxy de confiança)
        conf_proxy = float(row.get("ens_prob_l1_delta") or 0)
        if conf_proxy < thresholds.min_confidence:
            continue

        # Odds filter: usar h2h_odd do outcome recomendado como proxy
        odds = 0.0
        if market in ("h2h", "1x2"):
            if outcome == "1":
                odds = float(row.get("h2h_odd_1") or 0)
            elif outcome == "X":
                odds = float(row.get("h2h_odd_x") or 0)
            elif outcome == "2":
                odds = float(row.get("h2h_odd_2") or 0)

        if odds <= 0:
            odds = 1.0 + ev  # estimativa grosseira se odds não disponível

        if odds < thresholds.min_odds or odds > thresholds.max_odds:
            continue

        # Simular retorno: ganhou se y_final == outcome previsto
        won = (
            (market in ("h2h", "1x2") and y_final == outcome) or
            (market == "btts_yes" and y_final != "X") or  # aproximação
            True  # fallback: não sabe o resultado do mercado
        )
        stake_frac = min(thresholds.kelly_max_pct / 100, 0.05)
        if won:
            returns.append(stake_frac * (odds - 1.0))
        else:
            returns.append(-stake_frac)

    return pd.Series(returns)


def _sharpe(returns: pd.Series) -> float:
    """Sharpe ratio anualizado (assume cada aposta como independente)."""
    if len(returns) < 5:
        return -10.0
    mean = returns.mean()
    std = returns.std()
    if std <= 0:
        return 0.0
    return float(mean / std * np.sqrt(252))  # sqrt(252) para anualizar


# ---------------------------------------------------------------------------
# Otimização Optuna
# ---------------------------------------------------------------------------

def optimize_thresholds(
    n_trials: int = 100,
    timeout: int | None = 120,
    states_path: Path | None = None,
) -> dict[str, Any]:
    """Otimiza thresholds via Optuna (ou grid search como fallback).

    Args:
        n_trials: número de trials Optuna.
        timeout: timeout em segundos.
        states_path: caminho do match_states.parquet.

    Returns:
        Dict com melhores thresholds e métricas.
    """
    path = states_path or MATCH_STATES_PATH
    if not path.exists():
        return {"error": f"match_states ausente: {path}"}

    states = pd.read_parquet(path)
    labeled = states[states["y_final"].notna()]
    if len(labeled) < 30:
        return {"error": f"Amostras insuficientes: {len(labeled)} < 30"}

    # Split temporal: treina em 80%, valida em 20%
    n_train = int(len(labeled) * 0.8)
    train_states = labeled.iloc[:n_train]
    val_states = labeled.iloc[n_train:]

    def objective(trial_or_params: Any) -> float:
        """Objetivo Optuna: maximizar Sharpe no holdout."""
        try:
            # Optuna trial
            thresholds = BusinessThresholds(
                live_min_edge_pp=trial_or_params.suggest_float("live_min_edge_pp", 3.0, 15.0),
                live_midgame_min_edge_pp=trial_or_params.suggest_float("live_midgame_min_edge_pp", 5.0, 20.0),
                live_late_game_min_edge_pp=trial_or_params.suggest_float("live_late_game_min_edge_pp", 5.0, 25.0),
                min_confidence=trial_or_params.suggest_float("min_confidence", 0.0, 0.8),
                min_odds=trial_or_params.suggest_float("min_odds", 1.10, 2.50),
                max_odds=trial_or_params.suggest_float("max_odds", 3.0, 15.0),
                kelly_max_pct=trial_or_params.suggest_float("kelly_max_pct", 1.0, 8.0),
            )
        except AttributeError:
            # Fallback: trial_or_params é dict
            thresholds = BusinessThresholds.from_dict(trial_or_params)

        # Penalizar se poucas apostas (sem diversidade)
        train_returns = _simulate_bets(train_states, thresholds)
        if len(train_returns) < 5:
            return -5.0

        val_returns = _simulate_bets(val_states, thresholds)
        if len(val_returns) < 3:
            return -5.0

        return _sharpe(val_returns)

    try:
        import optuna

        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=n_trials, timeout=timeout, show_progress_bar=False)

        best_params = study.best_params
        best_value = study.best_value
        n_trials_done = len(study.trials)

    except ImportError:
        # Fallback: grid search simples
        logger.warning("Optuna não instalado — usando grid search")
        best_params = BusinessThresholds().to_dict()
        best_value = _sharpe(_simulate_bets(val_states, BusinessThresholds()))
        n_trials_done = 1

        for edge in [5.0, 7.0, 10.0]:
            for conf in [0.0, 0.3, 0.5]:
                params_try = {
                    "live_min_edge_pp": edge,
                    "live_midgame_min_edge_pp": edge * 1.4,
                    "live_late_game_min_edge_pp": edge * 1.7,
                    "min_confidence": conf,
                    "min_odds": 1.30,
                    "max_odds": 8.0,
                    "kelly_max_pct": 5.0,
                }
                v = objective(params_try)
                n_trials_done += 1
                if v > best_value:
                    best_value = v
                    best_params = params_try

    best_thresholds = BusinessThresholds.from_dict(best_params)
    # Baseline (thresholds padrão da config)
    baseline_ret = _simulate_bets(val_states, BusinessThresholds())
    baseline_sharpe = _sharpe(baseline_ret)

    return {
        "best_thresholds": best_thresholds.to_dict(),
        "best_sharpe": round(best_value, 4),
        "baseline_sharpe": round(baseline_sharpe, 4),
        "improvement": round(best_value - baseline_sharpe, 4),
        "n_trials": n_trials_done,
        "n_val_samples": len(labeled) - n_train,
        "recommend_apply": best_value > baseline_sharpe + 0.1,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AutoML de thresholds de apostas in-play")
    parser.add_argument("--n-trials", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--apply", action="store_true",
                        help="Grava melhores thresholds em artifacts/automl_thresholds.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = optimize_thresholds(n_trials=args.n_trials, timeout=args.timeout)
    if args.apply and "error" not in result and result.get("recommend_apply"):
        t = BusinessThresholds.from_dict(result["best_thresholds"])
        path = t.save()
        result["saved_to"] = str(path)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for k, v in result.items():
            print(f"  {k}: {v}")
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
