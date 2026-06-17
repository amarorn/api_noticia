"""Persistência bronze Superbet + merge em odds de mercado."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from config import settings
from ingest.superbet.client import SuperbetClient, SuperbetClientError
from ingest.superbet.parser import SuperbetEventSnapshot
from schemas.national_teams import normalize_national_team

logger = logging.getLogger(__name__)

DEFAULT_SUPERBET_ODDS = Path("data/rounds/superbet_odds.json")


def superbet_bronze_dir() -> Path:
    return settings.bronze_path / "superbet" / "events"


def save_event_snapshot(snapshot: SuperbetEventSnapshot) -> Path:
    base = superbet_bronze_dir() / str(snapshot.event_id)
    base.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    history = base / f"{ts}.json"
    history.write_text(
        json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    latest = base / "latest.json"
    latest.write_text(history.read_text(encoding="utf-8"), encoding="utf-8")
    return history


def load_latest_snapshot(event_id: int) -> SuperbetEventSnapshot | None:
    path = superbet_bronze_dir() / str(event_id) / "latest.json"
    if not path.exists():
        return None
    from ingest.superbet.parser import parse_superbet_event

    data = json.loads(path.read_text(encoding="utf-8"))
    return parse_superbet_event(_snapshot_to_raw_event(data))


def fetch_event_with_stale_fallback(
    client: SuperbetClient,
    event_id: int,
) -> tuple[SuperbetEventSnapshot, bool]:
    """Busca evento na Superbet; em falha de rede usa bronze ``latest.json``."""
    try:
        return client.fetch_event(event_id), False
    except SuperbetClientError as exc:
        stale = load_latest_snapshot(event_id)
        if stale is None:
            raise
        logger.warning(
            "superbet_fetch_using_stale_snapshot event_id=%s: %s",
            event_id,
            exc,
        )
        return stale, True


def _snapshot_to_raw_event(data: dict) -> dict:
    """Reconstrói estrutura mínima para re-parse (cache local)."""
    inplay = data.get("inplay")
    periods = []
    if inplay and inplay.get("ht_home_score") is not None:
        periods.append({
            "num": 1,
            "home_team_score": str(inplay["ht_home_score"]),
            "away_team_score": str(inplay["ht_away_score"]),
        })
    return {
        "event_id": data["event_id"],
        "fixture": {
            "event_name": data["event_name"],
            "utc_date": data.get("utc_date"),
            "betradar_id": data.get("betradar_id"),
            "event_tags": "superLive" if data.get("is_live") else "",
        },
        "inplay_stats": None if not inplay else {
            "home_team_score": str(inplay["home_score"]),
            "away_team_score": str(inplay["away_score"]),
            "minutes": str(inplay["minute"]),
            "stoppage_time": inplay.get("stoppage_time"),
            "home_team_corners": str(inplay.get("home_corners", 0)),
            "away_team_corners": str(inplay.get("away_corners", 0)),
            "home_team_yellow_cards": str(inplay.get("home_yellow_cards", 0)),
            "away_team_yellow_cards": str(inplay.get("away_yellow_cards", 0)),
            "periods": periods,
        },
        "inplay_stats_metadata": {
            "event_status_label": inplay.get("period_label") if inplay else None,
            "status": inplay.get("status") if inplay else None,
        },
        "markets": _markets_from_snapshot(data),
    }


def _markets_from_snapshot(data: dict) -> list[dict]:
    markets: list[dict] = []
    h2h = data.get("h2h_odds") or {}
    if h2h:
        markets.append({
            "name": "Resultado Final",
            "odds": [
                {
                    "price": h2h.get(k),
                    "metadata": {
                        "name": k,
                        "extra": data.get("generosity_probs") or {},
                    },
                }
                for k in ("1", "X", "2")
                if k in h2h
            ],
        })
    totals = data.get("totals") or {}
    if totals:
        odds = []
        for line, outcomes in totals.items():
            for name, price in outcomes.items():
                odds.append({
                    "price": price,
                    "metadata": {"name": name, "special_bet_value": line},
                })
        markets.append({"name": "Total de Gols", "odds": odds})
    corners = data.get("corners") or {}
    if corners:
        odds = []
        for line, outcomes in corners.items():
            for name, price in outcomes.items():
                odds.append({
                    "price": price,
                    "metadata": {"name": name, "special_bet_value": line},
                })
        markets.append({"name": "Total de Escanteios", "odds": odds})
    return markets


def merge_snapshot_into_odds_file(
    snapshot: SuperbetEventSnapshot,
    output_path: Path | None = None,
) -> Path:
    path = output_path or DEFAULT_SUPERBET_ODDS
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {
            "source": "superbet",
            "competition": "mixed",
            "matches": [],
        }

    home = normalize_national_team(snapshot.home_team)
    away = normalize_national_team(snapshot.away_team)
    if not snapshot.h2h_odds:
        return path

    entry = {
        "home_team": home,
        "away_team": away,
        "phase": "friendly" if snapshot.is_live else "group",
        "bookmaker": "superbet",
        "commence_time": snapshot.utc_date,
        "superbet_event_id": snapshot.event_id,
        "betradar_id": snapshot.betradar_id,
        "odds": {k: round(v, 3) for k, v in snapshot.h2h_odds.items()},
        "implied": {k: round(v, 4) for k, v in snapshot.h2h_implied.items()},
        "totals_implied": snapshot.totals_implied,
        "corners_implied": snapshot.corners_implied,
        "captured_at": snapshot.captured_at,
    }

    matches = data.get("matches") or []
    key = f"{home.casefold()}|{away.casefold()}"
    updated = False
    for i, row in enumerate(matches):
        row_key = f"{normalize_national_team(row['home_team']).casefold()}|{normalize_national_team(row['away_team']).casefold()}"
        if row_key == key:
            matches[i] = entry
            updated = True
            break
    if not updated:
        matches.append(entry)

    data["matches"] = matches
    data["captured_at"] = datetime.now(timezone.utc).isoformat()
    data["source"] = "superbet"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
