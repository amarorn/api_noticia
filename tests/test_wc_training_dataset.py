"""Treino WC Opção B — labels só Copa, histórico completo para features."""
from __future__ import annotations

import pandas as pd

from config import settings
from pipelines.wc_holdout import wc_holdout_test_df, wc_holdout_train_df
from pipelines.wc_training_dataset import (
    filter_wc_copa_labels,
    is_wc_copa_match,
    wc_temporal_train_val_test_split,
    wc_test_label_df,
    wc_training_label_df,
    wc_validation_label_df,
)


def test_is_wc_copa_match_by_competition():
    row = pd.Series({"competition": "Copa do Mundo", "phase": "group"})
    assert is_wc_copa_match(row) is True
    assert is_wc_copa_match(pd.Series({"competition": "Int. Friendly Games", "phase": "friendly"})) is False


def test_filter_wc_copa_labels_excludes_friendlies():
    df = pd.DataFrame(
        [
            {"competition": "Copa do Mundo", "phase": "group", "match_date": "2022-11-20", "label": "1"},
            {"competition": "Int. Friendly Games", "phase": "friendly", "match_date": "2022-03-01", "label": "X"},
        ]
    )
    out = filter_wc_copa_labels(df)
    assert len(out) == 1
    assert out.iloc[0]["competition"] == "Copa do Mundo"


def test_wc_training_label_df_excludes_holdout_and_friendlies(monkeypatch):
    monkeypatch.setattr(settings, "wc_holdout_mode", "edition")
    df = pd.DataFrame(
        [
            {
                "season": 2018,
                "competition": "Copa do Mundo",
                "phase": "group",
                "match_date": "2018-06-14",
                "home_team": "A",
                "away_team": "B",
                "label": "1",
            },
            {
                "season": 2022,
                "competition": "Copa do Mundo",
                "phase": "group",
                "match_date": "2022-11-20",
                "home_team": "C",
                "away_team": "D",
                "label": "2",
            },
            {
                "season": 2021,
                "competition": "Int. Friendly Games",
                "phase": "friendly",
                "match_date": "2021-06-01",
                "home_team": "E",
                "away_team": "F",
                "label": "X",
            },
        ]
    )
    train = wc_training_label_df(df, 2022, copa_labels_only=True)
    assert len(train) == 1
    assert train.iloc[0]["season"] == 2018

    holdout = wc_holdout_test_df(df, 2022)
    assert len(holdout) == 1
    assert holdout.iloc[0]["competition"] == "Copa do Mundo"


def test_wc_holdout_train_df_still_keeps_friendlies_without_copa_filter():
    """Split por edição sem filtro Copa (API interna)."""
    df = pd.DataFrame(
        [
            {
                "season": 2022,
                "competition": "Copa do Mundo",
                "phase": "group",
                "match_date": "2022-11-20",
                "label": "1",
            },
            {
                "season": 2022,
                "competition": "Int. Friendly Games",
                "phase": "friendly",
                "match_date": "2022-03-01",
                "label": "X",
            },
        ]
    )
    train = wc_holdout_train_df(df, 2022)
    assert len(train) == 1
    assert train.iloc[0]["phase"] == "friendly"


def test_training_label_respects_config_flag(monkeypatch):
    df = pd.DataFrame(
        [
            {
                "season": 2018,
                "competition": "Int. Friendly Games",
                "phase": "friendly",
                "match_date": "2018-03-01",
                "label": "X",
            },
        ]
    )
    monkeypatch.setattr(settings, "wc_train_labels_copa_only", False)
    monkeypatch.setattr(settings, "wc_holdout_mode", "edition")
    train = wc_training_label_df(df, 2022, copa_labels_only=None)
    assert len(train) == 1


def test_wc_temporal_split_80_10_10():
    rows = [
        {
            "season": 1990 + i,
            "competition": "Copa do Mundo",
            "phase": "group",
            "match_date": f"{1990 + i}-06-10",
            "label": "1",
        }
        for i in range(10)
    ]
    df = pd.DataFrame(rows)
    train, val, test = wc_temporal_train_val_test_split(
        df, train_ratio=0.8, val_ratio=0.1, test_ratio=0.1
    )
    assert len(train) == 8
    assert len(val) == 1
    assert len(test) == 1
    assert train.iloc[-1]["season"] == 1997
    assert val.iloc[0]["season"] == 1998
    assert test.iloc[0]["season"] == 1999


def test_wc_validation_temporal_mode_default(monkeypatch):
    monkeypatch.setattr(settings, "wc_holdout_mode", "temporal")
    monkeypatch.setattr(settings, "wc_train_split_ratio", 0.8)
    monkeypatch.setattr(settings, "wc_val_split_ratio", 0.1)
    monkeypatch.setattr(settings, "wc_test_split_ratio", 0.1)
    rows = [
        {
            "season": 1990 + i,
            "competition": "Copa do Mundo",
            "phase": "group",
            "match_date": f"{1990 + i}-06-10",
            "label": "1",
        }
        for i in range(10)
    ]
    df = pd.DataFrame(rows)
    train = wc_training_label_df(df, 2022)
    val = wc_validation_label_df(df, 2022)
    test = wc_test_label_df(df, 2022)
    assert len(train) == 8
    assert len(val) == 1
    assert len(test) == 1
    assert train.iloc[0]["season"] == 1990
    assert val.iloc[0]["season"] == 1998
    assert test.iloc[0]["season"] == 1999
