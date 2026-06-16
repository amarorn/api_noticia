"""Testes do calendário WC com palpites embutidos."""
from __future__ import annotations

import json

from pipelines.wc_schedule import _load_schedule_predictions_map, build_schedule_response


def test_build_schedule_includes_predictions(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    reports.mkdir(parents=True)
    preds = [
        {
            "home_team": "Brasil",
            "away_team": "Marrocos",
            "prediction": "X",
            "confidence": 0.31,
            "probabilities": {"1": 0.35, "X": 0.31, "2": 0.34},
        }
    ]
    (reports / "wc_2026_predictions_latest.json").write_text(
        json.dumps(preds), encoding="utf-8"
    )
    monkeypatch.setattr("config.settings.lake_root", tmp_path)

    data = {
        "season": 2026,
        "competition": "Copa",
        "matches": [
            {
                "home_team": "Brasil",
                "away_team": "Marrocos",
                "group": "G",
                "round": 1,
            }
        ],
    }
    out = build_schedule_response(data)
    match = out["matches"][0]
    assert match["prediction"] == "X"
    assert out["predictions_summary"]["draws"] == 1


def test_load_schedule_predictions_map_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("config.settings.lake_root", tmp_path)
    assert _load_schedule_predictions_map() == {}
