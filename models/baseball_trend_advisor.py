"""Copiloto de tendência in-play para beisebol (reutiliza wc_trend_advisor).

Normaliza ticks bronze Superbet (entrada + runs + ML/total) para GameTick e
delega detecção de fluxo a ``analyze_position``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from config import settings
from models.wc_trend_advisor import GameTick, analyze_position, trend_report_to_dict

logger = logging.getLogger(__name__)


def parse_baseball_tick(raw: dict[str, Any]) -> GameTick:
    """Converte snapshot bronze de beisebol em GameTick (runs tratadas como total_goals)."""
    inplay = raw.get("inplay") or {}
    home_score = int(inplay.get("home_score") or 0)
    away_score = int(inplay.get("away_score") or 0)
    inning = int(inplay.get("minute") or 1)
    # Heurística: 9 entradas ≈ 90' do futebol para limiares do trend advisor.
    effective_minute = max(inning, 1) * 10

    over_implied: dict[str, float] = {}
    totals_imp = raw.get("total_points_implied") or raw.get("totals_implied") or {}
    for line, probs in totals_imp.items():
        if not isinstance(probs, dict):
            continue
        for key, val in probs.items():
            key_l = str(key).lower()
            if "mais" in key_l or "over" in key_l:
                over_implied[str(line)] = float(val)

    h2h_imp = raw.get("moneyline_implied") or raw.get("h2h_implied") or {}

    return GameTick(
        minute=effective_minute,
        home_score=home_score,
        away_score=away_score,
        total_goals=home_score + away_score,
        over_implied=over_implied,
        h2h_implied={str(k): float(v) for k, v in h2h_imp.items()},
        markets_open=int(raw.get("raw_market_count") or 0),
        captured_at=str(raw.get("captured_at") or ""),
    )


def load_baseball_event_ticks(event_dir: Path) -> list[GameTick]:
    """Carrega ticks cronológicos do diretório bronze do evento."""
    ticks: list[GameTick] = []
    if not event_dir.is_dir():
        return ticks
    for path in sorted(event_dir.glob("2*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            ticks.append(parse_baseball_tick(raw))
        except Exception as exc:
            logger.warning("Erro ao ler tick beisebol %s: %s", path.name, exc)
    return ticks


def _normalize_baseball_bet_for_trend(user_bet: dict[str, Any]) -> dict[str, Any]:
    """Mapeia mercados de beisebol para o vocabulário do trend advisor."""
    picks = list(user_bet.get("picks") or [])
    if not picks and user_bet.get("market"):
        picks = [{"market": user_bet["market"], "outcome": user_bet.get("outcome", "")}]

    normalized: list[dict[str, str]] = []
    for pick in picks:
        market = str(pick.get("market") or "")
        outcome = str(pick.get("outcome") or "")
        if market in {"moneyline", "h2h", "f5_moneyline"}:
            normalized.append({"market": "h2h", "outcome": outcome})
        elif market in {"total_runs", "f5_total", "inning_total", "team_total_runs"}:
            if outcome.startswith("over"):
                normalized.append({"market": "totals_ft", "outcome": "over"})
            elif outcome.startswith("under"):
                normalized.append({"market": "totals_ft", "outcome": "under"})
            else:
                normalized.append({"market": market, "outcome": outcome})
        else:
            normalized.append({"market": market, "outcome": outcome})

    return {**user_bet, "picks": normalized}


def build_baseball_trend_report(
    *,
    event_id: int,
    home_team: str,
    away_team: str,
    user_bet: dict[str, Any] | None,
    event_snapshot_raw: dict[str, Any],
) -> dict[str, Any] | None:
    """Analisa tendência do jogo vs aposta aberta (mínimo 2 ticks)."""
    event_dir = Path(settings.lake_root) / "bronze" / "superbet" / "events" / str(event_id)
    ticks = load_baseball_event_ticks(event_dir)
    if len(ticks) < 2:
        return None

    bet_payload: dict[str, Any] = {"picks": []}
    if user_bet:
        bet_payload = _normalize_baseball_bet_for_trend(user_bet)
    else:
        try:
            from api.user_bets_store import get_bets_for_event

            open_bets = get_bets_for_event(home_team, away_team, status="open")
            if open_bets:
                bet_payload = _normalize_baseball_bet_for_trend(open_bets[0])
        except Exception as exc:
            logger.debug("baseball_trend_open_bets_skip: %s", exc)

    report = analyze_position(bet_payload, ticks, event_snapshot_raw, sport="baseball")
    return trend_report_to_dict(report)


__all__ = [
    "build_baseball_trend_report",
    "load_baseball_event_ticks",
    "parse_baseball_tick",
]
