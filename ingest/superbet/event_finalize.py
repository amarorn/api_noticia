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
from ingest.superbet.store import is_valid_superbet_event_id, merge_snapshot_into_odds_file

logger = logging.getLogger(__name__)

_REGISTRY_NAME = "superbet_finalized_events.json"
_FINISHED_STATUSES = {"FINISHED", "ENDED", "CLOSED", "CANCELLED", "ABANDONED", "COMPLETE"}
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


def list_pending_watch_event_ids(*, max_events: int | None = None) -> list[int]:
    """Eventos com bronze Superbet ainda não finalizados no gold."""
    events_root = settings.bronze_path / "superbet" / "events"
    if not events_root.is_dir():
        return []
    registry = _load_registry().get("events", {})
    pending: list[int] = []
    for path in sorted(events_root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_dir() or not path.name.isdigit():
            continue
        eid = int(path.name)
        if not is_valid_superbet_event_id(eid):
            logger.debug("watchlist_ignora_event_id_invalido event_id=%s", eid)
            continue
        if str(eid) in registry:
            continue
        latest = path / "latest.json"
        if not latest.exists():
            continue
        pending.append(eid)
        if max_events is not None and len(pending) >= max_events:
            break
    return pending


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

    ip = snapshot.inplay
    postmortem_path = None
    if ip is not None:
        try:
            from pipelines.inplay_postmortem import save_inplay_postmortem

            postmortem_path = save_inplay_postmortem(
                event_id,
                home_score=int(ip.home_score or 0),
                away_score=int(ip.away_score or 0),
                ht_home=ip.ht_home_score,
                ht_away=ip.ht_away_score,
                home_team=snapshot.home_team,
                away_team=snapshot.away_team,
            )
        except Exception as exc:
            logger.warning("postmortem falhou: %s", exc)

    try:
        from pipelines.inplay_match_states import upsert_match_states

        silver_path = upsert_match_states(event_ids=[event_id])
        entry_silver = str(silver_path)
    except Exception as exc:
        logger.warning("silver match_states falhou: %s", exc)
        entry_silver = None

    settle_summary = None
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
                home_corners=ip.home_corners,
                away_corners=ip.away_corners,
                baseball_innings=ip.baseball_innings or None,
            )
        except Exception as exc:
            logger.warning("settle open bets falhou: %s", exc)
            settle_summary = {"error": str(exc)}

    wc_sync = None
    if ip is not None:
        try:
            from pipelines.sync_wc_group_results import sync_single_wc_result

            wc_sync = sync_single_wc_result(
                snapshot.home_team,
                snapshot.away_team,
                int(ip.home_score or 0),
                int(ip.away_score or 0),
            )
        except Exception as exc:
            logger.warning("sync wc_2026 placar falhou: %s", exc)
            wc_sync = {"updated": False, "error": str(exc)}

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
        "postmortem_path": str(postmortem_path) if postmortem_path else None,
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
        "wc_result_sync": wc_sync,
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


def mark_event_watchlist_discarded(event_id: int, reason: str) -> dict[str, Any]:
    """Remove evento da watchlist sem pipeline gold completo (API 404 / bronze stale)."""
    key = str(event_id)
    registry = _load_registry()
    if key in registry.get("events", {}):
        return registry["events"][key]

    entry = {
        "event_id": event_id,
        "finalized_at": datetime.now(UTC).isoformat(),
        "discarded": True,
        "discard_reason": reason,
    }
    registry.setdefault("events", {})[key] = entry
    _save_registry(registry)
    logger.info("watchlist_evento_descartado event_id=%s reason=%s", event_id, reason)
    return entry


def _bronze_latest_age_hours(event_id: int) -> float | None:
    path = settings.bronze_path / "superbet" / "events" / str(event_id) / "latest.json"
    if not path.exists():
        return None
    age_sec = max(0.0, datetime.now(UTC).timestamp() - path.stat().st_mtime)
    return age_sec / 3600.0


def _snapshot_is_finished(snapshot: SuperbetEventSnapshot) -> bool:
    if not snapshot.inplay:
        return not snapshot.is_live
    status = str(snapshot.inplay.status or "").upper()
    if status in _FINISHED_STATUSES:
        return True
    if not snapshot.is_live and status not in {"", "LIVE", "IN_PROGRESS", "STARTED"}:
        return True
    return False


def _inplay_dict_from_snapshot(snapshot: SuperbetEventSnapshot) -> dict[str, Any]:
    ip = snapshot.inplay
    if ip is None:
        return {"current_score": "0x0"}
    return {
        "current_score": f"{ip.home_score}x{ip.away_score}",
        "prob_final_home": None,
        "prob_final_draw": None,
        "prob_final_away": None,
        "minute": ip.minute,
    }


def try_finalize_from_bronze(event_id: int) -> dict[str, Any] | None:
    """Finaliza evento a partir do bronze local quando o jogo já encerrou."""
    from ingest.superbet.store import load_latest_snapshot

    if is_event_finalized(event_id):
        return _load_registry().get("events", {}).get(str(event_id))

    snapshot = load_latest_snapshot(event_id)
    if snapshot is None:
        return mark_event_watchlist_discarded(event_id, "sem_bronze")

    if not _snapshot_is_finished(snapshot):
        return None

    inplay = _inplay_dict_from_snapshot(snapshot)
    advice = {"aportes": [], "confidence": None}
    return maybe_finalize_finished_event(
        event_id=event_id,
        snapshot=snapshot,
        inplay=inplay,
        advice=advice,
        is_finished=True,
    )


def sweep_stale_watchlist_events(
    event_ids: list[int],
    *,
    live_event_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Varre watchlist: finaliza encerrados ou descarta bronze antigo sem ao vivo."""
    if not settings.superbet_watchlist_sweep_enabled:
        return []

    live = live_event_ids or set()
    results: list[dict[str, Any]] = []
    stale_hours = settings.superbet_watchlist_stale_hours

    for event_id in event_ids:
        if event_id in live:
            continue
        if is_event_finalized(event_id):
            continue

        finalized = try_finalize_from_bronze(event_id)
        if finalized is not None:
            results.append({"event_id": event_id, "action": "finalized", "detail": finalized})
            continue

        age_h = _bronze_latest_age_hours(event_id)
        if age_h is not None and age_h >= stale_hours:
            from ingest.superbet.store import load_latest_snapshot

            snap = load_latest_snapshot(event_id)
            if snap is None or not snap.is_live:
                discarded = mark_event_watchlist_discarded(
                    event_id,
                    f"bronze_stale_{age_h:.0f}h",
                )
                results.append({"event_id": event_id, "action": "discarded", "detail": discarded})

    return results


__all__ = [
    "is_event_finalized",
    "list_pending_watch_event_ids",
    "mark_event_watchlist_discarded",
    "maybe_finalize_finished_event",
    "save_finished_event_record",
    "sweep_stale_watchlist_events",
    "try_finalize_from_bronze",
]
