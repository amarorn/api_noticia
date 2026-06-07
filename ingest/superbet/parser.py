"""Parser do payload Superbet (SSE) → snapshot estruturado."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from schemas.national_teams import normalize_national_team


@dataclass
class SuperbetInPlayState:
    home_score: int
    away_score: int
    minute: int
    stoppage_time: str | None
    home_corners: int
    away_corners: int
    home_yellow_cards: int
    away_yellow_cards: int
    ht_home_score: int | None
    ht_away_score: int | None
    period_label: str | None
    status: str | None


@dataclass
class SuperbetMarketOdds:
    market_name: str
    market_id: int | None
    line: str | None
    outcomes: dict[str, float] = field(default_factory=dict)
    implied_probs: dict[str, float] = field(default_factory=dict)


@dataclass
class SuperbetLiveEventSummary:
    event_id: int
    home_team: str
    away_team: str
    event_name: str
    sport_id: int
    tournament_id: int | None
    utc_date: str | None
    betradar_id: str | None
    minute: int
    home_score: int
    away_score: int
    period_label: str | None
    status: str | None
    market_count: int
    h2h_odds: dict[str, float]
    captured_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "event_name": self.event_name,
            "sport_id": self.sport_id,
            "tournament_id": self.tournament_id,
            "utc_date": self.utc_date,
            "betradar_id": self.betradar_id,
            "minute": self.minute,
            "home_score": self.home_score,
            "away_score": self.away_score,
            "period_label": self.period_label,
            "status": self.status,
            "market_count": self.market_count,
            "h2h_odds": self.h2h_odds,
            "captured_at": self.captured_at,
        }


@dataclass
class SuperbetEventSnapshot:
    event_id: int
    home_team: str
    away_team: str
    event_name: str
    utc_date: str | None
    betradar_id: str | None
    is_live: bool
    inplay: SuperbetInPlayState | None
    h2h_odds: dict[str, float]
    h2h_implied: dict[str, float]
    totals: dict[str, dict[str, float]]
    totals_implied: dict[str, dict[str, float]]
    corners: dict[str, dict[str, float]]
    corners_implied: dict[str, dict[str, float]]
    combo_markets: dict[str, dict[str, float]]
    generosity_probs: dict[str, float]
    raw_market_count: int
    captured_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "event_name": self.event_name,
            "utc_date": self.utc_date,
            "betradar_id": self.betradar_id,
            "is_live": self.is_live,
            "inplay": None if self.inplay is None else {
                "home_score": self.inplay.home_score,
                "away_score": self.inplay.away_score,
                "minute": self.inplay.minute,
                "stoppage_time": self.inplay.stoppage_time,
                "home_corners": self.inplay.home_corners,
                "away_corners": self.inplay.away_corners,
                "home_yellow_cards": self.inplay.home_yellow_cards,
                "away_yellow_cards": self.inplay.away_yellow_cards,
                "ht_home_score": self.inplay.ht_home_score,
                "ht_away_score": self.inplay.ht_away_score,
                "period_label": self.inplay.period_label,
                "status": self.inplay.status,
            },
            "h2h_odds": self.h2h_odds,
            "h2h_implied": self.h2h_implied,
            "totals": self.totals,
            "totals_implied": self.totals_implied,
            "corners": self.corners,
            "corners_implied": self.corners_implied,
            "combo_markets": self.combo_markets,
            "generosity_probs": self.generosity_probs,
            "raw_market_count": self.raw_market_count,
            "captured_at": self.captured_at,
        }


def parse_event_name(event_name: str) -> tuple[str, str]:
    for sep in ("·", " - ", " – ", " x ", " vs ", " v "):
        if sep in event_name:
            left, right = event_name.split(sep, 1)
            return normalize_national_team(left.strip()), normalize_national_team(right.strip())
    raise ValueError(f"Não foi possível separar times em: {event_name!r}")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _parse_minute(minutes: Any, stoppage: Any) -> int:
    base = _safe_int(minutes, 0)
    if not stoppage:
        return base
    text = str(stoppage).strip()
    if ":" in text:
        parts = text.split(":", 1)
        try:
            return base + int(parts[0])
        except ValueError:
            return base
    try:
        return base + int(text)
    except ValueError:
        return base


def _devig(probs: dict[str, float]) -> dict[str, float]:
    total = sum(probs.values()) or 1.0
    return {k: v / total for k, v in probs.items()}


def _implied_from_prices(prices: dict[str, float]) -> dict[str, float]:
    raw = {k: 1.0 / max(float(v), 1.01) for k, v in prices.items()}
    return _devig(raw)


def _find_market(markets: list[dict], name: str) -> dict | None:
    for market in markets:
        if market.get("name") == name:
            return market
    return None


def _extract_line_odds(market: dict) -> dict[str, dict[str, float]]:
    by_line: dict[str, dict[str, float]] = {}
    for odd in market.get("odds") or []:
        if not isinstance(odd, dict):
            continue
        price = odd.get("price")
        if not isinstance(price, (int, float)) or price <= 1.0:
            continue
        md = odd.get("metadata") or {}
        line = str(md.get("special_bet_value") or "default")
        label = str(md.get("name") or md.get("code") or "outcome")
        by_line.setdefault(line, {})[label] = float(price)
    return by_line


def _extract_combo_yes_no(market: dict, key: str) -> dict[str, float] | None:
    prices: dict[str, float] = {}
    for odd in market.get("odds") or []:
        md = odd.get("metadata") or {}
        name = str(md.get("name") or "").lower()
        price = odd.get("price")
        if not isinstance(price, (int, float)):
            continue
        if name in {"sim", "yes"}:
            prices["yes"] = float(price)
        elif name in {"não", "nao", "no"}:
            prices["no"] = float(price)
    if not prices:
        return None
    return {key: v for k, v in _implied_from_prices(prices).items() for key, v in [(k, v)]}


def _parse_inplay(ev: dict) -> SuperbetInPlayState | None:
    stats = ev.get("inplay_stats")
    if not isinstance(stats, dict) or not stats:
        return None
    meta = ev.get("inplay_stats_metadata") or {}
    periods = stats.get("periods") or []
    ht_home = ht_away = None
    for period in periods:
        if period.get("num") == 1:
            ht_home = _safe_int(period.get("home_team_score"))
            ht_away = _safe_int(period.get("away_team_score"))
    minute = _parse_minute(stats.get("minutes"), stats.get("stoppage_time"))
    status = str(meta.get("status") or "")
    if minute <= 0 and status in {"FINISHED", "ENDED", "CLOSED"}:
        minute = 90

    return SuperbetInPlayState(
        home_score=_safe_int(stats.get("home_team_score")),
        away_score=_safe_int(stats.get("away_team_score")),
        minute=minute,
        stoppage_time=str(stats.get("stoppage_time")) if stats.get("stoppage_time") else None,
        home_corners=_safe_int(stats.get("home_team_corners")),
        away_corners=_safe_int(stats.get("away_team_corners")),
        home_yellow_cards=_safe_int(stats.get("home_team_yellow_cards")),
        away_yellow_cards=_safe_int(stats.get("away_team_yellow_cards")),
        ht_home_score=ht_home,
        ht_away_score=ht_away,
        period_label=meta.get("event_status_label"),
        status=meta.get("status"),
    )


def _parse_teams_from_event(ev: dict) -> tuple[str, str, str]:
    fixture = ev.get("fixture") or {}
    event_name = str(fixture.get("event_name") or "")
    try:
        home_team, away_team = parse_event_name(event_name)
    except ValueError:
        home_team, away_team = event_name, ""
    return home_team, away_team, event_name


def _extract_h2h_odds(markets: list[dict]) -> dict[str, float]:
    h2h_odds: dict[str, float] = {}
    h2h_market = _find_market(markets, "Resultado Final")
    if not h2h_market:
        return h2h_odds
    for odd in h2h_market.get("odds") or []:
        md = odd.get("metadata") or {}
        code = str(md.get("name") or md.get("code") or "")
        price = odd.get("price")
        if not isinstance(price, (int, float)):
            continue
        if code in {"1", "X", "2", "0"}:
            key = "X" if code in {"X", "0"} else code
            h2h_odds[key] = float(price)
    return h2h_odds


def parse_live_event_summary(ev: dict) -> SuperbetLiveEventSummary | None:
    fixture = ev.get("fixture") or {}
    sport_id = _safe_int(fixture.get("sport_id"), 0)
    if sport_id <= 0:
        return None

    home_team, away_team, event_name = _parse_teams_from_event(ev)
    inplay = _parse_inplay(ev)
    meta = ev.get("inplay_stats_metadata") or {}
    markets = ev.get("markets") or []

    return SuperbetLiveEventSummary(
        event_id=int(ev.get("event_id") or fixture.get("event_id") or 0),
        home_team=home_team,
        away_team=away_team,
        event_name=event_name,
        sport_id=sport_id,
        tournament_id=_safe_int(fixture.get("tournament_id"), 0) or None,
        utc_date=fixture.get("utc_date"),
        betradar_id=str(fixture.get("betradar_id")) if fixture.get("betradar_id") else None,
        minute=inplay.minute if inplay else 0,
        home_score=inplay.home_score if inplay else 0,
        away_score=inplay.away_score if inplay else 0,
        period_label=inplay.period_label if inplay else meta.get("event_status_label"),
        status=inplay.status if inplay else meta.get("status"),
        market_count=_safe_int(meta.get("market_count"), len(markets)),
        h2h_odds=_extract_h2h_odds(markets),
        captured_at=datetime.now(timezone.utc).isoformat(),
    )


def parse_superbet_event(ev: dict) -> SuperbetEventSnapshot:
    home_team, away_team, event_name = _parse_teams_from_event(ev)
    fixture = ev.get("fixture") or {}
    markets = ev.get("markets") or []
    tags = str(fixture.get("event_tags") or "")
    is_live = "superLive" in tags or bool(ev.get("inplay_stats"))

    h2h_odds = _extract_h2h_odds(markets)
    generosity: dict[str, float] = {}
    h2h_market = _find_market(markets, "Resultado Final")
    if h2h_market:
        for odd in h2h_market.get("odds") or []:
            md = odd.get("metadata") or {}
            extra = md.get("extra") or {}
            if "generosity_prob_home" in extra:
                generosity["home"] = float(extra["generosity_prob_home"])
            if "generosity_prob_away" in extra:
                generosity["away"] = float(extra["generosity_prob_away"])

    totals = _extract_line_odds(_find_market(markets, "Total de Gols") or {})
    corners = _extract_line_odds(_find_market(markets, "Total de Escanteios") or {})

    combo_markets: dict[str, dict[str, float]] = {}
    combo_specs = {
        "btts_and_over_3_5": "Ambas as Equipes Marcam & Mais de 3.5 Gols",
        "ft_and_btts": "Resultado Final & Ambas as Equipes Marcam",
        "ft_and_total_3_5": "Resultado Final & Total de Gols (3.5)",
    }
    for key, market_name in combo_specs.items():
        market = _find_market(markets, market_name)
        if not market:
            continue
        prices: dict[str, float] = {}
        for odd in market.get("odds") or []:
            md = odd.get("metadata") or {}
            label = str(md.get("name") or md.get("info") or "outcome")
            price = odd.get("price")
            if isinstance(price, (int, float)) and price > 1.0:
                prices[label[:40]] = float(price)
        if prices:
            combo_markets[key] = _implied_from_prices(prices)

    totals_implied = {line: _implied_from_prices(prices) for line, prices in totals.items()}
    corners_implied = {line: _implied_from_prices(prices) for line, prices in corners.items()}

    return SuperbetEventSnapshot(
        event_id=int(ev.get("event_id") or fixture.get("event_id") or 0),
        home_team=home_team,
        away_team=away_team,
        event_name=event_name,
        utc_date=fixture.get("utc_date"),
        betradar_id=str(fixture.get("betradar_id")) if fixture.get("betradar_id") else None,
        is_live=is_live,
        inplay=_parse_inplay(ev),
        h2h_odds=h2h_odds,
        h2h_implied=_implied_from_prices(h2h_odds) if h2h_odds else {},
        totals=totals,
        totals_implied=totals_implied,
        corners=corners,
        corners_implied=corners_implied,
        combo_markets=combo_markets,
        generosity_probs=generosity,
        raw_market_count=len(markets),
        captured_at=datetime.now(timezone.utc).isoformat(),
    )
