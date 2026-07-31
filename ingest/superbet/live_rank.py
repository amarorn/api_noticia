"""Ranking ao vivo — prioriza clubes BR e jogos com edge modelado."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd

from ingest.superbet.live_ticks import live_ticks_path
from ingest.superbet.parser import SuperbetLiveEventSummary
from ingest.superbet.team_resolver import classify_live_match, is_wc_national_team

# Reexport para compatibilidade de testes/frontend legado.
__all__ = [
    "LiveBetRank",
    "is_wc_national_team",
    "rank_live_event",
    "rank_live_events",
]


@dataclass
class LiveBetRank:
    score: float
    tier: str
    label: str
    palpite: str | None = None
    opportunity_count: int = 0
    top_ev: float | None = None
    top_label: str | None = None
    match_kind: str = "other"

    def to_dict(self) -> dict[str, Any]:
        return {
            "bet_rank_score": round(self.score, 2),
            "bet_tier": self.tier,
            "bet_label": self.label,
            "bet_palpite": self.palpite,
            "bet_opportunity_count": self.opportunity_count,
            "bet_top_ev": round(self.top_ev, 4) if self.top_ev is not None else None,
            "bet_top_label": self.top_label,
            "match_kind": self.match_kind,
        }


def _cell_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _cell_str(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _latest_ticks_by_event(max_age_minutes: int = 45) -> dict[int, dict[str, Any]]:
    path = live_ticks_path()
    if not path.exists():
        return {}
    try:
        df = pd.read_parquet(path)
    except Exception:
        return {}
    if df.empty or "event_id" not in df.columns:
        return {}

    if "captured_at" in df.columns:
        df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True, errors="coerce")
        cutoff = datetime.now(UTC) - timedelta(minutes=max_age_minutes)
        df = df[df["captured_at"] >= cutoff]
    if df.empty:
        return {}

    df = df.sort_values("captured_at")
    out: dict[int, dict[str, Any]] = {}
    for event_id, group in df.groupby("event_id"):
        row = group.iloc[-1]
        out[int(event_id)] = {
            "top_aporte_ev": _cell_float(row.get("top_aporte_ev")),
            "top_aporte_market": _cell_str(row.get("top_aporte_market")),
            "top_aporte_outcome": _cell_str(row.get("top_aporte_outcome")),
            "prob_final_home": _cell_float(row.get("prob_final_home")),
            "prob_final_draw": _cell_float(row.get("prob_final_draw")),
            "prob_final_away": _cell_float(row.get("prob_final_away")),
        }
    return out


def _palpite_from_probs(h: float | None, d: float | None, a: float | None) -> str | None:
    if h is None or d is None or a is None:
        return None
    probs = {"1": h, "X": d, "2": a}
    best = max(probs, key=probs.get)
    if probs[best] < 0.38:
        return "neutro"
    return best


def _heuristic_score(event: SuperbetLiveEventSummary) -> tuple[float, list[str], str]:
    score = 0.0
    tags: list[str] = []
    _, _, match_kind = classify_live_match(event.home_team, event.away_team)
    minute = event.minute or 0
    gap = abs(event.home_score - event.away_score)
    status = (event.status or "").upper()

    if match_kind == "club":
        score += 80
        tags.append("clube BR")
    elif match_kind == "national":
        score += 55
        tags.append("seleção")

    if 8 <= minute <= 44:
        score += 35
        tags.append("janela in-play")
    elif minute > 45:
        score -= 50
        tags.append("após 45'")

    if gap <= 1:
        score += 25
        tags.append("jogo equilibrado")
    elif gap >= 3 and minute > 50:
        score -= 80
        tags.append("jogo decidido")

    if event.market_count >= 35:
        score += 15
        tags.append("mercados ricos")
    elif event.market_count >= 20:
        score += 5

    if status in {"FINISHED", "ENDED", "CLOSED", "CANCELLED", "ABANDONED"}:
        score -= 200
        tags.append("encerrado")

    if event.period_label and "END" in event.period_label.upper():
        score -= 200
        tags.append("encerrado")

    return score, tags, match_kind


def _tier_from_score(score: float, top_ev: float | None) -> str:
    if score <= -50:
        return "blocked"
    if top_ev is not None and top_ev >= 0.08:
        return "top"
    if score >= 70 or (top_ev is not None and top_ev >= 0.05):
        return "top"
    if score >= 45 or (top_ev is not None and top_ev >= 0.03):
        return "good"
    if score >= 15 or (top_ev is not None and top_ev > 0):
        return "watch"
    return "skip"


def _label_for_tier(tier: str, tags: list[str], top_label: str | None, top_ev: float | None) -> str:
    if tier == "blocked":
        return "Evitar — jogo encerrado ou sem novos aportes"
    if tier == "top":
        if top_label and top_ev is not None:
            return f"⭐ Melhor agora · {top_label} (EV +{top_ev * 100:.0f}%)"
        return "⭐ Melhor para palpite agora"
    if tier == "good":
        if top_label:
            return f"✓ Bom jogo · {top_label}"
        return "✓ Bom para analisar"
    if tier == "watch":
        return "👁 Monitorar · edge fraco"
    return "Sem edge claro · " + (tags[0] if tags else "prioridade baixa")


def rank_live_event(
    event: SuperbetLiveEventSummary,
    tick: dict[str, Any] | None = None,
) -> LiveBetRank:
    score, tags, match_kind = _heuristic_score(event)
    top_ev = tick.get("top_aporte_ev") if tick else None
    if top_ev is not None:
        score += min(40.0, top_ev * 200)

    palpite = None
    if tick:
        palpite = _palpite_from_probs(
            tick.get("prob_final_home"),
            tick.get("prob_final_draw"),
            tick.get("prob_final_away"),
        )

    top_label = None
    if tick and tick.get("top_aporte_market"):
        m = tick["top_aporte_market"]
        o = tick.get("top_aporte_outcome") or ""
        top_label = f"{m} {o}".strip() if o else m

    tier = _tier_from_score(score, top_ev)
    opp_count = 1 if top_ev and top_ev > 0 else 0
    label = _label_for_tier(tier, tags, top_label, top_ev)

    return LiveBetRank(
        score=score,
        tier=tier,
        label=label,
        palpite=palpite,
        opportunity_count=opp_count,
        top_ev=top_ev,
        top_label=top_label,
        match_kind=match_kind,
    )


def rank_live_events(events: list[SuperbetLiveEventSummary]) -> list[tuple[SuperbetLiveEventSummary, LiveBetRank]]:
    ticks = _latest_ticks_by_event()
    ranked: list[tuple[SuperbetLiveEventSummary, LiveBetRank]] = []
    for event in events:
        tick = ticks.get(event.event_id)
        ranked.append((event, rank_live_event(event, tick)))
    ranked.sort(key=lambda pair: pair[1].score, reverse=True)
    return ranked
