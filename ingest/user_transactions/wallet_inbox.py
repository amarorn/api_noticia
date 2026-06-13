"""Importação automática de CSV Superbet da pasta inbox do datalake.

Fluxo:
    1. Usuário exporta CSV na Superbet e salva em ``{LAKE_ROOT}/inbox/wallet/{user_id}/``
    2. ``scan_inbox()`` ou ``watch-wallet-csv`` detecta arquivos novos (hash SHA-256)
    3. Persiste em bronze e move para ``processed/``
    4. Opcionalmente dispara reconciliação

Idempotente: o mesmo arquivo (mesmo hash) não é importado duas vezes.
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import settings
from ingest.user_transactions.parser import parse_user_csv_file
from ingest.user_transactions.store import list_uploads, save_transactions_bronze

logger = logging.getLogger(__name__)

_REGISTRY_NAME = "_registry.json"


@dataclass
class InboxImportResult:
    """Resultado da importação de um CSV da inbox."""

    file_path: str
    upload_id: str | None = None
    n_rows: int = 0
    imported: bool = False
    skipped: bool = False
    reason: str | None = None
    bronze_path: str | None = None


@dataclass
class InboxScanResult:
    """Resumo de uma varredura da inbox."""

    user_id: str
    scanned_at: str
    imports: list[InboxImportResult] = field(default_factory=list)
    n_imported: int = 0
    n_skipped: int = 0
    reconciliation: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "scanned_at": self.scanned_at,
            "n_imported": self.n_imported,
            "n_skipped": self.n_skipped,
            "imports": [asdict(i) for i in self.imports],
            "reconciliation": self.reconciliation,
        }


def inbox_root(user_id: str | None = None) -> Path:
    """Raiz da inbox de carteira (``data/lake/inbox/wallet`` por padrão)."""
    base = Path(settings.lake_root) / settings.wallet_inbox_dir
    if user_id:
        return base / user_id
    return base


def _registry_path() -> Path:
    return inbox_root() / _REGISTRY_NAME


def _processed_dir(user_id: str) -> Path:
    return inbox_root(user_id) / "processed"


def _load_registry() -> dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return {"files": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"files": {}}
    data.setdefault("files", {})
    return data


def _save_registry(data: dict[str, Any]) -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _registry_key(user_id: str, sha: str) -> str:
    return f"{user_id}:{sha}"


def import_csv_file(
    path: Path,
    user_id: str,
    *,
    force: bool = False,
    move_to_processed: bool = True,
) -> InboxImportResult:
    """Importa um CSV para bronze se ainda não constar no registry."""
    path = path.resolve()
    if not path.is_file():
        return InboxImportResult(
            file_path=str(path),
            skipped=True,
            reason="arquivo_inexistente",
        )
    if path.suffix.lower() != ".csv":
        return InboxImportResult(
            file_path=str(path),
            skipped=True,
            reason="nao_e_csv",
        )

    sha = file_sha256(path)
    registry = _load_registry()
    reg_key = _registry_key(user_id, sha)
    if not force and reg_key in registry["files"]:
        prev = registry["files"][reg_key]
        return InboxImportResult(
            file_path=str(path),
            upload_id=prev.get("upload_id"),
            n_rows=int(prev.get("n_rows", 0)),
            skipped=True,
            reason="ja_importado",
        )

    rows = parse_user_csv_file(path, user_id, str(uuid.uuid4()))
    if not rows:
        return InboxImportResult(
            file_path=str(path),
            skipped=True,
            reason="csv_vazio_ou_invalido",
        )

    upload_id = str(uuid.uuid4())
    bronze_path = save_transactions_bronze(rows, user_id, upload_id)

    registry["files"][reg_key] = {
        "user_id": user_id,
        "sha256": sha,
        "upload_id": upload_id,
        "original_name": path.name,
        "n_rows": len(rows),
        "imported_at": datetime.now(UTC).isoformat(),
        "bronze_path": str(bronze_path),
    }
    _save_registry(registry)

    if move_to_processed:
        dest_dir = _processed_dir(user_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        dest = dest_dir / f"{ts}_{path.name}"
        shutil.move(str(path), str(dest))
        logger.info("wallet_inbox_movido", origem=str(path), destino=str(dest))

    logger.info(
        "wallet_inbox_importado",
        user_id=user_id,
        upload_id=upload_id,
        n_rows=len(rows),
        arquivo=path.name,
    )
    return InboxImportResult(
        file_path=str(path),
        upload_id=upload_id,
        n_rows=len(rows),
        imported=True,
        bronze_path=str(bronze_path),
    )


def list_pending_csvs(user_id: str) -> list[Path]:
    """CSV na inbox do usuário (exclui ``processed/``)."""
    folder = inbox_root(user_id)
    if not folder.exists():
        return []
    return sorted(
        p
        for p in folder.glob("*.csv")
        if p.is_file() and p.parent.name != "processed"
    )


def scan_inbox(user_id: str, *, reconcile: bool | None = None) -> InboxScanResult:
    """Varre a inbox, importa CSVs novos e opcionalmente reconcilia."""
    folder = inbox_root(user_id)
    folder.mkdir(parents=True, exist_ok=True)

    result = InboxScanResult(
        user_id=user_id,
        scanned_at=datetime.now(UTC).isoformat(),
    )

    for csv_path in list_pending_csvs(user_id):
        imp = import_csv_file(csv_path, user_id)
        result.imports.append(imp)
        if imp.imported:
            result.n_imported += 1
        elif imp.skipped:
            result.n_skipped += 1

    do_reconcile = (
        settings.wallet_inbox_auto_reconcile if reconcile is None else reconcile
    )
    if do_reconcile and (result.n_imported > 0 or _has_bronze_transactions(user_id)):
        try:
            from pipelines.user_bet_reconciliation import (
                reconcile_user_transactions,
                save_reconciliation,
            )

            df = reconcile_user_transactions(user_id)
            if not df.empty:
                rec_path = save_reconciliation(df, user_id)
                n_hi = int((df["match_confidence"].fillna(0) >= 0.7).sum())
                result.reconciliation = {
                    "n_pairs": len(df),
                    "n_high_confidence": n_hi,
                    "path": str(rec_path),
                }
            else:
                result.reconciliation = {"n_pairs": 0}
        except Exception as exc:
            logger.warning("wallet_inbox_reconcile_falhou: %s", exc)
            result.reconciliation = {"error": str(exc)}

    return result


def _has_bronze_transactions(user_id: str) -> bool:
    uploads = list_uploads(user_id)
    return bool(uploads)


def get_wallet_sync_status(user_id: str) -> dict[str, Any]:
    """Status da sincronização da carteira (último upload, CSV pendente na inbox)."""
    uploads = list_uploads(user_id)
    last_upload_at: str | None = None
    days_since_upload: float | None = None

    if uploads:
        last_raw = max(u.get("last_at") for u in uploads if u.get("last_at") is not None)
        if last_raw is not None:
            last_dt = _coerce_datetime(last_raw)
            if last_dt is not None:
                last_upload_at = last_dt.isoformat()
                delta = datetime.now(UTC) - last_dt
                days_since_upload = round(delta.total_seconds() / 86400, 2)

    pending = [p.name for p in list_pending_csvs(user_id)]
    stale = (
        days_since_upload is not None
        and days_since_upload > settings.wallet_inbox_stale_days
    )

    return {
        "user_id": user_id,
        "inbox_dir": str(inbox_root(user_id)),
        "pending_csv_files": pending,
        "n_pending": len(pending),
        "last_upload_at": last_upload_at,
        "days_since_upload": days_since_upload,
        "n_uploads": len(uploads),
        "stale": stale,
        "stale_threshold_days": settings.wallet_inbox_stale_days,
        "inbox_enabled": settings.wallet_inbox_enabled,
    }


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if hasattr(value, "to_pydatetime"):
        dt = value.to_pydatetime()
    elif isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        return pd_parse(value)
    else:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def pd_parse(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None


__all__ = [
    "InboxImportResult",
    "InboxScanResult",
    "file_sha256",
    "get_wallet_sync_status",
    "import_csv_file",
    "inbox_root",
    "list_pending_csvs",
    "scan_inbox",
]
