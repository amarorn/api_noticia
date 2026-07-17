"""Parser de mensagens WebSocket Evolution Bac Bo."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

_WINNER_KEYS = ("winner", "result", "winSpot", "winspot", "outcome", "winningSpot", "winningSpots")
_SCORE_KEYS = (
    ("playerScore", "bankerScore"),
    ("player_score", "banker_score"),
    ("playerTotal", "bankerTotal"),
)
_DICE_KEYS = (("playerDice", "bankerDice"), ("player_dice", "banker_dice"))
_ROUND_ID_KEYS = ("gameId", "game_id", "id", "roundId", "round_id", "gameNumber")
_HISTORY_KEYS = ("history", "results", "pastResults", "recentResults", "items", "entries")


@dataclass(frozen=True)
class BacboRoundRecord:
    round_id: str
    table_id: str
    winner: str  # player | banker | tie
    player_score: int | None = None
    banker_score: int | None = None
    msg_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_id": self.round_id,
            "table_id": self.table_id,
            "winner": self.winner,
            "player_score": self.player_score,
            "banker_score": self.banker_score,
            "msg_type": self.msg_type,
        }


def normalize_bacbo_winner(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"player", "p", "jogador", "blue"}:
        return "player"
    if text in {"banker", "b", "banca", "red"}:
        return "banker"
    if text in {"tie", "t", "empate", "green"}:
        return "tie"
    return None


def extract_instance_from_ws_url(url: str) -> str | None:
    match = re.search(r"[?&]instance=([^&]+)", url or "", re.I)
    return match.group(1) if match else None


def extract_ws_message_types(raw_messages: list[str]) -> dict[str, int]:
    """Conta tipos de mensagem WS (diagnóstico quando parse não extrai rodadas)."""
    counts: dict[str, int] = {}
    for raw in raw_messages:
        text = (raw or "").strip()
        if not text or text[0] not in "{[":
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            counts["<invalid_json>"] = counts.get("<invalid_json>", 0) + 1
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            msg_type = str(item.get("type") or item.get("event") or "<sem_tipo>")
            counts[msg_type] = counts.get(msg_type, 0) + 1
    return counts


def _sum_dice(values: Any) -> int | None:
    if not isinstance(values, list) or not values:
        return None
    total = 0
    for item in values:
        if isinstance(item, dict):
            val = _as_int(item.get("value") or item.get("face") or item.get("dice"))
        else:
            val = _as_int(item)
        if val is None:
            return None
        total += val
    return total


def _winner_from_node(node: dict[str, Any]) -> str | None:
    for key in _WINNER_KEYS:
        raw = node.get(key)
        if raw is None:
            continue
        if key == "winningSpots" and isinstance(raw, list) and raw:
            winner = normalize_bacbo_winner(raw[0])
            if winner:
                return winner
        if key == "result" and isinstance(raw, dict):
            nested = _winner_from_node(raw)
            if nested:
                return nested
        winner = normalize_bacbo_winner(raw)
        if winner:
            return winner
    return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _scores_from_node(node: dict[str, Any]) -> tuple[int | None, int | None]:
    for pk, bk in _SCORE_KEYS:
        ps = _as_int(node.get(pk))
        bs = _as_int(node.get(bk))
        if ps is not None or bs is not None:
            return ps, bs
    for pk, bk in _DICE_KEYS:
        ps = _sum_dice(node.get(pk))
        bs = _sum_dice(node.get(bk))
        if ps is not None or bs is not None:
            return ps, bs
    dice = node.get("dice") or node.get("dices")
    if isinstance(dice, dict):
        ps = _as_int(dice.get("player") or dice.get("playerTotal"))
        bs = _as_int(dice.get("banker") or dice.get("bankerTotal"))
        if ps is not None or bs is not None:
            return ps, bs
    return None, None


def extract_table_id_from_ws_url(url: str) -> str | None:
    match = re.search(r"/game/([^/?]+)/socket", url or "", re.I)
    return match.group(1) if match else None


def _round_id_from_node(node: dict[str, Any], fallback: str) -> str:
    for key in _ROUND_ID_KEYS:
        val = node.get(key)
        if val is not None and str(val).strip():
            return str(val)
    ps, bs = _scores_from_node(node)
    winner = _winner_from_node(node)
    parts = [fallback, winner or "?", str(ps), str(bs)]
    return "|".join(parts)


def _round_from_node(
    node: dict[str, Any],
    *,
    table_id: str,
    msg_type: str | None,
    fallback_idx: int,
) -> BacboRoundRecord | None:
    ps, bs = _scores_from_node(node)
    winner = _winner_from_node(node)
    if winner is None:
        return None
    round_id = _round_id_from_node(node, f"{table_id}-{fallback_idx}")
    return BacboRoundRecord(
        round_id=round_id,
        table_id=table_id,
        winner=winner,
        player_score=ps,
        banker_score=bs,
        msg_type=msg_type,
    )


def _walk_for_rounds(
    node: Any,
    *,
    table_id: str,
    msg_type: str | None,
    out: list[BacboRoundRecord],
    seen: set[str],
    depth: int = 0,
) -> None:
    if depth > 8:
        return
    if isinstance(node, list):
        for idx, item in enumerate(node):
            _walk_for_rounds(
                item,
                table_id=table_id,
                msg_type=msg_type,
                out=out,
                seen=seen,
                depth=depth + 1,
            )
        return
    if not isinstance(node, dict):
        return

    winner_present = _winner_from_node(node) is not None
    if winner_present:
        rec = _round_from_node(node, table_id=table_id, msg_type=msg_type, fallback_idx=len(out))
        if rec and rec.round_id not in seen:
            seen.add(rec.round_id)
            out.append(rec)

    for key in _HISTORY_KEYS:
        child = node.get(key)
        if isinstance(child, list):
            for idx, item in enumerate(child):
                if isinstance(item, dict):
                    rec = _round_from_node(
                        item,
                        table_id=table_id,
                        msg_type=msg_type,
                        fallback_idx=len(out) + idx,
                    )
                    if rec and rec.round_id not in seen:
                        seen.add(rec.round_id)
                        out.append(rec)

    args = node.get("args")
    if isinstance(args, dict):
        _walk_for_rounds(
            args,
            table_id=table_id,
            msg_type=msg_type,
            out=out,
            seen=seen,
            depth=depth + 1,
        )

    game = node.get("game")
    if isinstance(game, dict):
        _walk_for_rounds(
            game,
            table_id=table_id,
            msg_type=msg_type,
            out=out,
            seen=seen,
            depth=depth + 1,
        )

    for key, child in node.items():
        if key in {"args", "game"}:
            continue
        if isinstance(child, (dict, list)):
            _walk_for_rounds(
                child,
                table_id=table_id,
                msg_type=msg_type,
                out=out,
                seen=seen,
                depth=depth + 1,
            )


def parse_bacbo_ws_payload(
    raw: str,
    *,
    table_id: str = "",
    ws_url: str = "",
) -> list[BacboRoundRecord]:
    """Extrai rodadas Bac Bo de uma mensagem WebSocket (JSON)."""
    resolved_table = table_id or extract_table_id_from_ws_url(ws_url) or "unknown"
    text = (raw or "").strip()
    if not text or text[0] not in "{[":
        return []

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []

    messages: list[Any]
    if isinstance(payload, list):
        messages = payload
    else:
        messages = [payload]

    out: list[BacboRoundRecord] = []
    seen: set[str] = set()
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        msg_type = str(msg.get("type") or msg.get("event") or "")
        _walk_for_rounds(
            msg,
            table_id=resolved_table,
            msg_type=msg_type or None,
            out=out,
            seen=seen,
        )
    return out


def parse_bacbo_ws_batch(
    messages: list[str],
    *,
    table_id: str = "",
    ws_url: str = "",
) -> list[BacboRoundRecord]:
    """Parseia lote de mensagens WS deduplicando por round_id."""
    merged: list[BacboRoundRecord] = []
    seen: set[str] = set()
    for raw in messages:
        for rec in parse_bacbo_ws_payload(raw, table_id=table_id, ws_url=ws_url):
            if rec.round_id in seen:
                continue
            seen.add(rec.round_id)
            merged.append(rec)
    return merged
