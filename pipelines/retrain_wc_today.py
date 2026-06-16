"""Retreino WC + in-play com dados até hoje, sem vazamento nos jogos futuros.

Etapas:
1. Sincroniza placares oficiais → ``wc_2026.json``
2. Atualiza Parquet FIFA (treino ensemble vê jogos de hoje)
3. Retreina in-play (Hawkes, coeficientes, GBM, feedback opcional)
4. Retreina predictor pré-jogo (``train-wc --force``)
5. Gera palpites só para jogos **sem placar**, com ``before_date=kickoff``

CLI: ``retrain-wc-hoje``
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from config import settings
from pipelines.wc_predict_utils import before_date_for_match, match_is_played, parse_match_kickoff
from schemas.national_teams import normalize_national_team

log = structlog.get_logger()

DEFAULT_ROUND = Path("data/rounds/wc_2026.json")


@dataclass
class RetrainTodayReport:
    started_at: str
    data_sync: dict[str, Any] = field(default_factory=dict)
    inplay: dict[str, Any] = field(default_factory=dict)
    pregame: dict[str, Any] = field(default_factory=dict)
    predictions: dict[str, Any] | None = None
    finished_at: str | None = None
    errors: list[str] = field(default_factory=list)


def _fixture_stats() -> dict[str, Any]:
    root = settings.fixtures_path
    stats: dict[str, Any] = {}
    for name in ("fifa_matches.parquet", "sofascore_matches.parquet"):
        path = root / name
        if not path.exists():
            stats[name] = {"exists": False}
            continue
        df = pd.read_parquet(path)
        df["match_date"] = pd.to_datetime(df["match_date"], utc=True, errors="coerce")
        june26 = df[(df["match_date"].dt.year == 2026) & (df["match_date"].dt.month == 6)]
        scored = june26
        if "home_score" in june26.columns:
            scored = june26[june26["home_score"].notna() & june26["away_score"].notna()]
        stats[name] = {
            "exists": True,
            "rows": len(df),
            "jun_2026": len(june26),
            "jun_2026_scored": len(scored),
            "mtime": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(),
        }
    return stats


def sync_training_data(*, force_fifa_refresh: bool = True) -> dict[str, Any]:
    """Atualiza calendário oficial + Parquet FIFA usado pelo train-wc."""
    from ingest.fifa.match_ingest import load_fifa_window_matches
    from ingest.fifa.fixtures_importer import import_fifa_window_matches
    from pipelines.sync_wc_group_results import sync_wc_group_results

    round_file = DEFAULT_ROUND
    sync_report = sync_wc_group_results(
        round_file=round_file,
        source="fifa",
        force_fifa_refresh=force_fifa_refresh,
    )

    window = load_fifa_window_matches(force_refresh=force_fifa_refresh)
    fifa_df = import_fifa_window_matches(window_matches=window, skip_existing=False)

    return {
        "round_sync": sync_report.to_dict() if hasattr(sync_report, "to_dict") else sync_report,
        "fifa_parquet_rows": len(fifa_df),
        "fixtures": _fixture_stats(),
    }


def retrain_inplay_models(
    *,
    user_id: str = "jamarorn",
    min_confidence: float = 0.7,
    skip_feedback: bool = False,
    skip_hawkes: bool = False,
) -> dict[str, Any]:
    out: dict[str, Any] = {}

    if not skip_hawkes:
        from pipelines.wc_inplay_hawkes_fit import run_hawkes_calibration

        fit = run_hawkes_calibration(max_season=2026)
        out["hawkes"] = {
            "alpha_self": fit.alpha_self,
            "alpha_cross": fit.alpha_cross,
            "beta": fit.beta,
            "half_life_minutes": fit.half_life_minutes,
            "stable": fit.is_stable,
        }

    from pipelines.wc_inplay_tune import run_inplay_tune

    coefs = run_inplay_tune(verbose=False)
    out["coefficients"] = {
        "holdout_brier": coefs.holdout_brier,
        "n_observations": coefs.n_observations,
    }

    from pipelines.wc_inplay_gbm_train import run_gbm_training

    gbm = run_gbm_training(seed=42, max_season=2026)
    out["gbm"] = {
        "val_logloss": gbm.val_logloss,
        "val_accuracy": gbm.val_accuracy,
        "n_train": gbm.n_train,
        "n_val": gbm.n_val,
    }

    if not skip_feedback:
        try:
            from pipelines.feedback_retrain import retrain_with_feedback

            out["feedback"] = asdict(
                retrain_with_feedback(user_id=user_id, min_confidence=min_confidence)
            )
        except Exception as exc:
            out["feedback"] = {"error": str(exc)}

    return out


def retrain_pregame_predictor() -> dict[str, Any]:
    from models.wc_artifact import load_or_train_wc_predictor

    _, manifest = load_or_train_wc_predictor(force=True, allow_train=True)
    return {
        "created_at": manifest.get("created_at"),
        "fixture_rows": manifest.get("fixture_rows"),
        "holdout_accuracy": (manifest.get("training_metrics") or {}).get("holdout_accuracy"),
        "ensemble_brier": (manifest.get("collab_metrics") or {}).get("brier_score"),
    }


def predict_upcoming_matches(round_file: Path = DEFAULT_ROUND) -> dict[str, Any]:
    """Palpites para jogos sem placar, usando cutoff no kickoff (sem vazamento)."""
    from models.wc_artifact import load_or_train_wc_predictor

    round_data = json.loads(round_file.read_text(encoding="utf-8"))
    predictor, _ = load_or_train_wc_predictor(force=False, allow_train=False)
    now = datetime.now(UTC)

    preds: list[dict[str, Any]] = []
    skipped_played = 0

    for match in round_data.get("matches", []):
        if match_is_played(match):
            skipped_played += 1
            continue

        home = normalize_national_team(match["home_team"])
        away = normalize_national_team(match["away_team"])
        phase = match.get("phase", round_data.get("phase", "group"))
        cutoff = before_date_for_match(match, now=now)

        p = predictor.predict(
            home,
            away,
            phase=phase,
            is_neutral=True,
            before_date=cutoff,
            season=round_data.get("season"),
            group_name=match.get("group"),
        )
        preds.append(
            {
                "match_id": match.get("id"),
                "home_team": home,
                "away_team": away,
                "group": match.get("group"),
                "round": match.get("round"),
                "kickoff": match.get("kickoff"),
                "before_date": cutoff.isoformat() if cutoff else None,
                "prediction": p.prediction,
                "confidence": round(p.confidence, 4),
                "prob_home": round(p.prob_home, 4),
                "prob_draw": round(p.prob_draw, 4),
                "prob_away": round(p.prob_away, 4),
                "poisson_score": p.poisson_score,
            }
        )

    out_dir = settings.lake_root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"wc_2026_upcoming_{ts}.json"
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "competition": round_data.get("competition"),
        "season": round_data.get("season"),
        "n_upcoming": len(preds),
        "n_skipped_played": skipped_played,
        "note": "before_date=kickoff evita vazamento de jogos do mesmo dia já finalizados",
        "predictions": preds,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "n_upcoming": len(preds),
        "n_skipped_played": skipped_played,
        "output_path": str(out_path),
        "next_kickoffs": [
            p["kickoff"]
            for p in sorted(
                preds,
                key=lambda x: parse_match_kickoff({"kickoff": x.get("kickoff")}) or datetime.max.replace(tzinfo=UTC),
            )[:5]
        ],
    }


def run_retrain_wc_today(
    *,
    user_id: str = "jamarorn",
    min_confidence: float = 0.7,
    skip_data_sync: bool = False,
    skip_inplay: bool = False,
    skip_pregame: bool = False,
    skip_predictions: bool = False,
    skip_feedback: bool = False,
    skip_hawkes: bool = False,
    force_fifa_refresh: bool = True,
    round_file: Path = DEFAULT_ROUND,
) -> RetrainTodayReport:
    report = RetrainTodayReport(started_at=datetime.now(UTC).isoformat())

    if not skip_data_sync:
        print("\n=== 1/4 Sincronizar dados até hoje ===")
        try:
            report.data_sync = sync_training_data(force_fifa_refresh=force_fifa_refresh)
            print(json.dumps(report.data_sync, indent=2, ensure_ascii=False, default=str))
        except Exception as exc:
            log.exception("data_sync_failed", error=str(exc))
            report.errors.append(f"data_sync: {exc}")
            print(f"ERRO sync: {exc}")

    if not skip_inplay:
        print("\n=== 2/4 Retreino in-play ===")
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

    if not skip_pregame:
        print("\n=== 3/4 Retreino predictor pré-jogo (train-wc) ===")
        try:
            report.pregame = retrain_pregame_predictor()
            print(json.dumps(report.pregame, indent=2, ensure_ascii=False, default=str))
        except Exception as exc:
            log.exception("pregame_retrain_failed", error=str(exc))
            report.errors.append(f"pregame: {exc}")
            print(f"ERRO pré-jogo: {exc}")

    if not skip_predictions:
        print("\n=== 4/4 Palpites jogos restantes (sem vazamento) ===")
        try:
            report.predictions = predict_upcoming_matches(round_file)
            print(json.dumps(report.predictions, indent=2, ensure_ascii=False, default=str))
        except Exception as exc:
            log.exception("predictions_failed", error=str(exc))
            report.errors.append(f"predictions: {exc}")
            print(f"ERRO palpites: {exc}")

    report.finished_at = datetime.now(UTC).isoformat()
    out_dir = settings.lake_root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = out_dir / f"retrain_wc_today_{ts}.json"
    report_path.write_text(
        json.dumps(asdict(report), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"\nRelatório: {report_path}")
    if report.errors:
        print(f"Avisos/erros: {len(report.errors)}")
    else:
        print("Retreino concluído. Reinicie a API para carregar o novo artifact.")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Retreina modelos WC com dados até hoje; palpites só para jogos futuros"
    )
    parser.add_argument("--user", default="jamarorn")
    parser.add_argument("--min-confidence", type=float, default=0.7)
    parser.add_argument("--skip-data-sync", action="store_true")
    parser.add_argument("--skip-inplay", action="store_true")
    parser.add_argument("--skip-pregame", action="store_true", help="Pula train-wc (~5–15 min)")
    parser.add_argument("--skip-predictions", action="store_true")
    parser.add_argument("--skip-feedback", action="store_true")
    parser.add_argument("--skip-hawkes", action="store_true")
    parser.add_argument("--no-fifa-refresh", action="store_true", help="Usa cache FIFA local")
    parser.add_argument("--round-file", type=Path, default=DEFAULT_ROUND)
    args = parser.parse_args()

    report = run_retrain_wc_today(
        user_id=args.user,
        min_confidence=args.min_confidence,
        skip_data_sync=args.skip_data_sync,
        skip_inplay=args.skip_inplay,
        skip_pregame=args.skip_pregame,
        skip_predictions=args.skip_predictions,
        skip_feedback=args.skip_feedback,
        skip_hawkes=args.skip_hawkes,
        force_fifa_refresh=not args.no_fifa_refresh,
        round_file=args.round_file,
    )
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
