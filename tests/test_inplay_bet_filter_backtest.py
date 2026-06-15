"""Testes do backtest de filtros in-play e health do relatório semanal."""
from __future__ import annotations

import pandas as pd
import pytest

from pipelines.inplay_bet_filter_backtest import backtest_minute_filters
from pipelines.weekly_pl_report import build_weekly_report


@pytest.fixture
def mock_reconciliation(monkeypatch):
    df = pd.DataFrame(
        {
            "match_minute": [10, 20, 50, 70, 90],
            "won": [True, True, False, False, False],
            "pnl": [10.0, 5.0, -20.0, -15.0, -10.0],
        }
    )

    monkeypatch.setattr(
        "pipelines.user_bet_reconciliation.load_reconciliation",
        lambda _u: df,
    )


def test_backtest_midgame_improves_hit_rate(mock_reconciliation, monkeypatch):
    monkeypatch.setattr("config.settings.live_midgame_strict_minute", 45)
    monkeypatch.setattr("config.settings.live_block_minute", 88)
    report = backtest_minute_filters("test")
    baseline = next(s for s in report["scenarios"] if s["name"] == "baseline")
    mid = next(s for s in report["scenarios"] if s["name"] == "block_midgame")
    assert baseline["hit_rate"] == pytest.approx(0.4)
    assert mid["hit_rate"] == pytest.approx(1.0)
    assert mid["n_bets"] == 2


def test_weekly_report_model_beats_market_negative_delta(monkeypatch):
    monkeypatch.setattr(
        "pipelines.weekly_pl_report.compute_wallet_summary",
        lambda _u: {"pnl": 0, "roi": 0, "hit_rate": 0.5, "n_bets_placed": 1, "total_staked": 10, "daily_pnl": []},
    )
    monkeypatch.setattr(
        "pipelines.weekly_pl_report._load_reconciliation_stats",
        lambda _u: {"n_pairs": 1, "n_high_confidence": 1},
    )
    monkeypatch.setattr(
        "pipelines.weekly_pl_report._latest_benchmark",
        lambda: {"inplay_delta": -0.029},
    )
    monkeypatch.setattr(
        "pipelines.weekly_pl_report.get_wallet_sync_status",
        lambda _u: {"stale": False, "n_uploads": 1, "n_pending": 0},
    )
    monkeypatch.setattr(
        "pipelines.inplay_bet_filter_backtest.backtest_minute_filters",
        lambda _u: {"hit_rate_delta_pp": 12.0},
    )

    report = build_weekly_report("test")
    assert report["health"]["model_beats_market_inplay"] is True
    assert report["health"]["filter_improves_hit_rate"] is True
