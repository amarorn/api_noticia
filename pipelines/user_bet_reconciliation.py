"""Reconciliação de transações do usuário com snapshots dos eventos Superbet.

Para cada `bilhete colocado` (in-play), procura o snapshot mais próximo em
`data/lake/bronze/superbet/events/<event_id>/<timestamp>.json` dentro de uma
janela temporal, e calcula:
- match_confidence (0-1): qualidade do match
- inferred_market: qual mercado o bilhete provavelmente atinge
- model_prob_*: probabilidades do modelo no momento da aposta
- won (se há `valor ganhado` correspondente)

Output: silver_bet_reconciliation.parquet
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from config import settings
from ingest.user_transactions.store import load_transactions

# Janela máxima de busca por snapshot
MATCH_WINDOW_SECONDS = 180  # ±3 min
TS_FILENAME_RE = re.compile(r"(\d{8}T\d{6}Z)\.json$")


def _events_root() -> Path:
    return Path(settings.lake_root) / "bronze" / "superbet" / "events"


def _silver_root() -> Path:
    p = Path(settings.lake_root) / "silver" / "bet_reconciliation"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _parse_snapshot_timestamp(filename: str) -> datetime | None:
    """Extrai o timestamp do nome do arquivo: 20260609T064127Z.json → datetime."""
    m = TS_FILENAME_RE.search(filename)
    if not m:
        return None
    raw = m.group(1)
    return datetime.strptime(raw, "%Y%m%dT%H%M%SZ")


@dataclass
class SnapshotRef:
    """Referência para um snapshot indexado em memória."""

    event_id: int
    path: Path
    timestamp: datetime
    home_team: str
    away_team: str
    is_live: bool
    minute: int | None = None
    home_score: int | None = None
    away_score: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)


def index_event_snapshots() -> list[SnapshotRef]:
    """Lê todos os snapshots em bronze/superbet/events/ e indexa por timestamp."""
    root = _events_root()
    refs: list[SnapshotRef] = []
    if not root.exists():
        return refs

    for event_dir in root.iterdir():
        if not event_dir.is_dir():
            continue
        try:
            event_id = int(event_dir.name)
        except ValueError:
            continue

        for snap_file in event_dir.glob("*.json"):
            ts = _parse_snapshot_timestamp(snap_file.name)
            if ts is None:
                continue
            try:
                payload = json.loads(snap_file.read_text(encoding="utf-8"))
            except Exception:
                continue

            inplay = payload.get("inplay") or {}
            ref = SnapshotRef(
                event_id=event_id,
                path=snap_file,
                timestamp=ts,
                home_team=payload.get("home_team", ""),
                away_team=payload.get("away_team", ""),
                is_live=bool(payload.get("is_live")),
                minute=inplay.get("minute"),
                home_score=inplay.get("home_score"),
                away_score=inplay.get("away_score"),
                payload=payload,
            )
            refs.append(ref)

    refs.sort(key=lambda r: r.timestamp)
    return refs


@dataclass
class MatchResult:
    """Resultado da tentativa de match de uma aposta com snapshots."""

    matched: bool
    snapshot: SnapshotRef | None = None
    delta_seconds: float | None = None
    confidence: float = 0.0
    candidates_considered: int = 0


def find_snapshot_for_bet(
    bet_at_local: datetime,
    snapshots: list[SnapshotRef],
    *,
    window_seconds: int = MATCH_WINDOW_SECONDS,
    expected_home_team: str | None = None,
    expected_away_team: str | None = None,
) -> MatchResult:
    """Busca o snapshot in-play mais próximo da hora da aposta.

    Args:
        bet_at_local: timestamp da aposta (CSV usa horário local BR; snapshots usam UTC).
                      A diferença é tratada via janela ±window_seconds + tolerância de fuso.
        snapshots: lista pré-indexada e ordenada por timestamp.
        window_seconds: janela de busca em segundos.
        expected_*: nomes opcionais para boost de confidence.

    Returns:
        MatchResult com o melhor candidato.
    """
    if not snapshots:
        return MatchResult(matched=False)

    # CSV vem em horário local BR (UTC-3); snapshots em UTC.
    # Converter bet_at para UTC.
    bet_at_utc = bet_at_local + timedelta(hours=3)

    candidates = []
    for snap in snapshots:
        if not snap.is_live:
            continue
        delta = abs((snap.timestamp - bet_at_utc).total_seconds())
        if delta > window_seconds:
            continue
        candidates.append((delta, snap))

    if not candidates:
        return MatchResult(matched=False, candidates_considered=0)

    # Score: 1.0 quando delta=0; cai linearmente até 0.5 no limite da janela
    best_delta, best_snap = min(candidates, key=lambda x: x[0])
    base_conf = 1.0 - 0.5 * (best_delta / window_seconds)

    # Boost se nomes batem
    name_boost = 0.0
    if expected_home_team:
        if expected_home_team.lower() in best_snap.home_team.lower():
            name_boost += 0.1
    if expected_away_team:
        if expected_away_team.lower() in best_snap.away_team.lower():
            name_boost += 0.1

    confidence = min(1.0, base_conf + name_boost)
    return MatchResult(
        matched=True,
        snapshot=best_snap,
        delta_seconds=best_delta,
        confidence=confidence,
        candidates_considered=len(candidates),
    )


def pair_placed_with_outcome(
    df_tx: pd.DataFrame,
    *,
    pair_window_minutes: int = 240,
) -> list[dict]:
    """Empareia 'bilhete colocado' → 'valor ganhado' (heurística por proximidade).

    Como o CSV não tem ticket_code direto, atribui o `valor ganhado` mais próximo
    posterior à aposta colocada, dentro de uma janela de horas.

    Args:
        df_tx: DataFrame de transações.
        pair_window_minutes: janela máxima entre colocada e ganho.

    Returns:
        Lista de dicts com {placed_at, stake, won_at, won_amount, won}.
    """
    if df_tx.empty:
        return []

    placed = df_tx[df_tx["transaction_type"] == "bilhete colocado"].copy()
    won = df_tx[df_tx["transaction_type"] == "valor ganhado"].copy()
    cancelled = df_tx[df_tx["transaction_type"] == "bilhete cancelado"]

    # Identificar bilhetes cancelados por proximidade (mesmo timestamp ±2s)
    cancelled_keys = set()
    if not cancelled.empty:
        for _, c in cancelled.iterrows():
            for idx, p in placed.iterrows():
                if abs((c["transaction_at"] - p["transaction_at"]).total_seconds()) < 5:
                    if abs(c["amount"] - p["amount"]) < 0.01:
                        cancelled_keys.add(idx)

    pairs = []
    used_won = set()

    for idx, p in placed.iterrows():
        if idx in cancelled_keys:
            continue
        placed_at = p["transaction_at"]
        stake = float(p["amount"])
        game = p.get("game_name", "")

        if "INPLAY" not in (game or "").upper():
            continue

        window_end = placed_at + timedelta(minutes=pair_window_minutes)
        candidates = won[
            (won["transaction_at"] > placed_at)
            & (won["transaction_at"] < window_end)
            & (~won.index.isin(used_won))
        ].sort_values("transaction_at")

        won_amount = 0.0
        won_at = None
        if not candidates.empty:
            first = candidates.iloc[0]
            won_amount = float(first["amount"])
            won_at = first["transaction_at"]
            used_won.add(candidates.index[0])

        pairs.append({
            "placed_at": placed_at,
            "stake": stake,
            "game_name": game,
            "won_at": won_at,
            "won_amount": won_amount,
            "won": won_amount > 0,
            "user_id": p.get("user_id"),
            "upload_id": p.get("upload_id"),
        })

    return pairs


def reconcile_user_transactions(
    user_id: str,
    *,
    snapshots: list[SnapshotRef] | None = None,
) -> pd.DataFrame:
    """Pipeline ponta-a-ponta: lê transações + snapshots + gera silver.

    Args:
        user_id: usuário para reconciliar.
        snapshots: snapshots pré-indexados (opcional, se None lê do bronze).

    Returns:
        DataFrame com a tabela de reconciliação.
    """
    df_tx = load_transactions(user_id)
    if df_tx.empty:
        return pd.DataFrame()

    if snapshots is None:
        snapshots = index_event_snapshots()

    pairs = pair_placed_with_outcome(df_tx)

    rows = []
    for pair in pairs:
        bet_at = pair["placed_at"]
        match = find_snapshot_for_bet(bet_at, snapshots)

        row: dict[str, Any] = {
            "placed_at": bet_at,
            "won_at": pair["won_at"],
            "stake": pair["stake"],
            "won_amount": pair["won_amount"],
            "won": pair["won"],
            "pnl": pair["won_amount"] - pair["stake"],
            "user_id": pair["user_id"],
            "upload_id": pair["upload_id"],
            "match_confidence": match.confidence,
            "match_delta_seconds": match.delta_seconds,
            "candidates_considered": match.candidates_considered,
        }

        if match.matched and match.snapshot:
            snap = match.snapshot
            payload = snap.payload
            generosity = payload.get("generosity_probs") or {}
            row.update({
                "event_id": snap.event_id,
                "snapshot_path": str(snap.path),
                "match_minute": snap.minute,
                "home_team": snap.home_team,
                "away_team": snap.away_team,
                "home_score": snap.home_score,
                "away_score": snap.away_score,
                "model_generosity_home": generosity.get("home"),
                "model_generosity_away": generosity.get("away"),
            })
        else:
            row.update({
                "event_id": None,
                "snapshot_path": None,
                "match_minute": None,
                "home_team": None,
                "away_team": None,
                "home_score": None,
                "away_score": None,
                "model_generosity_home": None,
                "model_generosity_away": None,
            })
        rows.append(row)

    return pd.DataFrame(rows)


def save_reconciliation(df: pd.DataFrame, user_id: str) -> Path:
    """Persiste a tabela de reconciliação em silver/bet_reconciliation/."""
    out = _silver_root() / f"reconciliation_{user_id}.parquet"
    df.to_parquet(out, index=False)
    return out


def load_reconciliation(user_id: str) -> pd.DataFrame:
    """Lê a tabela de reconciliação salva (ou retorna vazio)."""
    path = _silver_root() / f"reconciliation_{user_id}.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)
