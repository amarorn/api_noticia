"""Testes da seleção de fonte em tune-inplay."""
from __future__ import annotations

import pandas as pd

from pipelines.wc_inplay_tune import _merge_training_timelines


def test_merge_training_timelines_ticks_only(monkeypatch):
    ticks_df = pd.DataFrame(
        [
            {
                "match_id": "live_1",
                "season": 2026,
                "minute": 30,
                "home_score_partial": 0,
                "away_score_partial": 0,
                "remaining_goals_home": 1,
                "remaining_goals_away": 0,
                "remaining_fraction": 0.67,
                "home_red_cards": 0,
                "away_red_cards": 0,
                "home_corners": 2,
                "away_corners": 1,
                "source": "live_ticks",
            }
        ]
    )
    monkeypatch.setattr(
        "pipelines.wc_inplay_tune.build_timeline_from_fixtures",
        lambda **_: pd.DataFrame(),
    )
    monkeypatch.setattr(
        "pipelines.wc_inplay_ticks_dataset.build_timeline_from_live_ticks",
        lambda: ticks_df,
    )

    merged = _merge_training_timelines(
        min_train_season=2010,
        eval_season=2022,
        include_fixtures=False,
        include_ticks=True,
    )
    assert len(merged) == 1
    assert merged.iloc[0]["source"] == "live_ticks"
