"""Testes do relatório diário in-play e gate de regressão (WS1)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from pipelines import inplay_daily_report as daily
from scripts.check_model_regression import check_regression


@pytest.fixture
def report_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(daily, "REPORTS_DIR", reports)
    monkeypatch.setattr(daily, "METRICS_HISTORY_PATH", tmp_path / "metrics_history.parquet")
    monkeypatch.setattr(daily, "BASELINE_PATH", reports / "inplay_baseline.json")
    return tmp_path


def test_metrics_row_and_append_history(report_dirs: Path) -> None:
    report = {
        "report_date": "2026-08-04",
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "brier_modelo": 0.21,
            "brier_mercado": 0.22,
            "delta_brier": -0.01,
            "n_ticks": 120,
            "n_events": 8,
        },
        "live_ticks": {
            "brier_by_minute_bucket": {
                "0-15": {"brier": 0.20, "n": 30},
                "15-30": {"brier": 0.22, "n": 25},
            },
            "accuracy_modelo": 0.45,
        },
        "operational": {
            "gbm_availability_pct": 92.0,
            "staleness_pct": 2.0,
            "sofascore_coverage_pct": 85.0,
        },
        "wallet": {
            "wallet_hit_rate": 0.55,
            "wallet_pnl": 10.0,
            "wallet_roi": 0.05,
            "recon_hit_rate": 0.58,
            "recon_pnl": 12.0,
        },
    }

    path = daily.append_metrics_history(report)
    assert path.is_file()
    df = pd.read_parquet(path)
    assert len(df) == 1
    assert df.iloc[0]["brier_modelo"] == pytest.approx(0.21)

    daily.append_metrics_history(report)
    df2 = pd.read_parquet(path)
    assert len(df2) == 1


def test_save_daily_report_and_baseline_seed(report_dirs: Path) -> None:
    report = {
        "report_date": "2026-08-04",
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {"brier_modelo": 0.19, "n_ticks": 80, "gbm_availability_pct": 95.0},
    }
    out = daily.save_daily_report(report)
    assert out.name == "inplay_daily_20260804.json"
    assert json.loads(out.read_text())["report_date"] == "2026-08-04"

    seeded = daily.seed_baseline_if_missing(report, min_ticks=50)
    assert seeded is True
    assert daily.BASELINE_PATH.is_file()
    assert daily.seed_baseline_if_missing(report) is False


def test_check_regression_passes_with_good_metrics(
    report_dirs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import check_model_regression as gate

    baseline = {
        "brier_modelo": 0.22,
        "created_at": "2026-08-01T00:00:00+00:00",
    }
    gate.BASELINE_PATH.write_text(json.dumps(baseline), encoding="utf-8")

    history = pd.DataFrame(
        [
            {"report_date": "2026-08-01", "brier_modelo": 0.22},
            {"report_date": "2026-08-02", "brier_modelo": 0.21},
            {"report_date": "2026-08-03", "brier_modelo": 0.215},
        ]
    )
    history.to_parquet(gate.METRICS_HISTORY_PATH, index=False)

    report = {
        "report_date": "2026-08-04",
        "summary": {"brier_modelo": 0.21, "gbm_availability_pct": 95.0},
        "live_ticks": {"brier_by_minute_bucket": {}},
    }
    ok, messages = check_regression(report)
    assert ok is True
    assert any("OK" in m for m in messages)


def test_check_regression_fails_on_simulated_degrade(
    report_dirs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import check_model_regression as gate

    gate.BASELINE_PATH.write_text(
        json.dumps({"brier_modelo": 0.20}),
        encoding="utf-8",
    )

    report = {
        "report_date": "2026-08-04",
        "summary": {"brier_modelo": 0.20, "gbm_availability_pct": 95.0},
        "live_ticks": {"brier_by_minute_bucket": {}},
    }
    ok, messages = check_regression(report, simulate_degrade=0.10)
    assert ok is False
    assert any("FALHA" in m for m in messages)


def test_check_regression_fails_low_gbm(report_dirs: Path) -> None:
    report = {
        "report_date": "2026-08-04",
        "summary": {"brier_modelo": 0.18, "gbm_availability_pct": 50.0},
        "live_ticks": {"brier_by_minute_bucket": {}},
    }
    ok, messages = check_regression(report, min_gbm_availability=90.0)
    assert ok is False
    assert any("GBM availability" in m for m in messages)
