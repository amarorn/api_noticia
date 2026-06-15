"""Parser de CSV de transações Superbet.

Formato esperado (header):
    DataHoraDaTransação,Transação,Método de Pagamento,Valor,
    SaldoEmDinheiro,SaldoEmDinheiroAnterior,SaldoBônus,SaldoBônusAnterior,NomeDoJogo
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd

from schemas.user_transaction import UserTransactionRow

# Mapping CSV header → field interno
COLUMN_MAP = {
    "DataHoraDaTransação": "transaction_at",
    "Transação": "transaction_type",
    "Método de Pagamento": "payment_method",
    "Valor": "amount",
    "SaldoEmDinheiro": "cash_balance",
    "SaldoEmDinheiroAnterior": "cash_balance_prev",
    "SaldoBônus": "bonus_balance",
    "SaldoBônusAnterior": "bonus_balance_prev",
    "NomeDoJogo": "game_name",
}


def _parse_timestamp(raw: str) -> datetime:
    """Tenta vários formatos comuns do CSV Superbet."""
    raw = (raw or "").strip()
    formats = [
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(raw)


def _parse_float(raw: str | None) -> float:
    if raw is None or str(raw).strip() == "":
        return 0.0
    s = str(raw).strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_string(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    return s if s else None


def parse_user_csv(
    content: str | bytes,
    user_id: str,
    upload_id: str | None = None,
) -> list[UserTransactionRow]:
    """Parse do CSV em uma lista de UserTransactionRow validados.

    Args:
        content: bytes ou string do CSV (com header).
        user_id: identificador do usuário dono do CSV.
        upload_id: UUID opcional; se None, gera um novo.

    Returns:
        Lista de UserTransactionRow.
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")  # remove BOM se existir

    if upload_id is None:
        upload_id = str(uuid.uuid4())

    # Detectar header com possível "Dados da carteira para X" como primeira linha
    lines = content.splitlines()
    header_idx = 0
    for idx, line in enumerate(lines):
        if "DataHora" in line and "Transação" in line:
            header_idx = idx
            break

    csv_text = "\n".join(lines[header_idx:])

    reader = csv.DictReader(io.StringIO(csv_text))
    rows: list[UserTransactionRow] = []
    for raw in reader:
        try:
            row = UserTransactionRow(
                transaction_at=_parse_timestamp(raw.get("DataHoraDaTransação", "")),
                transaction_type=(_parse_string(raw.get("Transação")) or "").lower(),
                payment_method=_parse_string(raw.get("Método de Pagamento")),
                amount=_parse_float(raw.get("Valor")),
                cash_balance=_parse_float(raw.get("SaldoEmDinheiro")),
                cash_balance_prev=_parse_float(raw.get("SaldoEmDinheiroAnterior")),
                bonus_balance=_parse_float(raw.get("SaldoBônus")),
                bonus_balance_prev=_parse_float(raw.get("SaldoBônusAnterior")),
                game_name=_parse_string(raw.get("NomeDoJogo")) or "UNKNOWN",
                user_id=user_id,
                upload_id=upload_id,
            )
            rows.append(row)
        except Exception:
            # Linha mal-formada; pular silenciosamente
            continue

    return rows


def parse_user_csv_file(
    path: Path,
    user_id: str,
    upload_id: str | None = None,
) -> list[UserTransactionRow]:
    """Atalho para ler arquivo do disco."""
    return parse_user_csv(path.read_bytes(), user_id, upload_id)


def rows_to_dataframe(rows: list[UserTransactionRow]) -> pd.DataFrame:
    """Converte para DataFrame pandas tipado para escrita Parquet."""
    if not rows:
        return pd.DataFrame()
    data = [r.model_dump() for r in rows]
    df = pd.DataFrame(data)
    if "transaction_at" in df.columns:
        df["transaction_at"] = pd.to_datetime(df["transaction_at"], errors="coerce")
    return df
