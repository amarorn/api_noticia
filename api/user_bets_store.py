"""Persistência de apostas do usuário em JSON local (abertas + liquidadas)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from config import settings

_USER_BETS_FILE = Path(settings.lake_root) / "user_open_bets.json"
_SETTLED_BETS_FILE = Path(settings.lake_root) / "user_settled_bets.json"


class PickData(BaseModel):
    market: str
    outcome: str
    target_value: str | None = None


class UserOpenBet(BaseModel):
    id: str
    event_name: str
    home_team: str
    away_team: str
    picks: list[PickData]
    stake: float
    odds_placed: float
    potential_return: float
    cashout_value: float | None = None
    ticket_code: str | None = None
    status: str = "open"
    source: str = "manual"
    captured_at: str = ""
    superbet_event_id: int | None = None
    user_id: str | None = None

    def model_post_init(self, __context: Any) -> None:
        if not self.captured_at:
            self.captured_at = datetime.now().isoformat()


def _load_store() -> dict[str, Any]:
    if not _USER_BETS_FILE.exists():
        return {"version": 1, "bets": []}
    return json.loads(_USER_BETS_FILE.read_text(encoding="utf-8"))


def _save_store(store: dict[str, Any]) -> None:
    _USER_BETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _USER_BETS_FILE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def add_open_bet(ub_kwargs: dict[str, Any]) -> UserOpenBet:
    store = _load_store()
    ub = UserOpenBet(**ub_kwargs)
    store["bets"].append(ub.model_dump(mode="json"))
    _save_store(store)
    return ub


def list_open_bets(user_id: str | None = None) -> list[UserOpenBet]:
    store = _load_store()
    bets = [UserOpenBet(**b) for b in store.get("bets", [])]
    if user_id:
        bets = [b for b in bets if b.user_id == user_id]
    return [b for b in bets if b.status == "open"]


def find_open_bet(bet_id: str) -> UserOpenBet | None:
    store = _load_store()
    for b in store.get("bets", []):
        if b.get("id") == bet_id:
            return UserOpenBet(**b)
    return None


def update_bet_status(bet_id: str, status: str) -> bool:
    store = _load_store()
    for b in store.get("bets", []):
        if b.get("id") == bet_id:
            b["status"] = status
            _save_store(store)
            return True
    return False


def get_bets_for_event(
    home_team: str,
    away_team: str,
    *,
    status: str = "open",
) -> list[dict]:
    """Retorna apostas do evento filtradas por time, já deduplicadas.

    Deduplicação: mesmo stake + odds + market + outcome = duplicata de captura repetida.
    """
    store = _load_store()
    all_bets = store.get("bets", [])

    home_lower = home_team.lower()
    away_lower = away_team.lower()

    relevant = []
    for b in all_bets:
        if status and b.get("status") != status:
            continue
        event = (b.get("event_name") or "").lower()
        b_home = (b.get("home_team") or "").lower()
        b_away = (b.get("away_team") or "").lower()
        # Match flexível por substring nos times ou event_name
        match = (
            (home_lower in b_home or home_lower in event)
            and (away_lower in b_away or away_lower in event)
        )
        if match:
            relevant.append(b)

    # Deduplicar por (stake, odds, market, outcome)
    seen: set[tuple] = set()
    unique: list[dict] = []
    for b in relevant:
        picks = b.get("picks") or []
        key = (
            b.get("stake"),
            b.get("odds_placed"),
            picks[0].get("market") if picks else "",
            picks[0].get("outcome") if picks else "",
        )
        if key not in seen:
            seen.add(key)
            unique.append(b)

    return unique


# ──────────────────────────────────────────────────────────────────────
# Apostas liquidadas (histórico de resultados)
# ──────────────────────────────────────────────────────────────────────

class SettledBet(BaseModel):
    """Aposta finalizada com resultado conhecido."""

    id: str
    event_name: str
    home_team: str
    away_team: str
    picks: list[PickData]
    stake: float
    odds_placed: float
    potential_return: float
    result: str  # "won" | "lost" | "cashout" | "void"
    profit: float  # ganho líquido (negativo se perdeu)
    cashout_value: float | None = None
    ticket_code: str | None = None
    source: str = "superbet_extension"
    placed_at: str = ""  # quando apostou
    settled_at: str = ""  # quando encerrou
    superbet_event_id: int | None = None
    final_score: str | None = None  # "2x0", "1x1", etc.


def _load_settled_store() -> dict[str, Any]:
    if not _SETTLED_BETS_FILE.exists():
        return {"version": 1, "bets": []}
    return json.loads(_SETTLED_BETS_FILE.read_text(encoding="utf-8"))


def _save_settled_store(store: dict[str, Any]) -> None:
    _SETTLED_BETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SETTLED_BETS_FILE.write_text(
        json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_settled_bet(bet_data: dict[str, Any]) -> SettledBet:
    """Adiciona uma aposta liquidada ao histórico."""
    store = _load_settled_store()
    bet = SettledBet(**bet_data)
    # Deduplicar: se já existe com mesmo ticket_code ou id, não inserir
    existing_ids = {b.get("id") for b in store.get("bets", [])}
    existing_tickets = {
        b.get("ticket_code") for b in store.get("bets", []) if b.get("ticket_code")
    }
    if bet.id in existing_ids:
        return bet
    if bet.ticket_code and bet.ticket_code in existing_tickets:
        return bet
    store["bets"].append(bet.model_dump(mode="json"))
    _save_settled_store(store)
    return bet


def add_settled_bets_batch(bets_data: list[dict[str, Any]]) -> int:
    """Adiciona múltiplas apostas liquidadas de uma vez. Retorna quantas novas."""
    store = _load_settled_store()
    existing_ids = {b.get("id") for b in store.get("bets", [])}
    existing_tickets = {
        b.get("ticket_code") for b in store.get("bets", []) if b.get("ticket_code")
    }
    added = 0
    for data in bets_data:
        try:
            bet = SettledBet(**data)
        except Exception:
            continue
        if bet.id in existing_ids:
            continue
        if bet.ticket_code and bet.ticket_code in existing_tickets:
            continue
        store["bets"].append(bet.model_dump(mode="json"))
        existing_ids.add(bet.id)
        if bet.ticket_code:
            existing_tickets.add(bet.ticket_code)
        added += 1
    if added:
        _save_settled_store(store)
    return added


def list_settled_bets() -> list[SettledBet]:
    """Lista todas as apostas liquidadas."""
    store = _load_settled_store()
    return [SettledBet(**b) for b in store.get("bets", [])]
