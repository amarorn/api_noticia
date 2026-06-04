import pandas as pd

from pipelines.wc_group_pressure import compute_group_pressure


def test_must_win_on_final_group_matchday():
    fixtures = pd.DataFrame(
        [
            {
                "season": 2022,
                "match_date": "2022-11-20T18:00:00+00:00",
                "home_team": "Brasil",
                "away_team": "Sérvia",
                "home_score": 2,
                "away_score": 0,
                "phase": "group",
                "group_name": "G",
                "is_neutral": True,
            },
            {
                "season": 2022,
                "match_date": "2022-11-24T18:00:00+00:00",
                "home_team": "Brasil",
                "away_team": "Suíça",
                "home_score": 1,
                "away_score": 1,
                "phase": "group",
                "group_name": "G",
                "is_neutral": True,
            },
            {
                "season": 2022,
                "match_date": "2022-11-26T18:00:00+00:00",
                "home_team": "Suíça",
                "away_team": "Camarões",
                "home_score": 1,
                "away_score": 0,
                "phase": "group",
                "group_name": "G",
                "is_neutral": True,
            },
            {
                "season": 2022,
                "match_date": "2022-11-28T18:00:00+00:00",
                "home_team": "Camarões",
                "away_team": "Sérvia",
                "home_score": 3,
                "away_score": 3,
                "phase": "group",
                "group_name": "G",
                "is_neutral": True,
            },
        ]
    )
    pressure = compute_group_pressure(
        fixtures,
        season=2022,
        group_name="G",
        home_team="Camarões",
        away_team="Brasil",
        before_date=pd.Timestamp("2022-12-02T18:00:00+00:00").to_pydatetime(),
        phase="group",
    )
    assert pressure.group_matchday == 2.0
    assert pressure.home_must_win == 1.0
    assert pressure.away_points == 4.0
