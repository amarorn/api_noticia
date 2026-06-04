import pandas as pd

from models.poisson_wc import _team_attack_defense


def test_recent_seasons_weigh_more_on_attack():
    old = pd.DataFrame(
        [
            {
                "season": 1990,
                "home_team": "A",
                "away_team": "B",
                "home_score": 0,
                "away_score": 0,
            }
        ]
    )
    recent = pd.DataFrame(
        [
            {
                "season": 2022,
                "home_team": "A",
                "away_team": "B",
                "home_score": 5,
                "away_score": 0,
            }
        ]
    )
    df = pd.concat([old, recent], ignore_index=True)
    from models.poisson_wc import _season_weight
    from pipelines.wc_hyperparams import WcHyperParams, set_active_hyperparams

    att_decay, _, _ = _team_attack_defense(df, ref_season=2022)

    set_active_hyperparams(WcHyperParams(poisson_season_half_life=1000.0))
    try:
        att_flat, _, _ = _team_attack_defense(df, ref_season=2022)
    finally:
        set_active_hyperparams(None)

    assert _season_weight(1990, 2022, 8.0) < _season_weight(2022, 2022, 8.0)
    assert att_decay["A"] > att_flat["A"]
