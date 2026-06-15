"""Persistência de apostas do usuário em JSON local (abertas + liquidadas)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from config import settings

def _user_bets_file() -> Path:
    return Path(settings.lake_root) / "user_open_bets.json"


def _settled_bets_file() -> Path:
    return Path(settings.lake_root) / "user_settled_bets.json"


class PickData(BaseModel):
    market: str
    outcome: str
    target_value: str | None = None
    model_prob: float | None = None
    market_odd: float | None = None
    expected_value: float | None = None
    edge_pp: float | None = None


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
    model_source: str | None = None
    combined_ev: float | None = None
    combined_prob: float | None = None
    proposal_minute: int | None = None
    register_minute: int | None = None

    def model_post_init(self, __context: Any) -> None:
        if not self.captured_at:
            self.captured_at = datetime.now().isoformat()


def _load_store() -> dict[str, Any]:
    path = _user_bets_file()
    if not path.exists():
        return {"version": 1, "bets": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_store(store: dict[str, Any]) -> None:
    path = _user_bets_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def add_open_bet(
    ub_kwargs: dict[str, Any],
    *,
    minute: int | None = None,
    skip_guardrails: bool = False,
) -> UserOpenBet:
    from models.bet_guardrails import validate_register_open_bet

    if not skip_guardrails:
        store = _load_store()
        picks = ub_kwargs.get("picks") or []
        validate_register_open_bet(
            existing_bets=store.get("bets", []),
            superbet_event_id=ub_kwargs.get("superbet_event_id"),
            home_team=str(ub_kwargs.get("home_team", "")),
            away_team=str(ub_kwargs.get("away_team", "")),
            picks=picks,
            bet_id=ub_kwargs.get("id"),
            minute=minute,
            stake=float(ub_kwargs.get("stake") or 0) or None,
            source=str(ub_kwargs.get("source") or ""),
        )

    store = _load_store()
    ub = UserOpenBet(**ub_kwargs)
    store["bets"].append(ub.model_dump(mode="json"))
    _save_store(store)
    return ub


def dedupe_open_bets_store() -> dict[str, int]:
    """Remove apostas abertas duplicadas (mesmo evento + mercado + palpite).

    Mantém o registro com ``ticket_code``; senão o ``captured_at`` mais recente.
    """
    from models.bet_guardrails import bet_market_fingerprint

    store = _load_store()
    bets: list[dict[str, Any]] = store.get("bets", [])
    open_indices: list[int] = [i for i, b in enumerate(bets) if b.get("status") == "open"]
    if not open_indices:
        return {"before": len(bets), "after": len(bets), "removed": 0}

    best_by_key: dict[tuple[Any, ...], int] = {}
    for idx in open_indices:
        b = bets[idx]
        picks = b.get("picks") or []
        if not picks:
            continue
        pk = picks[0]
        key = bet_market_fingerprint(
            superbet_event_id=b.get("superbet_event_id"),
            home_team=str(b.get("home_team", "")),
            away_team=str(b.get("away_team", "")),
            market=str(pk.get("market", "")),
            outcome=str(pk.get("outcome", "")),
        )
        prev_idx = best_by_key.get(key)
        if prev_idx is None:
            best_by_key[key] = idx
            continue
        prev = bets[prev_idx]
        prev_score = (1 if prev.get("ticket_code") else 0, str(prev.get("captured_at", "")))
        cur_score = (1 if b.get("ticket_code") else 0, str(b.get("captured_at", "")))
        if cur_score > prev_score:
            best_by_key[key] = idx

    keep_open = set(best_by_key.values())
    removed = 0
    new_bets: list[dict[str, Any]] = []
    for i, b in enumerate(bets):
        if b.get("status") == "open" and i not in keep_open:
            removed += 1
            continue
        new_bets.append(b)

    if removed:
        store["bets"] = new_bets
        _save_store(store)

    return {"before": len(bets), "after": len(new_bets), "removed": removed}


def list_open_bets(user_id: str | None = None) -> list[UserOpenBet]:
    store = _load_store()
    bets = [UserOpenBet(**b) for b in store.get("bets", [])]
    if user_id:
        bets = [b for b in bets if b.user_id == user_id]
    return [b for b in bets if b.status == "open"]


def list_combo_proposals(user_id: str | None = None) -> list[UserOpenBet]:
    """Propostas enviadas pelo frontend (ainda não apostadas na Superbet)."""
    store = _load_store()
    bets = [UserOpenBet(**b) for b in store.get("bets", [])]
    if user_id:
        bets = [b for b in bets if b.user_id == user_id]
    return [b for b in bets if b.status == "proposal"]


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


def move_open_to_settled(bet_id: str, settled_fields: dict[str, Any]) -> SettledBet | None:
    """Remove aposta aberta e registra em ``user_settled_bets.json``."""
    store = _load_store()
    bet_dict: dict[str, Any] | None = None
    remaining = []
    for b in store.get("bets", []):
        if b.get("id") == bet_id:
            bet_dict = b
        else:
            remaining.append(b)
    if not bet_dict:
        return None

    store["bets"] = remaining
    _save_store(store)

    payload = {**bet_dict, **settled_fields}
    payload.setdefault("placed_at", bet_dict.get("captured_at", ""))
    return add_settled_bet(payload)


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
    path = _settled_bets_file()
    if not path.exists():
        return {"version": 1, "bets": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_settled_store(store: dict[str, Any]) -> None:
    path = _settled_bets_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
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
