"""Testes da camada operacional beisebol (fase, mercados mortos, strategy, API)."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from ingest.superbet.parser import SuperbetEventSnapshot, SuperbetInPlayState
from models.baseball_bet_guardrails import build_baseball_bet_guardrails
from models.baseball_bet_strategy import build_baseball_bet_strategy_report
from models.baseball_dead_market import is_dead_baseball_market
from models.baseball_game_phase import resolve_baseball_game_phase

client = TestClient(app)


def test_resolve_baseball_game_phase_f5_open():
    phase = resolve_baseball_game_phase(
        inning=3, home_score=1, away_score=2, is_finished=False
    )
    assert phase.phase == "f5_open"
    assert phase.block_f5 is False


def test_resolve_baseball_game_phase_late():
    phase = resolve_baseball_game_phase(
        inning=8, home_score=3, away_score=7, is_finished=False
    )
    assert phase.phase == "late"
    assert phase.block_f5 is True


def test_is_dead_baseball_market_over_beaten():
    dead, reason = is_dead_baseball_market(
        "total_runs",
        "over_8_5",
        home_score=5,
        away_score=4,
        inning=7,
    )
    assert dead is True
    assert reason is not None


def test_is_dead_baseball_market_f5_after_inning_5():
    dead, _ = is_dead_baseball_market(
        "f5_total",
        "over_4_5",
        home_score=0,
        away_score=5,
        inning=6,
    )
    assert dead is True


def test_build_baseball_bet_guardrails_finished():
    phase = resolve_baseball_game_phase(
        inning=9, home_score=4, away_score=2, is_finished=True
    )
    payload = build_baseball_bet_guardrails(game_phase=phase, dead_markets=[])
    assert payload["block_new_bets"] is True
    assert payload["allow_f5"] is False


def test_build_baseball_bet_strategy_report_filters_f5():
    phase = resolve_baseball_game_phase(
        inning=7, home_score=2, away_score=5, is_finished=False
    )

    class FakeInplay:
        home_score = 2
        away_score = 5
        inning = 7

    aportes = [
        {
            "market": "f5_total",
            "outcome": "over_4_5",
            "label": "Mais de 4.5 F5",
            "edge_pp": 8.0,
            "action": "apostar",
            "expected_value": 0.12,
            "market_odd": 1.95,
            "model_prob": 0.58,
        },
        {
            "market": "moneyline",
            "outcome": "2",
            "label": "Visitante",
            "edge_pp": 6.0,
            "action": "monitorar",
            "expected_value": 0.05,
            "market_odd": 1.20,
            "model_prob": 0.88,
        },
    ]

    class FakeSnapshot:
        event_id = 1
        home_team = "A"
        away_team = "B"

    report = build_baseball_bet_strategy_report(
        inplay=FakeInplay(),
        snapshot=FakeSnapshot(),
        aportes=aportes,
        game_phase=phase,
        benchmark=None,
    )
    markets = [o["market"] for o in report["opportunities"]]
    assert "f5_total" not in markets
    assert report["posture"] in {"neutro", "defensivo", "atacar"}


def _snapshot() -> SuperbetEventSnapshot:
    return SuperbetEventSnapshot(
        event_id=12856152,
        home_team="Hanwha Eagles",
        away_team="Kiwoom Heroes",
        event_name="Hanwha Eagles·Kiwoom Heroes",
        utc_date="2026-07-16T09:30:00Z",
        betradar_id="67204684",
        is_live=True,
        inplay=SuperbetInPlayState(
            home_score=0,
            away_score=5,
            minute=5,
            stoppage_time=None,
            home_corners=0,
            away_corners=0,
            home_yellow_cards=0,
            away_yellow_cards=0,
            ht_home_score=None,
            ht_away_score=None,
            period_label="5I",
            status="STARTED",
            baseball_innings=[
                {"num": 1, "home": 0, "away": 1},
                {"num": 5, "home": 0, "away": 2},
            ],
        ),
        h2h_odds={},
        h2h_implied={},
        totals={},
        totals_implied={},
        corners={},
        corners_implied={},
        combo_markets={},
        btts_odds={},
        next_goal_odds={},
        generosity_probs={},
        team_totals={"home": {}, "away": {}},
        first_half_totals={},
        second_half_totals={},
        yellow_cards={},
        first_half_yellow_cards={},
        team_shots={"home": {}, "away": {}},
        team_shots_on_target={"home": {}, "away": {}},
        half_markets={},
        handicap_odds={},
        handicap_implied={},
        moneyline_odds={"1": 8.5, "2": 1.04},
        moneyline_implied={"1": 0.105, "2": 0.895},
        spread_odds={"p4_5": {"home": 1.78, "away": 1.92}},
        spread_implied={"p4_5": {"home": 0.53, "away": 0.47}},
        total_points_odds={},
        total_points_implied={},
        raw_market_count=9,
        captured_at="2026-07-16T10:00:00+00:00",
    )


def test_advise_baseball_cashout_negative_ev():
    from models.baseball_cashout import advise_baseball_cashout
    from models.wc_bet_advice import UserBetInput

    bet = UserBetInput(market="moneyline", outcome="1", stake=100.0, odds_placed=5.0)
    inplay = {
        "moneyline_probs": {"1": 0.08, "2": 0.92},
        "prob_home_win": 0.08,
        "prob_away_win": 0.92,
    }
    advice = advise_baseball_cashout(bet, inplay, inning=7)
    assert advice.action in {"cashout", "cashout_parcial", "aguardar"}
    assert advice.remaining_ev < 0


def test_poll_once_baseball_calls_advice(monkeypatch):
    from pipelines.poll_superbet_live import poll_once_baseball

    calls: list[int] = []

    def fake_advice(event_id, **kwargs):
        calls.append(event_id)
        return {
            "home_team": "A",
            "away_team": "B",
            "current_score": "0x3",
            "inning": 6,
            "is_live": True,
            "is_finished": False,
            "aportes": [],
            "strategy": {"posture": "neutro"},
        }

    monkeypatch.setattr(
        "pipelines.poll_superbet_live.run_baseball_live_advice",
        fake_advice,
    )
    result = poll_once_baseball([12856152])
    assert result["captured"] == 1
    assert calls == [12856152]


    def test_advice_with_user_bet_returns_cashout(self, monkeypatch):
        monkeypatch.setattr("config.settings.api_key", None)
        snap = _snapshot()
        with patch(
            "ingest.superbet.baseball_advice.fetch_event_with_stale_fallback",
            return_value=(snap, False),
        ), patch(
            "ingest.superbet.baseball_advice.save_event_snapshot",
        ):
            response = client.get(
                "/baseball/superbet/live/12856152/advice"
                "?fast=true&market=moneyline&outcome=2&stake=100&odds_placed=1.04"
            )
        assert response.status_code == 200
        data = response.json()
        assert data.get("cashout") is not None
        assert data["cashout"]["action"] in {
            "cashout",
            "cashout_parcial",
            "manter",
            "aguardar",
        }


class TestBaseballOperationalApi:
    def test_advice_includes_operational_fields(self, monkeypatch):
        monkeypatch.setattr("config.settings.api_key", None)
        snap = _snapshot()
        with patch(
            "ingest.superbet.baseball_advice.fetch_event_with_stale_fallback",
            return_value=(snap, False),
        ), patch(
            "ingest.superbet.baseball_advice.save_event_snapshot",
        ):
            response = client.get("/baseball/superbet/live/12856152/advice?fast=true")
        assert response.status_code == 200
        data = response.json()
        assert data["game_phase"]["phase"] == "f5_open"
        assert "strategy" in data
        assert data["strategy"]["posture"] in {"neutro", "defensivo", "atacar"}
        assert "bet_guardrails" in data
        assert "market_benchmark" in data

    def test_advice_stale_fallback_on_superbet_error(self, monkeypatch):
        monkeypatch.setattr("config.settings.api_key", None)
        from ingest.superbet.client import SuperbetClientError
        from ingest.superbet.live_advice_cache import set_cached_advice

        stale_payload = {
            "home_team": "A",
            "away_team": "B",
            "inning": 5,
            "minute": 5,
            "is_finished": False,
            "is_live": True,
            "superbet_stale": False,
            "superbet_event_id": 999,
            "captured_at": "2026-01-01T00:00:00Z",
            "aportes": [],
            "game_phase": {
                "phase": "f5_open",
                "label": "Entrada 5",
                "extras_possible": True,
                "block_f5": False,
                "block_ft_totals": False,
                "block_new_ft_aportes": False,
                "run_gap": 1,
                "lead_side": "away",
            },
            "bet_guardrails": {
                "block_new_bets": False,
                "block_reason": None,
                "dead_markets": [],
                "allow_f5": True,
                "allow_ft_totals": True,
                "extras_warning": False,
            },
        }
        set_cached_advice(
            (999, 0, 1, 5, 100000, True, "baseball"),
            stale_payload,
            ttl_sec=60.0,
        )

        with patch(
            "ingest.superbet.baseball_advice.fetch_event_with_stale_fallback",
            side_effect=SuperbetClientError("offline"),
        ):
            response = client.get("/baseball/superbet/live/999/advice?fast=true")
        assert response.status_code == 200
        data = response.json()
        assert data["superbet_stale"] is True
        assert data["home_team"] == "A"


def test_baseball_advice_finalize_on_finished():
    from ingest.superbet.baseball_advice import _build_baseball_advice_payload

    snap = _snapshot()
    snap.event_id = 12896894
    snap.is_live = False
    snap.inplay.status = "FINISHED"
    snap.inplay.home_score = 4
    snap.inplay.away_score = 2
    snap.inplay.minute = 9
    snap.inplay.period_label = "9I"

    with patch(
        "ingest.superbet.baseball_advice.maybe_finalize_finished_event",
        return_value={"event_id": 12896894, "gold_path": "/tmp/gold.json"},
    ) as finalize:
        payload = _build_baseball_advice_payload(
            event_id=12896894,
            snapshot=snap,
            superbet_stale=False,
            bankroll=1000.0,
            fast=False,
            save_bronze=False,
            save_tick=False,
        )

    assert payload["is_finished"] is True
    assert payload["event_finalize"] is not None
    finalize.assert_called_once()
