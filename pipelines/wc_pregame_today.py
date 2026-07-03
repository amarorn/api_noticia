"""Janela de jogos para a tela de análise pré-jogo."""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from dateutil.parser import parse as parse_dt

from schemas.national_teams import normalize_national_team

DEFAULT_PREGAME_TZ = "America/Sao_Paulo"
MATCH_DURATION_MIN = 105
# Jogos após meia-noite local ainda entram em "hoje" se começarem nas próximas N horas
# (ex.: Suíça x Argélia 00:00 BRT enquanto ainda é 23h do dia anterior).
PREGAME_TODAY_SPILLOVER_HOURS = 8


def _parse_kickoff(raw: str) -> datetime | None:
    try:
        return parse_dt(raw).astimezone(UTC)
    except Exception:
        return None


def _local_date(ko: datetime, tz: ZoneInfo) -> datetime.date:
    return ko.astimezone(tz).date()


def _is_played(match: dict[str, Any]) -> bool:
    return match.get("home_score") is not None and match.get("away_score") is not None


def _kickoff_finished(ko: datetime, now: datetime) -> bool:
    return ko + timedelta(minutes=MATCH_DURATION_MIN) < now


def match_in_pregame_window(
    ko: datetime,
    match: dict[str, Any],
    *,
    now: datetime,
    tz: ZoneInfo,
    calendar_start: datetime,
    calendar_end: datetime,
    rolling_end: datetime,
    hours_after_kickoff: int = 8,
) -> bool:
    """Inclui jogos do dia local, próximas 72h e partidas recentes ainda sem placar."""
    played = _is_played(match)

    if calendar_start <= ko <= calendar_end:
        return True

    if ko > now and ko <= rolling_end:
        return True

    if not played and now <= ko <= now + timedelta(hours=hours_after_kickoff):
        return True

    if not played and ko < now and (now - ko) <= timedelta(hours=hours_after_kickoff):
        return True

    if played and _local_date(ko, tz) == now.astimezone(tz).date():
        return True

    return False


def build_pregame_window(
    schedule: dict[str, Any],
    *,
    now: datetime | None = None,
    tz_name: str = DEFAULT_PREGAME_TZ,
    days_ahead: int = 1,
    days_back: int = 0,
    hours_forward: int = 72,
    today_only: bool = False,
) -> tuple[list[tuple[datetime, dict[str, Any]]], dict[str, Any]]:
    """Retorna jogos ordenados por kickoff e metadados da janela."""
    now = now or datetime.now(UTC)
    tz = ZoneInfo(tz_name)
    local_now = now.astimezone(tz)
    local_today = local_now.date()

    if today_only or (days_back == 0 and days_ahead == 1):
        local_start_day = local_today
        local_end_day = local_today
        use_rolling_fallback = False
    else:
        local_start_day = local_today - timedelta(days=max(days_back, 0))
        local_end_day = local_today + timedelta(days=max(days_ahead, 1) - 1)
        use_rolling_fallback = True

    calendar_start = datetime.combine(local_start_day, time.min, tzinfo=tz).astimezone(UTC)
    calendar_end = datetime.combine(local_end_day, time.max, tzinfo=tz).astimezone(UTC)
    rolling_end = now + timedelta(hours=hours_forward)

    seen: set[tuple[str, str, str] | str] = set()
    window: list[tuple[datetime, dict[str, Any]]] = []

    for match in schedule.get("matches", []):
        ko_raw = match.get("kickoff")
        if not ko_raw:
            continue
        ko = _parse_kickoff(str(ko_raw))
        if ko is None:
            continue

        local_ko_day = _local_date(ko, tz)
        if local_start_day <= local_ko_day <= local_end_day:
            pair_key = (
                normalize_national_team(str(match.get("home_team") or "")),
                normalize_national_team(str(match.get("away_team") or "")),
                local_ko_day.isoformat(),
            )
            if pair_key in seen:
                continue
            seen.add(pair_key)
            window.append((ko, match))
            continue

        if today_only and ko > now and ko <= now + timedelta(hours=PREGAME_TODAY_SPILLOVER_HOURS):
            pair_key = (
                normalize_national_team(str(match.get("home_team") or "")),
                normalize_national_team(str(match.get("away_team") or "")),
                local_ko_day.isoformat(),
            )
            if pair_key in seen:
                continue
            seen.add(pair_key)
            window.append((ko, match))
            continue

        if not use_rolling_fallback:
            continue

        match_key = str(match.get("id") or f"{match.get('home_team')}-{match.get('away_team')}-{ko.isoformat()}")
        if match_key in seen:
            continue

        if match_in_pregame_window(
            ko,
            match,
            now=now,
            tz=tz,
            calendar_start=calendar_start,
            calendar_end=calendar_end,
            rolling_end=rolling_end,
        ):
            seen.add(match_key)
            window.append((ko, match))

    window.sort(key=lambda item: item[0])

    meta = {
        "timezone": tz_name,
        "date": local_today.isoformat(),
        "start_date": local_start_day.isoformat(),
        "end_date": local_end_day.isoformat(),
        "days_ahead": days_ahead,
        "days_back": days_back,
        "today_only": today_only or (days_back == 0 and days_ahead == 1),
        "hours_forward": hours_forward,
        "calendar_start_utc": calendar_start.isoformat(),
        "calendar_end_utc": calendar_end.isoformat(),
        "rolling_end_utc": rolling_end.isoformat(),
    }
    return window, meta


def match_status(ko: datetime, match: dict[str, Any], *, now: datetime | None = None) -> str:
    """upcoming | live | finished."""
    now = now or datetime.now(UTC)
    if _is_played(match):
        return "finished"
    if ko <= now <= ko + timedelta(minutes=MATCH_DURATION_MIN):
        return "live"
    if _kickoff_finished(ko, now):
        return "finished"
    return "upcoming"
