"""Persistência das transações em Parquet bronze particionado."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import settings
from ingest.user_transactions.parser import rows_to_dataframe
from schemas.user_transaction import UserTransactionRow


def _bronze_root() -> Path:
    return Path(settings.lake_root) / "bronze" / "user_transactions"


def save_transactions_bronze(
    rows: list[UserTransactionRow],
    user_id: str,
    upload_id: str,
) -> Path:
    """Persiste as transações em Parquet particionado por user/year/month.

    Estrutura:
        data/lake/bronze/user_transactions/user=<id>/year=<>/month=<>/
            transactions_<upload_id>.parquet

    Para idempotência, regenera com mesmo upload_id se já existir.
    """
    if not rows:
        raise ValueError("Lista de transações vazia")

    df = rows_to_dataframe(rows)
    if df.empty:
        raise ValueError("DataFrame vazio após conversão")

    df["year"] = df["transaction_at"].dt.year
    df["month"] = df["transaction_at"].dt.month

    root = _bronze_root()
    grouped = df.groupby(["year", "month"], sort=True)

    output_paths = []
    for (year, month), grp in grouped:
        partition = root / f"user={user_id}" / f"year={year}" / f"month={month}"
        partition.mkdir(parents=True, exist_ok=True)
        out = partition / f"transactions_{upload_id}.parquet"
        grp.drop(columns=["year", "month"]).to_parquet(out, index=False)
        output_paths.append(out)

    # Para resposta: principal partição
    return output_paths[0] if output_paths else root


def load_transactions(user_id: str | None = None) -> pd.DataFrame:
    """Lê todas as transações do usuário (ou todos)."""
    root = _bronze_root()
    if not root.exists():
        return pd.DataFrame()

    pattern = f"user={user_id}/**/*.parquet" if user_id else "**/*.parquet"
    files = list(root.glob(pattern))
    if not files:
        return pd.DataFrame()

    dfs = []
    for f in files:
        try:
            dfs.append(pd.read_parquet(f))
        except Exception:
            continue

    if not dfs:
        return pd.DataFrame()

    df = pd.concat(dfs, ignore_index=True)
    if "transaction_at" in df.columns:
        df["transaction_at"] = pd.to_datetime(df["transaction_at"], errors="coerce")
        df = df.sort_values("transaction_at").reset_index(drop=True)
    return df


def list_uploads(user_id: str) -> list[dict]:
    """Lista uploads conhecidos para um usuário."""
    df = load_transactions(user_id)
    if df.empty or "upload_id" not in df.columns:
        return []

    grouped = df.groupby("upload_id").agg(
        n_rows=("transaction_type", "count"),
        first_at=("transaction_at", "min"),
        last_at=("transaction_at", "max"),
    ).reset_index()
    return grouped.to_dict(orient="records")
