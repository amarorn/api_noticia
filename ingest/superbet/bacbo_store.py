"""Persistência bronze de rodadas Bac Bo capturadas pela extensão."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import settings
from ingest.superbet.bacbo_parser import BacboRoundRecord, extract_ws_message_types

MAX_ROUNDS_PER_TABLE = 300


def bacbo_store_path() -> Path:
    return settings.bronze_path / "superbet" / "bacbo" / "rounds.json"


def _empty_store() -> dict[str, Any]:
    return {"updated_at": None, "tables": {}}


def load_bacbo_store() -> dict[str, Any]:
    path = bacbo_store_path()
    if not path.exists():
        return _empty_store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty_store()
    if not isinstance(data, dict):
        return _empty_store()
    data.setdefault("tables", {})
    return data


def save_bacbo_store(data: dict[str, Any]) -> Path:
    path = bacbo_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(UTC).isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _stats_from_rounds(rounds: list[dict[str, Any]]) -> dict[str, int]:
    stats = {"player": 0, "banker": 0, "tie": 0, "total": len(rounds)}
    for row in rounds:
        w = row.get("winner")
        if w in stats:
            stats[w] += 1
    return stats


def append_bacbo_rounds(
    records: list[BacboRoundRecord],
    *,
    raw_messages: list[str] | None = None,
    ws_url: str | None = None,
) -> dict[str, Any]:
    """Anexa rodadas deduplicadas por round_id + table_id."""
    store = load_bacbo_store()
    debug = store.setdefault("debug", {"message_types": {}, "last_ws_url": None})

    if raw_messages:
        for msg_type, count in extract_ws_message_types(raw_messages).items():
            debug["message_types"][msg_type] = int(debug["message_types"].get(msg_type, 0)) + count
        if ws_url:
            debug["last_ws_url"] = ws_url

    if not records:
        save_bacbo_store(store)
        return {"inserted": 0, "store": store, "debug": debug}

    tables: dict[str, Any] = store.setdefault("tables", {})
    inserted = 0

    for rec in records:
        table = tables.setdefault(rec.table_id, {"rounds": [], "stats": {}})
        rounds: list[dict[str, Any]] = table.setdefault("rounds", [])
        existing_ids = {r.get("round_id") for r in rounds}
        if rec.round_id in existing_ids:
            continue
        row = rec.to_dict()
        row["captured_at"] = datetime.now(UTC).isoformat()
        rounds.append(row)
        inserted += 1
        if len(rounds) > MAX_ROUNDS_PER_TABLE:
            table["rounds"] = rounds[-MAX_ROUNDS_PER_TABLE:]
        table["stats"] = _stats_from_rounds(table["rounds"])

    save_bacbo_store(store)
    return {"inserted": inserted, "store": store, "debug": debug}


def list_bacbo_rounds(
    *,
    table_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    store = load_bacbo_store()
    tables: dict[str, Any] = store.get("tables") or {}
    if table_id:
        table = tables.get(table_id) or {"rounds": [], "stats": {}}
        rounds = list(reversed(table.get("rounds") or []))[:limit]
        return {
            "table_id": table_id,
            "count": len(rounds),
            "stats": table.get("stats") or _stats_from_rounds(table.get("rounds") or []),
            "rounds": rounds,
            "updated_at": store.get("updated_at"),
            "debug": store.get("debug"),
        }

    summary = []
    for tid, table in tables.items():
        stats = table.get("stats") or _stats_from_rounds(table.get("rounds") or [])
        summary.append(
            {
                "table_id": tid,
                "total_rounds": len(table.get("rounds") or []),
                "stats": stats,
            }
        )
    return {
        "tables": summary,
        "updated_at": store.get("updated_at"),
        "count": len(summary),
    }
