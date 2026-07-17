"""Testes da janela de jogos pré-jogo."""
from __future__ import annotations

from datetime import UTC, datetime

from pipelines.wc_pregame_today import build_pregame_window


def _sched(*matches):
    return {"matches": list(matches)}


def test_pregame_today_only_includes_local_today():
    now = datetime(2026, 7, 2, 15, 0, tzinfo=UTC)
    schedule = _sched(
        {
            "id": "usa-bosnia",
            "home_team": "Estados Unidos",
            "away_team": "Bósnia",
            "kickoff": "2026-07-02T20:00:00+00:00",
            "phase": "round_of_32",
        },
        {
            "id": "eng-congo",
            "home_team": "Inglaterra",
            "away_team": "República Democrática do Congo",
            "kickoff": "2026-07-01T16:00:00+00:00",
            "phase": "round_of_32",
        },
    )
    window, meta = build_pregame_window(
        schedule,
        now=now,
        tz_name="America/Sao_Paulo",
        today_only=True,
    )
    ids = {m.get("id") for _, m in window}
    assert ids == {"usa-bosnia"}
    assert meta["today_only"] is True
    assert meta["date"] == "2026-07-02"


def test_pregame_today_only_excludes_yesterday_evening_brt():
    """00:00 UTC = 21h BRT do dia anterior — não entra em 'hoje' no Brasil."""
    now = datetime(2026, 7, 2, 15, 0, tzinfo=UTC)
    schedule = _sched(
        {
            "id": "usa-bosnia",
            "home_team": "Estados Unidos",
            "away_team": "Bósnia",
            "kickoff": "2026-07-02T00:00:00+00:00",
            "phase": "round_of_32",
        },
    )
    window, _ = build_pregame_window(
        schedule,
        now=now,
        tz_name="America/Sao_Paulo",
        today_only=True,
    )
    assert len(window) == 0


def test_pregame_today_only_includes_midnight_spillover_brt():
    """00:00 BRT (03:00 UTC) ainda aparece à noite do dia anterior."""
    now = datetime(2026, 7, 3, 2, 37, tzinfo=UTC)  # 23:37 BRT em 02/07
    schedule = _sched(
        {
            "id": "round_of_32-suica-argelia",
            "home_team": "Suíça",
            "away_team": "Argélia",
            "kickoff": "2026-07-03T03:00:00Z",
            "phase": "round_of_32",
        },
        {
            "id": "por-cro",
            "home_team": "Portugal",
            "away_team": "Croácia",
            "kickoff": "2026-07-02T23:00:00+00:00",
            "phase": "round_of_32",
        },
    )
    window, meta = build_pregame_window(
        schedule,
        now=now,
        tz_name="America/Sao_Paulo",
        today_only=True,
    )
    ids = {m.get("id") for _, m in window}
    assert "round_of_32-suica-argelia" in ids
    assert "por-cro" in ids
    assert meta["date"] == "2026-07-02"


def test_pregame_window_with_days_back_includes_yesterday():
    now = datetime(2026, 7, 2, 10, 0, tzinfo=UTC)
    schedule = _sched(
        {
            "id": "bel-sen",
            "home_team": "Bélgica",
            "away_team": "Senegal",
            "kickoff": "2026-07-01T20:00:00+00:00",
            "phase": "round_of_32",
        },
    )
    window, _ = build_pregame_window(schedule, now=now, days_ahead=2, days_back=1)
    assert len(window) == 1


def test_find_next_upcoming_match_skips_played_and_past():
    from pipelines.wc_pregame_today import find_next_upcoming_match, serialize_next_match

    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    schedule = _sched(
        {
            "id": "semi-done",
            "home_team": "França",
            "away_team": "Espanha",
            "kickoff": "2026-07-14T19:00:00+00:00",
            "phase": "semifinal",
            "home_score": 0,
            "away_score": 2,
        },
        {
            "id": "semi-next",
            "home_team": "Argentina",
            "away_team": "Brasil",
            "kickoff": "2026-07-15T19:00:00+00:00",
            "phase": "semifinal",
        },
        {
            "id": "final-later",
            "home_team": "TBD",
            "away_team": "TBD2",
            "kickoff": "2026-07-19T19:00:00+00:00",
            "phase": "final",
        },
    )
    nxt = find_next_upcoming_match(schedule, now=now)
    assert nxt is not None
    assert nxt[1]["id"] == "semi-next"
    payload = serialize_next_match(nxt[0], nxt[1], now=now)
    assert payload["home_team"] == "Argentina"
    assert "eta_label" in payload
    assert payload["kickoff_br"]
