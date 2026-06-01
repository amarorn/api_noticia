from ingest.odds.the_odds_api import H2HOdds, merge_schedule_with_odds


def test_merge_schedule_with_live_odds() -> None:
    schedule = {
        "season": 2026,
        "competition": "Copa do Mundo",
        "phase": "group",
        "round": 1,
        "matches": [
            {"home_team": "Brasil", "away_team": "Marrocos", "phase": "group", "group": "G"},
            {"home_team": "Argentina", "away_team": "México", "phase": "group", "group": "C"},
        ],
    }
    live = [
        H2HOdds(
            home_team="Brasil",
            away_team="Marrocos",
            odds_1=1.9,
            odds_x=3.4,
            odds_2=5.2,
            bookmaker="bet365",
            commence_time="2026-06-10T15:00:00Z",
        )
    ]

    merged, matched = merge_schedule_with_odds(schedule, live)
    assert matched == 1
    assert len(merged["matches"]) == 1
    assert merged["matches"][0]["home_team"] == "Brasil"
    assert merged["matches"][0]["odds"]["1"] == 1.9
