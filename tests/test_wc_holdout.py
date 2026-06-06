import pandas as pd

from pipelines.wc_holdout import wc_holdout_test_df, wc_holdout_train_df


def test_holdout_2022_prefers_copa_do_mundo():
    df = pd.DataFrame(
        [
            {
                "season": 2022,
                "competition": "Copa do Mundo",
                "phase": "group",
                "match_date": "2022-11-20",
                "home_team": "A",
                "away_team": "B",
                "label": "1",
            },
            {
                "season": 2022,
                "competition": "Int. Friendly Games",
                "phase": "friendly",
                "match_date": "2022-03-01",
                "home_team": "C",
                "away_team": "D",
                "label": "X",
            },
        ]
    )
    holdout = wc_holdout_test_df(df, 2022)
    assert len(holdout) == 1
    assert holdout.iloc[0]["competition"] == "Copa do Mundo"

    train = wc_holdout_train_df(df, 2022)
    assert len(train) == 1
    assert train.iloc[0]["phase"] == "friendly"
