"""Rotas de carteira e transações do usuário."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from config import settings

router = APIRouter(prefix="/user")


@router.get("/wallet/sync-status", response_model=dict)
def get_wallet_sync_status(user_id: str = Query("default")):
    from ingest.user_transactions.wallet_inbox import get_wallet_sync_status as _status

    return _status(user_id)


@router.post("/wallet/import-inbox", response_model=dict)
def import_wallet_inbox(user_id: str = Query("default")):
    from ingest.user_transactions.wallet_inbox import scan_inbox

    if not settings.wallet_inbox_enabled:
        raise HTTPException(status_code=503, detail="Wallet inbox desabilitada")
    outcome = scan_inbox(user_id, reconcile=True)
    return outcome.to_dict()


@router.post("/transactions/upload", response_model=dict)
async def upload_user_transactions(
    user_id: str = Query("default"),
    file: UploadFile = File(...),
):
    import uuid as _uuid

    from ingest.user_transactions.parser import parse_user_csv
    from ingest.user_transactions.store import save_transactions_bronze

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Arquivo deve ser .csv")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV maior que 10MB")

    upload_id = str(_uuid.uuid4())
    rows = parse_user_csv(content, user_id, upload_id)
    if not rows:
        raise HTTPException(status_code=422, detail="Nenhuma linha válida no CSV")

    out_path = save_transactions_bronze(rows, user_id, upload_id)

    n_inplay_placed = sum(1 for r in rows if r.is_inplay_bet and r.is_bet_placed)
    n_wins = sum(1 for r in rows if r.is_win)
    total_staked = sum(r.amount for r in rows if r.is_bet_placed)
    total_won = sum(r.amount for r in rows if r.is_win)

    return {
        "upload_id": upload_id, "user_id": user_id, "n_rows": len(rows),
        "n_inplay_bets_placed": n_inplay_placed, "n_wins": n_wins,
        "total_staked": round(total_staked, 2), "total_won": round(total_won, 2),
        "pnl": round(total_won - total_staked, 2),
        "file_path": str(out_path), "message": "ok",
    }


@router.get("/transactions/summary", response_model=dict)
def get_user_wallet_summary(user_id: str = Query("default")):
    from pipelines.user_bet_analytics import compute_wallet_summary

    return compute_wallet_summary(user_id)


@router.post("/transactions/reconcile", response_model=dict)
def reconcile_user_bets(user_id: str = Query("default")):
    from pipelines.user_bet_reconciliation import reconcile_user_transactions, save_reconciliation

    df = reconcile_user_transactions(user_id)
    if df.empty:
        return {"status": "empty", "n_pairs": 0}

    path = save_reconciliation(df, user_id)
    n_matched = int((df["match_confidence"].fillna(0) >= 0.5).sum())
    return {
        "status": "ok", "n_pairs": len(df),
        "n_matched_high_confidence": n_matched,
        "match_rate": round(n_matched / len(df), 3),
        "file_path": str(path),
    }


@router.get("/transactions/reconciliation", response_model=dict)
def get_user_reconciliation(
    user_id: str = Query("default"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    from pipelines.user_bet_analytics import compute_reconciliation_table

    return compute_reconciliation_table(user_id, limit=limit, offset=offset)


@router.get("/transactions/model-errors", response_model=dict)
def get_user_model_errors(user_id: str = Query("default")):
    from pipelines.user_bet_analytics import compute_model_errors_heatmap

    return compute_model_errors_heatmap(user_id)
