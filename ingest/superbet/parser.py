"""Parser do payload Superbet (SSE) → snapshot estruturado."""
from __future__ import annotations

import re
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
    basket_periods: list[dict[str, int]] = field(default_factory=list)


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
    btts_odds: dict[str, float]
    next_goal_odds: dict[str, float]
    generosity_probs: dict[str, float]
    team_totals: dict[str, dict[str, dict[str, float]]]
    first_half_totals: dict[str, dict[str, float]]
    second_half_totals: dict[str, dict[str, float]]
    yellow_cards: dict[str, dict[str, float]]
    first_half_yellow_cards: dict[str, dict[str, float]]
    team_shots: dict[str, dict[str, dict[str, float]]]
    team_shots_on_target: dict[str, dict[str, dict[str, float]]]
    half_markets: dict[str, dict[str, Any]]
    handicap_odds: dict[str, float]
    handicap_implied: dict[str, float]
    # Basquete
    moneyline_odds: dict[str, float] = field(default_factory=dict)
    moneyline_implied: dict[str, float] = field(default_factory=dict)
    spread_odds: dict[str, dict[str, float]] = field(default_factory=dict)
    spread_implied: dict[str, dict[str, float]] = field(default_factory=dict)
    total_points_odds: dict[str, dict[str, float]] = field(default_factory=dict)
    total_points_implied: dict[str, dict[str, float]] = field(default_factory=dict)
    raw_market_count: int = 0
    captured_at: str = ""

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
                "basket_periods": self.inplay.basket_periods,
            },
            "h2h_odds": self.h2h_odds,
            "h2h_implied": self.h2h_implied,
            "totals": self.totals,
            "totals_implied": self.totals_implied,
            "corners": self.corners,
            "corners_implied": self.corners_implied,
            "combo_markets": self.combo_markets,
            "btts_odds": self.btts_odds,
            "next_goal_odds": self.next_goal_odds,
            "generosity_probs": self.generosity_probs,
            "team_totals": self.team_totals,
            "first_half_totals": self.first_half_totals,
            "second_half_totals": self.second_half_totals,
            "yellow_cards": self.yellow_cards,
            "first_half_yellow_cards": self.first_half_yellow_cards,
            "team_shots": self.team_shots,
            "team_shots_on_target": self.team_shots_on_target,
            "half_markets": self.half_markets,
            "handicap_odds": self.handicap_odds,
            "handicap_implied": self.handicap_implied,
            "moneyline_odds": self.moneyline_odds,
            "moneyline_implied": self.moneyline_implied,
            "spread_odds": self.spread_odds,
            "spread_implied": self.spread_implied,
            "total_points_odds": self.total_points_odds,
            "total_points_implied": self.total_points_implied,
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


def _parse_handicap_line_value(raw: str) -> float | None:
    text = str(raw or "").strip().replace(",", ".")
    match = re.search(r"([+-]?\d+(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_handicap_odds(
    markets: list[dict],
    home_team: str,
    away_team: str,
) -> dict[str, float]:
    """Extrai odds de handicap asiático (casa/fora por linha)."""
    from models.wc_handicap import format_handicap_key

    out: dict[str, float] = {}
    home_l = home_team.lower()
    away_l = away_team.lower()
    keywords = ("handicap asiático", "handicap asiatico", "asian handicap", "handicap")
    for market in markets:
        name = str(market.get("name") or "").lower()
        if not any(k in name for k in keywords):
            continue
        if "escanteio" in name or "cart" in name:
            continue
        for odd in market.get("odds") or []:
            if not isinstance(odd, dict):
                continue
            price = odd.get("price")
            if not isinstance(price, (int, float)) or price <= 1.0:
                continue
            md = odd.get("metadata") or {}
            line_raw = str(md.get("special_bet_value") or md.get("info") or md.get("name") or "")
            line = _parse_handicap_line_value(line_raw)
            if line is None:
                continue
            label = str(md.get("name") or md.get("info") or "").lower()
            code = str(md.get("code") or md.get("name") or "").upper()
            side: str | None = None
            if code in {"1", "HOME"} or home_l in label or "casa" in label:
                side = "home"
            elif code in {"2", "AWAY"} or away_l in label or "fora" in label or "visit" in label:
                side = "away"
            if side is None:
                continue
            key = format_handicap_key(side, line)  # type: ignore[arg-type]
            out[key] = float(price)
    return out


def _find_market(markets: list[dict], name: str) -> dict | None:
    for market in markets:
        if market.get("name") == name:
            return market
    return None


def _is_active_odd(odd: dict) -> bool:
    """Verifica se a odd está ativa (status == 1) e com preço válido."""
    status = odd.get("status")
    if status is not None and int(status) != 1:
        return False
    price = odd.get("price")
    if not isinstance(price, (int, float)) or price <= 1.0:
        return False
    return True


def _extract_yes_no_odds(market: dict | None) -> dict[str, float]:
    if not market:
        return {}
    prices: dict[str, float] = {}
    for odd in market.get("odds") or []:
        if not isinstance(odd, dict) or not _is_active_odd(odd):
            continue
        name = str((odd.get("metadata") or {}).get("name") or "").lower()
        price = float(odd["price"])
        if name in {"sim", "yes"}:
            prices["yes"] = price
        elif name in {"não", "nao", "no"}:
            prices["no"] = price
    return prices


def _team_side(label: str, home_team: str, away_team: str) -> str | None:
    text = label.lower()
    home = home_team.lower()
    away = away_team.lower()
    if home and home in text:
        return "home"
    if away and away in text:
        return "away"
    if text in {"1", "casa", "home"}:
        return "home"
    if text in {"2", "fora", "away", "visitante"}:
        return "away"
    if text in {"nenhum", "sem gol", "no goal", "none"}:
        return "none"
    return None


def _extract_next_goal_odds(markets: list[dict], home_team: str, away_team: str) -> dict[str, float]:
    for market_name in (
        "Próximo Gol",
        "2º Gol",
        "3º Gol",
        "4º Gol",
        "5º Gol",
        "Próximo gol",
    ):
        market = _find_market(markets, market_name)
        if not market:
            continue
        out: dict[str, float] = {}
        for odd in market.get("odds") or []:
            if not isinstance(odd, dict) or not _is_active_odd(odd):
                continue
            md = odd.get("metadata") or {}
            label = str(md.get("name") or md.get("info") or "")
            side = _team_side(label, home_team, away_team)
            if side and side not in out:
                out[side] = float(odd["price"])
        if out:
            return out
    return {}


def _extract_line_odds(market: dict) -> dict[str, dict[str, float]]:
    by_line: dict[str, dict[str, float]] = {}
    for odd in market.get("odds") or []:
        if not isinstance(odd, dict) or not _is_active_odd(odd):
            continue
        md = odd.get("metadata") or {}
        line = str(md.get("special_bet_value") or "default")
        label = str(md.get("name") or md.get("code") or "outcome")
        by_line.setdefault(line, {})[label] = float(odd["price"])
    return by_line


def _extract_combo_yes_no(market: dict, key: str) -> dict[str, float] | None:
    prices: dict[str, float] = {}
    for odd in market.get("odds") or []:
        if not isinstance(odd, dict) or not _is_active_odd(odd):
            continue
        md = odd.get("metadata") or {}
        name = str(md.get("name") or "").lower()
        if name in {"sim", "yes"}:
            prices["yes"] = float(odd["price"])
        elif name in {"não", "nao", "no"}:
            prices["no"] = float(odd["price"])
    if not prices:
        return None
    return {key: v for k, v in _implied_from_prices(prices).items() for key, v in [(k, v)]}


_BASKET_SPORT_IDS = {4}  # Superbet BR: sport_id 4 = Basquete (virtual/simulado, quartos de 10min)
_BASKET_QUARTER_MINUTES = 10


def _parse_basket_elapsed_minute(stats: dict, meta: dict) -> int:
    """Converte o relógio do quarto (contagem regressiva) em minutos acumulados de jogo.

    Ao contrário do futebol, `stats["minutes"]` no basquete é uma contagem regressiva
    dentro do quarto atual (ex.: "9" = faltam 9min pro fim do quarto em andamento), não
    tempo decorrido. `periods` traz o quarto em andamento como último item.
    """
    periods = stats.get("periods") or []
    quarter_num = len(periods) if periods else 1
    label = str(meta.get("event_status_label") or meta.get("period_status") or "")
    if label.startswith("Q"):
        try:
            quarter_num = max(quarter_num, int(label[1:]))
        except ValueError:
            pass
    countdown = max(0, min(_safe_int(stats.get("minutes")), _BASKET_QUARTER_MINUTES))
    elapsed_in_quarter = _BASKET_QUARTER_MINUTES - countdown
    return max(0, (quarter_num - 1) * _BASKET_QUARTER_MINUTES + elapsed_in_quarter)


def _parse_inplay(ev: dict) -> SuperbetInPlayState | None:
    stats = ev.get("inplay_stats")
    if not isinstance(stats, dict) or not stats:
        return None
    meta = ev.get("inplay_stats_metadata") or {}
    fixture = ev.get("fixture") or {}
    sport_id = _safe_int(fixture.get("sport_id"), 0)
    periods = stats.get("periods") or []
    ht_home = ht_away = None
    for period in periods:
        if period.get("num") == 1:
            ht_home = _safe_int(period.get("home_team_score"))
            ht_away = _safe_int(period.get("away_team_score"))
    status = str(meta.get("status") or "")
    basket_periods: list[dict[str, int]] = []
    if sport_id in _BASKET_SPORT_IDS:
        minute = _parse_basket_elapsed_minute(stats, meta)
        basket_periods = [
            {
                "num": _safe_int(period.get("num")),
                "home": _safe_int(period.get("home_team_score")),
                "away": _safe_int(period.get("away_team_score")),
            }
            for period in periods
            if period.get("num") is not None
        ]
    else:
        minute = _parse_minute(stats.get("minutes"), stats.get("stoppage_time"))
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
        basket_periods=basket_periods,
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


_HALF_1H_RE = re.compile(
    r"1[ºo°]\s*tempo|primeiro\s*tempo|\(1[ºo°]\s*tempo\)|1st\s*half",
    re.I,
)
_HALF_2H_RE = re.compile(
    r"2[ºo°]\s*tempo|segundo\s*tempo|\(2[ºo°]\s*tempo\)|2nd\s*half",
    re.I,
)


def _period_from_market_name(name: str) -> str | None:
    if _HALF_1H_RE.search(name):
        return "1h"
    if _HALF_2H_RE.search(name):
        return "2h"
    return None


def _handicap_line_key(line: float) -> str:
    if line == 0.0:
        return "0"
    sign = "p" if line > 0 else "m"
    return f"{sign}{abs(line):g}".replace(".", "_")


def _parse_handicap_line(raw: str) -> float | None:
    text = raw.strip().replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_score_key(label: str) -> str | None:
    text = label.strip().lower().replace(" ", "")
    match = re.match(r"^(\d+)[:x\-–](\d+)$", text)
    if match:
        return f"{match.group(1)}x{match.group(2)}"
    return None


def _normalize_exact_key(label: str) -> str | None:
    text = label.strip().lower()
    if re.fullmatch(r"\d+", text):
        return text
    match = re.search(r"(\d+)\s*ou\s*mais", text)
    if match:
        return f"{int(match.group(1))}+"
    if re.fullmatch(r"\d+\+", text):
        return text
    return None


def _exact_team_side(name: str, home_team: str, away_team: str) -> str | None:
    lower = name.lower()
    home_l = home_team.lower()
    away_l = away_team.lower()
    if home_l and home_l in lower:
        return "home"
    if away_l and away_l in lower:
        return "away"
    match = re.search(r"n[úu]mero exato de gols de\s+(.+)$", name, re.I)
    if match:
        team = normalize_national_team(match.group(1).strip()).lower()
        if team == home_l or home_l.startswith(team):
            return "home"
        if team == away_l or away_l.startswith(team):
            return "away"
    return None


def _classify_ft_market(name: str) -> str | None:
    """Mercados de handicap do jogo inteiro (sem 1T/2T no nome)."""
    if _period_from_market_name(name):
        return None
    lower = name.lower()
    if re.search(r"handicap\s*3\s*-?\s*way|3-way|3way", lower):
        return None
    if "empate anula" in lower or "draw no bet" in lower:
        return None
    if "asiático" in lower or "asiatico" in lower:
        return "asian_handicap"
    if "handicap" in lower:
        return "handicap"
    return None


def _classify_half_market(name: str, home_team: str, away_team: str) -> tuple[str | None, str | None]:
    period = _period_from_market_name(name)
    if not period:
        return None, None
    lower = name.lower()
    if " ou " in lower and "resultado" in lower:
        return period, None
    if "handicap" in lower:
        if re.search(r"handicap\s*3\s*-?\s*way|3-way|3way", lower):
            return period, None
        if "asiático" in lower or "asiatico" in lower:
            return period, "asian_handicap"
        return period, "handicap"
    if "resultado correto" in lower:
        return period, "correct_score"
    if "número exato" in lower or "numero exato" in lower:
        side = _exact_team_side(name, home_team, away_team)
        if side == "home":
            return period, "exact_team_home"
        if side == "away":
            return period, "exact_team_away"
        return period, "exact_total"
    if re.search(r"resultado\s*\(?1x2\)?", lower):
        return period, "h2h"
    if "resultado final" in lower:
        return period, "h2h"
    return period, None


def _find_period_total_goals(markets: list[dict], period: str) -> dict | None:
    """Mercado de total de gols do período (ex.: '1º Tempo - Total de Gols')."""
    for market in markets:
        name = str(market.get("name") or "")
        if _period_from_market_name(name) != period:
            continue
        lower = name.lower()
        if "total de gols" not in lower:
            continue
        if "asiático" in lower or "asiatico" in lower:
            continue
        if re.search(r"total de gols de\s", lower):
            continue
        if re.search(r"-\s*total de gols\s*$", lower):
            return market
    return None


def _find_prop_total_market(
    markets: list[dict],
    *,
    stat: str,
    period: str | None = None,
    team: str | None = None,
    home_team: str = "",
    away_team: str = "",
) -> dict | None:
    """Localiza mercado Over/Under por linha (gols, cartões, chutes)."""
    stat_keywords: dict[str, tuple[str, ...]] = {
        "goals": ("total de gols",),
        "yellow_cards": (
            "cartões amarelos",
            "cartoes amarelos",
            "cartão amarelo",
            "cartao amarelo",
            "total de cartões",
            "total de cartoes",
        ),
        "shots": ("total de chutes", "chutes totais"),
        "shots_on_target": ("chutes no gol", "chutes a gol", "chutes ao gol"),
        "corners": ("total de escanteios", "escanteios"),
    }
    keywords = stat_keywords.get(stat, ())
    if not keywords:
        return None

    home_l = home_team.lower()
    away_l = away_team.lower()
    team_l = (team or "").lower()

    for market in markets:
        name = str(market.get("name") or "")
        lower = name.lower()
        if not any(k in lower for k in keywords):
            continue
        if stat == "shots" and ("a gol" in lower or "no gol" in lower):
            continue
        if stat == "shots_on_target" and not any(k in lower for k in ("no gol", "a gol", "ao gol")):
            continue
        if stat == "yellow_cards":
            if "vermelh" in lower:
                continue
            if any(x in lower for x in ("1x2", "handicap", "exato", "equipe com", "1° cartão", "1º cartão")):
                continue
        market_period = _period_from_market_name(name)
        if period == "1h" and market_period != "1h":
            continue
        if period == "ft" and market_period is not None:
            continue
        if period == "1h" and market_period is None and "primeiro tempo" not in lower:
            continue
        if team_l:
            if team_l not in lower and not (home_l and home_l in lower and team == home_team):
                if not (away_l and away_l in lower and team == away_team):
                    continue
            if " de " in lower and stat == "goals":
                if re.search(r"total de gols de\s", lower):
                    continue
        elif stat == "goals":
            if re.search(r"total de gols de\s", lower):
                continue
            if home_l and home_l in lower and "total de gols" in lower:
                continue
            if away_l and away_l in lower and "total de gols" in lower:
                continue
        elif stat == "yellow_cards" and not team_l:
            if home_l and home_l in lower:
                continue
            if away_l and away_l in lower:
                continue
            if re.search(r"total de cart(õ|o)es de\s", lower):
                continue
        return market
    return None


def _extract_half_h2h(market: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for odd in market.get("odds") or []:
        if not isinstance(odd, dict) or not _is_active_odd(odd):
            continue
        md = odd.get("metadata") or {}
        code = str(md.get("name") or md.get("code") or "").upper()
        if code in {"1", "X", "2", "0"}:
            key = "X" if code in {"X", "0"} else code
            out[key] = float(odd["price"])
    return out


def _extract_half_correct_score(market: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for odd in market.get("odds") or []:
        if not isinstance(odd, dict) or not _is_active_odd(odd):
            continue
        md = odd.get("metadata") or {}
        label = str(md.get("name") or md.get("info") or "")
        key = _normalize_score_key(label)
        if key:
            out[key] = float(odd["price"])
    return out


def _extract_half_exact(market: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for odd in market.get("odds") or []:
        if not isinstance(odd, dict) or not _is_active_odd(odd):
            continue
        md = odd.get("metadata") or {}
        label = str(md.get("name") or md.get("info") or "")
        key = _normalize_exact_key(label)
        if key:
            out[key] = float(odd["price"])
    return out


def _extract_half_handicap(
    market: dict,
    home_team: str,
    away_team: str,
) -> dict[str, dict[str, float]]:
    by_line: dict[str, dict[str, float]] = {}
    for odd in market.get("odds") or []:
        if not isinstance(odd, dict) or not _is_active_odd(odd):
            continue
        md = odd.get("metadata") or {}
        label = str(md.get("name") or md.get("info") or "")
        raw_line = md.get("special_bet_value")
        line_val = _parse_handicap_line(str(raw_line)) if raw_line is not None else None
        if line_val is None:
            match = re.search(r"([+\-]?\d+(?:\.\d+)?)", label)
            if match:
                line_val = _parse_handicap_line(match.group(1))
        side = _team_side(label, home_team, away_team)
        if line_val is None or side not in {"home", "away"}:
            continue
        lk = _handicap_line_key(line_val)
        by_line.setdefault(lk, {})[side] = float(odd["price"])
    return by_line


def _extract_half_markets(
    markets: list[dict],
    home_team: str,
    away_team: str,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {"1h": {}, "2h": {}}
    for market in markets:
        name = str(market.get("name") or "")
        period, mtype = _classify_half_market(name, home_team, away_team)
        if not period or not mtype:
            continue
        bucket = result[period]
        if mtype == "h2h":
            extracted: Any = _extract_half_h2h(market)
        elif mtype == "correct_score":
            extracted = _extract_half_correct_score(market)
        elif mtype in {"exact_total", "exact_team_home", "exact_team_away"}:
            extracted = _extract_half_exact(market)
        elif mtype == "handicap":
            extracted = _extract_half_handicap(market, home_team, away_team)
        elif mtype == "asian_handicap":
            extracted = _extract_half_handicap(market, home_team, away_team)
        else:
            continue
        if not extracted:
            continue
        if mtype in {"handicap", "asian_handicap"}:
            bucket_key = "asian_handicap" if mtype == "asian_handicap" else "handicap"
            target = bucket.setdefault(bucket_key, {})
            for lk, sides in extracted.items():
                target.setdefault(lk, {}).update(sides)
        else:
            bucket.setdefault(mtype, {}).update(extracted)
    return {k: v for k, v in result.items() if v}


def _extract_ft_markets(
    markets: list[dict],
    home_team: str,
    away_team: str,
) -> dict[str, Any]:
    """Handicap europeu e asiático do jogo inteiro."""
    bucket: dict[str, Any] = {}
    for market in markets:
        name = str(market.get("name") or "")
        mtype = _classify_ft_market(name)
        if not mtype:
            continue
        extracted = _extract_half_handicap(market, home_team, away_team)
        if not extracted:
            continue
        bucket_key = "asian_handicap" if mtype == "asian_handicap" else "handicap"
        target = bucket.setdefault(bucket_key, {})
        for lk, sides in extracted.items():
            target.setdefault(lk, {}).update(sides)
    return bucket


def _extract_h2h_odds(markets: list[dict]) -> dict[str, float]:
    h2h_odds: dict[str, float] = {}
    h2h_market = _find_market(markets, "Resultado Final")
    if not h2h_market:
        return h2h_odds
    for odd in h2h_market.get("odds") or []:
        if not isinstance(odd, dict) or not _is_active_odd(odd):
            continue
        md = odd.get("metadata") or {}
        code = str(md.get("name") or md.get("code") or "")
        price = float(odd["price"])
        if code in {"1", "X", "2", "0"}:
            key = "X" if code in {"X", "0"} else code
            h2h_odds[key] = price
    return h2h_odds


# ---------------------------------------------------------------------------
# Basquete
# ---------------------------------------------------------------------------

_BASKET_MONEYLINE_NAMES = (
    "Vencedor",
    "Moneyline",
)

_BASKET_SPREAD_NAMES = (
    "Handicap",
    "Spread",
    "Point Spread",
)

_BASKET_TOTAL_NAMES = (
    "Total de Pontos",
    "Total Points",
)


def _is_basket_full_match_market(name: str, keywords: tuple[str, ...]) -> bool:
    """True se o nome do mercado COMEÇA com uma das keywords.

    A Superbet reaproveita os mesmos nomes de mercado para o jogo completo
    ("Total de Pontos (Inc. prorrogação)"), por quarto ("2º Quarto - Total de
    Pontos"), por tempo ("1º Tempo - Handicap") e por time ("Southland Sharks -
    Total de Pontos (...)"). Usar `startswith` em vez de substring evita misturar
    linhas de períodos/times diferentes no mesmo dict de odds.
    """
    stripped = name.strip().lower()
    return any(stripped.startswith(k.lower()) for k in keywords)


def _is_basket_moneyline_market(name: str) -> bool:
    return _is_basket_full_match_market(name, _BASKET_MONEYLINE_NAMES)


def _is_basket_spread_market(name: str) -> bool:
    return _is_basket_full_match_market(name, _BASKET_SPREAD_NAMES)


def _is_basket_total_market(name: str) -> bool:
    return _is_basket_full_match_market(name, _BASKET_TOTAL_NAMES)


def _extract_basket_moneyline(
    markets: list[dict],
    home_team: str,
    away_team: str,
) -> dict[str, float]:
    """Extrai odds de vencedor da partida (1 = casa, 2 = fora)."""
    out: dict[str, float] = {}
    home_l = home_team.lower()
    away_l = away_team.lower()
    for market in markets:
        if not _is_basket_moneyline_market(str(market.get("name") or "")):
            continue
        for odd in market.get("odds") or []:
            if not isinstance(odd, dict) or not _is_active_odd(odd):
                continue
            md = odd.get("metadata") or {}
            code = str(md.get("code") or md.get("name") or "").upper()
            label = str(md.get("name") or md.get("info") or "").lower()
            price = float(odd["price"])
            key: str | None = None
            if code == "1" or code == "HOME" or (home_l and home_l in label):
                key = "1"
            elif code == "2" or code == "AWAY" or (away_l and away_l in label):
                key = "2"
            if key:
                out[key] = price
        if out:
            break
    return out


def _extract_basket_spread(
    markets: list[dict],
    home_team: str,
    away_team: str,
) -> dict[str, dict[str, float]]:
    """Extrai odds de spread por linha (home/away)."""
    out: dict[str, dict[str, float]] = {}
    home_l = home_team.lower()
    away_l = away_team.lower()
    for market in markets:
        if not _is_basket_spread_market(str(market.get("name") or "")):
            continue
        for odd in market.get("odds") or []:
            if not isinstance(odd, dict) or not _is_active_odd(odd):
                continue
            md = odd.get("metadata") or {}
            line_raw = str(md.get("special_bet_value") or md.get("info") or md.get("name") or "")
            line = _parse_handicap_line_value(line_raw)
            if line is None:
                continue
            label = str(md.get("name") or md.get("info") or "").lower()
            code = str(md.get("code") or "").upper()
            side: str | None = None
            if code == "1" or code == "HOME" or (home_l and home_l in label):
                side = "home"
            elif code == "2" or code == "AWAY" or (away_l and away_l in label):
                side = "away"
            if side is None:
                continue
            lk = _handicap_line_key(line)
            out.setdefault(lk, {})[side] = float(odd["price"])
    return out


def _extract_basket_total_points(markets: list[dict]) -> dict[str, dict[str, float]]:
    """Extrai odds de total de pontos por linha (over/under)."""
    out: dict[str, dict[str, float]] = {}
    for market in markets:
        if not _is_basket_total_market(str(market.get("name") or "")):
            continue
        for odd in market.get("odds") or []:
            if not isinstance(odd, dict) or not _is_active_odd(odd):
                continue
            md = odd.get("metadata") or {}
            line_raw = str(md.get("special_bet_value") or md.get("info") or md.get("name") or "")
            line = _parse_handicap_line_value(line_raw)
            if line is None:
                continue
            label = str(md.get("name") or "").lower()
            code = str(md.get("code") or "").strip()
            outcome: str | None = None
            if code == "+" or label.startswith(("over", "mais", "acima")):
                outcome = "over"
            elif code == "-" or label.startswith(("under", "menos", "abaixo")):
                outcome = "under"
            if outcome is None:
                continue
            out.setdefault(f"{line:g}", {})[outcome] = float(odd["price"])
    return out


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
        "btts_and_over_2_5": "Ambas as Equipes Marcam & Mais de 2.5 Gols",
        "btts_and_over_3_5": "Ambas as Equipes Marcam & Mais de 3.5 Gols",
        "ft_and_btts": "Resultado Final & Ambas as Equipes Marcam",
        "ft_and_total_1_5": "Resultado Final & Total de Gols (1.5)",
        "ft_and_total_2_5": "Resultado Final & Total de Gols (2.5)",
        "ft_and_total_3_5": "Resultado Final & Total de Gols (3.5)",
    }
    for key, market_name in combo_specs.items():
        market = _find_market(markets, market_name)
        if not market:
            continue
        prices: dict[str, float] = {}
        for odd in market.get("odds") or []:
            if not isinstance(odd, dict) or not _is_active_odd(odd):
                continue
            md = odd.get("metadata") or {}
            label = str(md.get("name") or md.get("info") or "outcome")
            prices[label[:40]] = float(odd["price"])
        if prices:
            combo_markets[key] = _implied_from_prices(prices)

    totals_implied = {line: _implied_from_prices(prices) for line, prices in totals.items()}
    corners_implied = {line: _implied_from_prices(prices) for line, prices in corners.items()}
    btts_odds = _extract_yes_no_odds(_find_market(markets, "Ambas as Equipes Marcam"))
    next_goal_odds = _extract_next_goal_odds(markets, home_team, away_team)

    # Total por time (home / away)
    team_totals: dict[str, dict[str, dict[str, float]]] = {"home": {}, "away": {}}
    home_total_mkt = _find_market(markets, f"{home_team} - Total de Gols")
    if not home_total_mkt:
        home_total_mkt = _find_market(markets, "Total de Gols - Time da Casa")
    if not home_total_mkt:
        home_total_mkt = _find_market(markets, f"Total de Gols - {home_team}")
    if home_total_mkt:
        team_totals["home"] = _extract_line_odds(home_total_mkt)
    if not team_totals["home"]:
        alt = _find_prop_total_market(
            markets, stat="goals", period="ft", team=home_team,
            home_team=home_team, away_team=away_team,
        )
        if alt:
            team_totals["home"] = _extract_line_odds(alt)
    away_total_mkt = _find_market(markets, f"{away_team} - Total de Gols")
    if not away_total_mkt:
        away_total_mkt = _find_market(markets, "Total de Gols - Time Visitante")
    if not away_total_mkt:
        away_total_mkt = _find_market(markets, f"Total de Gols - {away_team}")
    if away_total_mkt:
        team_totals["away"] = _extract_line_odds(away_total_mkt)
    if not team_totals["away"]:
        alt = _find_prop_total_market(
            markets, stat="goals", period="ft", team=away_team,
            home_team=home_team, away_team=away_team,
        )
        if alt:
            team_totals["away"] = _extract_line_odds(alt)

    # Total 1º Tempo e 2º Tempo
    first_half_totals = _extract_line_odds(
        _find_market(markets, "Total de Gols (1º Tempo)") or {}
    )
    if not first_half_totals:
        first_half_totals = _extract_line_odds(_find_period_total_goals(markets, "1h") or {})
    if not first_half_totals:
        first_half_totals = _extract_line_odds(
            _find_market(markets, "Total de Gols nos Primeiros X Minutos") or {}
        )
    second_half_totals = _extract_line_odds(
        _find_market(markets, "Total de Gols (2º Tempo)") or {}
    )
    if not second_half_totals:
        second_half_totals = _extract_line_odds(_find_period_total_goals(markets, "2h") or {})
    half_markets = _extract_half_markets(markets, home_team, away_team)
    ft_markets = _extract_ft_markets(markets, home_team, away_team)
    if ft_markets:
        half_markets["ft"] = ft_markets

    yellow_cards = _extract_line_odds(
        _find_prop_total_market(markets, stat="yellow_cards", period="ft") or {}
    )
    first_half_yellow_cards = _extract_line_odds(
        _find_prop_total_market(markets, stat="yellow_cards", period="1h") or {}
    )
    team_shots: dict[str, dict[str, dict[str, float]]] = {"home": {}, "away": {}}
    home_shots_mkt = _find_prop_total_market(
        markets, stat="shots", period="ft", team=home_team, home_team=home_team, away_team=away_team
    )
    if home_shots_mkt:
        team_shots["home"] = _extract_line_odds(home_shots_mkt)
    away_shots_mkt = _find_prop_total_market(
        markets, stat="shots", period="ft", team=away_team, home_team=home_team, away_team=away_team
    )
    if away_shots_mkt:
        team_shots["away"] = _extract_line_odds(away_shots_mkt)

    team_shots_on_target: dict[str, dict[str, dict[str, float]]] = {"home": {}, "away": {}}
    home_sot_mkt = _find_prop_total_market(
        markets,
        stat="shots_on_target",
        period="ft",
        team=home_team,
        home_team=home_team,
        away_team=away_team,
    )
    if home_sot_mkt:
        team_shots_on_target["home"] = _extract_line_odds(home_sot_mkt)
    away_sot_mkt = _find_prop_total_market(
        markets,
        stat="shots_on_target",
        period="ft",
        team=away_team,
        home_team=home_team,
        away_team=away_team,
    )
    if away_sot_mkt:
        team_shots_on_target["away"] = _extract_line_odds(away_sot_mkt)

    handicap_odds = _extract_handicap_odds(markets, home_team, away_team)
    handicap_implied = _implied_from_prices(handicap_odds) if handicap_odds else {}

    # Basquete
    moneyline_odds = _extract_basket_moneyline(markets, home_team, away_team)
    spread_odds = _extract_basket_spread(markets, home_team, away_team)
    total_points_odds = _extract_basket_total_points(markets)
    moneyline_implied = _implied_from_prices(moneyline_odds) if moneyline_odds else {}
    spread_implied = {
        line: _implied_from_prices(prices)
        for line, prices in spread_odds.items()
    }
    total_points_implied = {
        line: _implied_from_prices(prices)
        for line, prices in total_points_odds.items()
    }

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
        btts_odds=btts_odds,
        next_goal_odds=next_goal_odds,
        generosity_probs=generosity,
        team_totals=team_totals,
        first_half_totals=first_half_totals,
        second_half_totals=second_half_totals,
        yellow_cards=yellow_cards,
        first_half_yellow_cards=first_half_yellow_cards,
        team_shots=team_shots,
        team_shots_on_target=team_shots_on_target,
        half_markets=half_markets,
        handicap_odds=handicap_odds,
        handicap_implied=handicap_implied,
        moneyline_odds=moneyline_odds,
        moneyline_implied=moneyline_implied,
        spread_odds=spread_odds,
        spread_implied=spread_implied,
        total_points_odds=total_points_odds,
        total_points_implied=total_points_implied,
        raw_market_count=len(markets),
        captured_at=datetime.now(timezone.utc).isoformat(),
    )
