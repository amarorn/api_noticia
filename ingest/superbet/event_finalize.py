"""Finalização de evento Superbet: persistência gold + retreino in-play.

Disparado quando run_live_advice detecta status FINISHED/ENDED.
Idempotente por event_id (registry em artifacts).
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import settings
from ingest.superbet.parser import SuperbetEventSnapshot
from ingest.superbet.store import merge_snapshot_into_odds_file

logger = logging.getLogger(__name__)

_REGISTRY_NAME = "superbet_finalized_events.json"
_retrain_lock = threading.Lock()
_retrain_queue: list[int] = []
_retrain_worker: threading.Thread | None = None


def _registry_path() -> Path:
    return settings.lake_root / "artifacts" / _REGISTRY_NAME


def _gold_event_dir(event_id: int) -> Path:
    return settings.gold_path / "superbet" / "events" / str(event_id)


def _load_registry() -> dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return {"events": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"events": {}}
    if "events" not in data:
        data["events"] = {}
    return data


def _save_registry(data: dict[str, Any]) -> Path:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def is_event_finalized(event_id: int) -> bool:
    return str(event_id) in _load_registry().get("events", {})


def _count_bronze_snapshots(event_id: int) -> int:
    base = settings.bronze_path / "superbet" / "events" / str(event_id)
    if not base.exists():
        return 0
    return sum(1 for p in base.glob("*.json") if p.name != "latest.json")


def _count_live_ticks(event_id: int) -> int:
    try:
        import pandas as pd

        from ingest.superbet.live_ticks import live_ticks_path

        path = live_ticks_path()
        if path.exists():
            df = pd.read_parquet(path)
            if "event_id" in df.columns:
                return int((df["event_id"] == event_id).sum())
    except Exception as exc:
        logger.debug("contagem live_ticks falhou: %s", exc)
    return 0


def save_finished_event_record(
    *,
    event_id: int,
    snapshot: SuperbetEventSnapshot,
    inplay: dict[str, Any],
    advice: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> Path:
    """Grava manifest gold do jogo encerrado (placar final, ticks, resumo modelo)."""
    out_dir = _gold_event_dir(event_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    ip = snapshot.inplay
    record = {
        "event_id": event_id,
        "home_team": snapshot.home_team,
        "away_team": snapshot.away_team,
        "betradar_id": snapshot.betradar_id,
        "final_score": inplay.get("current_score"),
        "home_score": ip.home_score if ip else None,
        "away_score": ip.away_score if ip else None,
        "ht_score": f"{ip.ht_home_score}x{ip.ht_away_score}" if ip and ip.ht_home_score is not None else None,
        "status": ip.status if ip else None,
        "period_label": ip.period_label if ip else None,
        "minute": ip.minute if ip else None,
        "captured_at": snapshot.captured_at,
        "finalized_at": datetime.now(UTC).isoformat(),
        "n_bronze_snapshots": _count_bronze_snapshots(event_id),
        "n_live_ticks": _count_live_ticks(event_id),
        "inplay_summary": {
            "prob_final_home": inplay.get("prob_final_home"),
            "prob_final_draw": inplay.get("prob_final_draw"),
            "prob_final_away": inplay.get("prob_final_away"),
            "over_2_5": (inplay.get("final_line_probs") or {}).get("over_2_5"),
            "btts_final": inplay.get("btts_final"),
        },
        "confidence": advice.get("confidence"),
        "n_aportes": len(advice.get("aportes") or []),
        "extra": extra or {},
    }
    out_path = out_dir / "final.json"
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def _run_retrain_pipeline(event_id: int, user_id: str) -> dict[str, Any]:
    """Retreina modelos in-play após jogo encerrado."""
    result: dict[str, Any] = {"event_id": event_id, "steps": {}}

    if settings.wallet_inbox_enabled:
        try:
            from ingest.user_transactions.wallet_inbox import scan_inbox

            inbox = scan_inbox(user_id, reconcile=False)
            result["steps"]["wallet_inbox"] = inbox.to_dict()
        except Exception as exc:
            logger.warning("wallet inbox pós-jogo falhou: %s", exc)
            result["steps"]["wallet_inbox"] = {"error": str(exc)}

    # Reconciliar carteira (se houver transações bronze)
    try:
        from pipelines.user_bet_reconciliation import reconcile_user_transactions, save_reconciliation

        df = reconcile_user_transactions(user_id)
        if not df.empty:
            path = save_reconciliation(df, user_id)
            result["steps"]["reconciliation"] = {"n_pairs": len(df), "path": str(path)}
    except Exception as exc:
        logger.warning("reconcile pós-jogo falhou: %s", exc)
        result["steps"]["reconciliation"] = {"error": str(exc)}

    if settings.superbet_finalize_retrain_feedback:
        try:
            from pipelines.feedback_retrain import retrain_with_feedback

            fb = retrain_with_feedback(
                user_id=user_id,
                min_confidence=settings.superbet_finalize_min_confidence,
            )
            result["steps"]["feedback_gbm"] = {
                "accepted": fb.accepted,
                "n_feedback": fb.n_feedback_examples,
                "brier_delta": fb.brier_delta,
                "artifact": fb.artifact_path,
            }
        except Exception as exc:
            logger.warning("retrain-with-feedback falhou: %s", exc)
            result["steps"]["feedback_gbm"] = {"error": str(exc)}

    if settings.superbet_finalize_retrain_gbm:
        try:
            from pipelines.wc_inplay_gbm_train import run_gbm_training

            gbm = run_gbm_training(seed=42)
            result["steps"]["gbm"] = {
                "val_logloss": gbm.val_logloss,
                "val_accuracy": gbm.val_accuracy,
                "n_train": gbm.n_train,
            }
        except Exception as exc:
            logger.warning("train-inplay-gbm falhou: %s", exc)
            result["steps"]["gbm"] = {"error": str(exc)}

    if settings.superbet_finalize_retrain_coefficients:
        try:
            from pipelines.wc_inplay_tune import run_inplay_tune

            coefs = run_inplay_tune(verbose=False)
            result["steps"]["coefficients"] = {
                "holdout_brier": coefs.holdout_brier,
                "n_observations": coefs.n_observations,
            }
        except Exception as exc:
            logger.warning("inplay tune falhou: %s", exc)
            result["steps"]["coefficients"] = {"error": str(exc)}

    result["completed_at"] = datetime.now(UTC).isoformat()
    return result


def _retrain_worker_loop() -> None:
    global _retrain_queue
    while True:
        with _retrain_lock:
            if not _retrain_queue:
                break
            event_id = _retrain_queue.pop(0)
        user_id = settings.superbet_finalize_user_id
        logger.info("post_event_retrain_started", event_id=event_id, user_id=user_id)
        try:
            outcome = _run_retrain_pipeline(event_id, user_id)
            registry = _load_registry()
            entry = registry["events"].get(str(event_id), {})
            entry["retrain"] = outcome
            registry["events"][str(event_id)] = entry
            _save_registry(registry)
            logger.info("post_event_retrain_done", event_id=event_id, steps=list(outcome.get("steps", {})))
        except Exception as exc:
            logger.exception("post_event_retrain_failed", event_id=event_id, error=str(exc))


def _enqueue_retrain(event_id: int) -> None:
    global _retrain_worker
    with _retrain_lock:
        if event_id not in _retrain_queue:
            _retrain_queue.append(event_id)
        if _retrain_worker is None or not _retrain_worker.is_alive():
            _retrain_worker = threading.Thread(
                target=_retrain_worker_loop,
                name="superbet-post-event-retrain",
                daemon=True,
            )
            _retrain_worker.start()


def maybe_finalize_finished_event(
    *,
    event_id: int,
    snapshot: SuperbetEventSnapshot,
    inplay: dict[str, Any],
    advice: dict[str, Any],
    is_finished: bool,
) -> dict[str, Any] | None:
    """Salva gold + dispara retreino uma única vez por event_id."""
    if not is_finished or not settings.superbet_finalize_enabled:
        return None

    key = str(event_id)
    registry = _load_registry()
    if key in registry.get("events", {}):
        return registry["events"][key]

    gold_path = save_finished_event_record(
        event_id=event_id,
        snapshot=snapshot,
        inplay=inplay,
        advice=advice,
    )

    try:
        from pipelines.inplay_match_states import upsert_match_states

        silver_path = upsert_match_states(event_ids=[event_id])
        entry_silver = str(silver_path)
    except Exception as exc:
        logger.warning("silver match_states falhou: %s", exc)
        entry_silver = None

    settle_summary = None
    ip = snapshot.inplay
    if settings.superbet_finalize_settle_open_bets and ip is not None:
        try:
            from models.open_bet_settle import settle_open_bets_for_event

            hs = ip.home_score if ip.home_score is not None else 0
            as_ = ip.away_score if ip.away_score is not None else 0
            settle_summary = settle_open_bets_for_event(
                event_id=event_id,
                home_team=snapshot.home_team,
                away_team=snapshot.away_team,
                home_score=int(hs),
                away_score=int(as_),
                final_score=inplay.get("current_score"),
            )
        except Exception as exc:
            logger.warning("settle open bets falhou: %s", exc)
            settle_summary = {"error": str(exc)}

    odds_path = None
    if snapshot.h2h_odds:
        try:
            odds_path = merge_snapshot_into_odds_file(snapshot)
            from pipelines.wc_market_features import load_match_odds_index

            load_match_odds_index.cache_clear()
        except Exception as exc:
            logger.warning("merge odds pós-jogo falhou: %s", exc)

    entry = {
        "event_id": event_id,
        "home_team": snapshot.home_team,
        "away_team": snapshot.away_team,
        "final_score": inplay.get("current_score"),
        "finalized_at": datetime.now(UTC).isoformat(),
        "gold_path": str(gold_path),
        "silver_match_states": entry_silver,
        "settle_open_bets": (
            {
                "n_matched": settle_summary.n_matched,
                "n_settled": settle_summary.n_settled,
                "n_skipped": settle_summary.n_skipped,
                "settled_ids": settle_summary.settled_ids,
            }
            if settle_summary and hasattr(settle_summary, "n_settled")
            else settle_summary
        ),
        "odds_path": str(odds_path) if odds_path else None,
        "retrain_scheduled": settings.superbet_finalize_retrain,
    }
    registry.setdefault("events", {})[key] = entry
    _save_registry(registry)

    logger.info(
        "evento_superbet_finalizado",
        event_id=event_id,
        score=inplay.get("current_score"),
        gold=str(gold_path),
    )

    if settings.superbet_finalize_retrain:
        _enqueue_retrain(event_id)

    return entry


__all__ = [
    "is_event_finalized",
    "maybe_finalize_finished_event",
    "save_finished_event_record",
]
