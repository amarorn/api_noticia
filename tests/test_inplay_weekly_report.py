"""Testes do relatório semanal in-play (WS1)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

import pipelines.inplay_daily_report as daily
from pipelines import inplay_weekly_report as weekly
from pipelines.inplay_daily_report import append_metrics_row


@pytest.fixture
def weekly_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(weekly, "REPORTS_DIR", reports)
    metrics_path = tmp_path / "metrics_history.parquet"
    monkeypatch.setattr(weekly, "METRICS_HISTORY_PATH", metrics_path)
    monkeypatch.setattr(daily, "METRICS_HISTORY_PATH", metrics_path)
    monkeypatch.setattr(weekly, "WEEKLY_BASELINE_PATH", reports / "inplay_weekly_baseline.json")
    return tmp_path


def test_build_weekly_report_mocked(weekly_dirs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        weekly,
        "run_tune_step",
        lambda **_: {"ok": True, "holdout_brier": 0.19, "n_observations": 600},
    )
    monkeypatch.setattr(
        weekly,
        "run_walkforward_step",
        lambda **_: {
            "calibrated": {"brier_overall": 0.21, "n_samples": 150},
            "baseline_coefficients": {"brier_overall": 0.22},
        },
    )
    monkeypatch.setattr(
        weekly,
        "run_gbm_train_step",
        lambda **_: {"ok": True, "val_accuracy": 0.62, "val_logloss": 0.95},
    )

    report = weekly.build_weekly_report(verbose=False)
    assert report["report_kind"] == "weekly"
    assert report["summary"]["walkforward_brier"] == 0.21
    assert report["summary"]["gbm_val_accuracy"] == 0.62

    path = weekly.save_weekly_report(report)
    assert path.name.startswith("inplay_weekly_")
    assert json.loads(path.read_text())["summary"]["tune_holdout_brier"] == 0.19


def test_weekly_metrics_and_baseline(weekly_dirs: Path) -> None:
    report = {
        "week_ending": "2026-08-04",
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "walkforward_brier": 0.20,
            "walkforward_n_samples": 200,
            "gbm_val_accuracy": 0.61,
        },
    }
    row = weekly._metrics_row_from_weekly(report)
    append_metrics_row(row)
    df = pd.read_parquet(weekly.METRICS_HISTORY_PATH)
    assert len(df) == 1
    assert df.iloc[0]["report_kind"] == "weekly"

    seeded = weekly.seed_weekly_baseline_if_missing(report, min_samples=100)
    assert seeded is True
    assert weekly.WEEKLY_BASELINE_PATH.is_file()


def test_check_weekly_regression_pass_and_fail(weekly_dirs: Path) -> None:
    weekly.WEEKLY_BASELINE_PATH.write_text(
        json.dumps({"walkforward_brier": 0.20}),
        encoding="utf-8",
    )
    report_ok = {
        "week_ending": "2026-08-04",
        "summary": {"walkforward_brier": 0.21},
    }
    ok, _msgs = weekly.check_weekly_regression(report_ok)
    assert ok is True

    report_bad = {
        "week_ending": "2026-08-11",
        "summary": {"walkforward_brier": 0.24},
    }
    ok2, msgs2 = weekly.check_weekly_regression(report_bad)
    assert ok2 is False
    assert any("FALHA" in m for m in msgs2)


def test_run_weekly_skip_flags(weekly_dirs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def _tune(**_) -> dict:
        calls.append("tune")
        return {"ok": True}

    def _wf(**_) -> dict:
        calls.append("wf")
        return {"calibrated": {"brier_overall": 0.2, "n_samples": 120}}

    def _gbm(**_) -> dict:
        calls.append("gbm")
        return {"ok": True}

    monkeypatch.setattr(weekly, "run_tune_step", _tune)
    monkeypatch.setattr(weekly, "run_walkforward_step", _wf)
    monkeypatch.setattr(weekly, "run_gbm_train_step", _gbm)

    weekly.run_weekly_report(skip_tune=True, skip_gbm=True, append_history=False)
    assert calls == ["wf"]
