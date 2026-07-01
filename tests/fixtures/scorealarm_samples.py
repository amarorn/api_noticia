"""Fixtures reais ScoreAlarm (amostras de produção)."""

TEAM_STATS_SSE = {
    "teams": {
        "away": {
            "stats": {
                "1": {"0": {"val": "1"}, "6": {"val": "1"}},
                "5": {"0": {"val": "5"}, "6": {"val": "5"}},
                "6": {"0": {"val": "4"}, "6": {"val": "4"}},
                "7": {"0": {"val": "1"}, "6": {"val": "1"}},
                "11": {"0": {"val": "3"}, "6": {"val": "3"}},
                "24": {"0": {"val": "0"}, "6": {"val": "0"}},
            },
            "meta": {"names": [{"value": "Lilla Torg FF", "type": 1}]},
        },
        "home": {
            "stats": {
                "1": {"0": {"val": "0"}, "6": {"val": "0"}},
                "5": {"0": {"val": "1"}, "6": {"val": "1"}},
                "6": {"0": {"val": "1"}, "6": {"val": "1"}},
                "11": {"0": {"val": "3"}, "6": {"val": "3"}},
                "24": {"0": {"val": "2"}, "6": {"val": "2"}},
            },
            "meta": {"names": [{"value": "Nosaby IF", "type": 1}]},
        },
    },
    "meta": {"offer_id": "ax:match:13425692"},
}

OVERVIEW_STATISTICS = {
    "statistics": [
        {
            "period": 0,
            "data": [
                {
                    "team1": "49%",
                    "team2": "51%",
                    "type": 1,
                    "text": {"args": ["stats.football.match.ball_possesion"]},
                },
                {
                    "team1": "1",
                    "team2": "5",
                    "type": 18,
                    "text": {"args": ["stats.football.match.shots"]},
                },
                {
                    "team1": "1",
                    "team2": "4",
                    "type": 2,
                    "text": {"args": ["stats.football.match.shots_on_goal"]},
                },
                {
                    "team1": "3",
                    "team2": "3",
                    "type": 5,
                    "text": {"args": ["stats.football.match.corner_kicks"]},
                },
                {
                    "team1": "2",
                    "team2": "0",
                    "type": 12,
                    "text": {"args": ["stats.football.match.yellow_cards"]},
                },
            ],
        }
    ],
    "live_events": [
        {
            "type": 4,
            "subtype": 8,
            "side": 2,
            "minute": {"value": 19},
            "main": {"text": {"args": ["0:1"]}},
        },
        {
            "type": 14,
            "subtype": 0,
            "side": 2,
            "minute": {"value": 24},
            "main": {"text": {"args": ["stats.football.match.corner_event"]}},
        },
    ],
    "team1": {"name": "Nosaby IF", "id": "home-id"},
    "team2": {"name": "Lilla Torg FF", "id": "away-id"},
}

OVERVIEW_PREMATCH = {
    "team1_manager": {
        "name": "Lorenzo, Nestor",
        "names": [{"value": {"string_value": "Nestor Lorenzo"}, "type": 1}],
    },
    "team2_manager": {"name": "Patrice Carteron"},
    "team1": {"name": "Colômbia", "id": "home-id"},
    "team2": {"name": "Jordânia", "id": "away-id"},
}

H2H_PREMATCH = {
    "h2h_year_since": 2018,
    "h2h_statistics": {"team1": 1, "draw": 0, "team2": 0},
    "team1_events": [
        {
            "scores": [{"team1": 2, "team2": 0, "type": 0}],
            "team1": {"name": "Colômbia"},
            "team2": {"name": "Jordânia"},
        },
        {
            "scores": [{"team1": 3, "team2": 1, "type": 0}],
            "team1": {"name": "Colômbia"},
            "team2": {"name": "Costa Rica"},
        },
        {
            "scores": [{"team1": 0, "team2": 1, "type": 0}],
            "team1": {"name": "Colômbia"},
            "team2": {"name": "Uruguai"},
        },
        {
            "scores": [{"team1": 2, "team2": 2, "type": 0}],
            "team1": {"name": "Colômbia"},
            "team2": {"name": "Peru"},
        },
        {
            "scores": [{"team1": 1, "team2": 0, "type": 0}],
            "team1": {"name": "Colômbia"},
            "team2": {"name": "Chile"},
        },
    ],
    "team2_events": [
        {
            "scores": [{"team1": 3, "team2": 1, "type": 0}],
            "team1": {"name": "Áustria"},
            "team2": {"name": "Jordânia"},
        },
        {
            "scores": [{"team1": 2, "team2": 0, "type": 0}],
            "team1": {"name": "Colômbia"},
            "team2": {"name": "Jordânia"},
        },
        {
            "scores": [{"team1": 4, "team2": 1, "type": 0}],
            "team1": {"name": "Suíça"},
            "team2": {"name": "Jordânia"},
        },
        {
            "scores": [{"team1": 0, "team2": 0, "type": 0}],
            "team1": {"name": "Jordânia"},
            "team2": {"name": "Iraque"},
        },
        {
            "scores": [{"team1": 2, "team2": 3, "type": 0}],
            "team1": {"name": "Palestina"},
            "team2": {"name": "Jordânia"},
        },
    ],
    "h2h_events": [
        {
            "scores": [{"team1": 2, "team2": 0, "type": 0}],
            "team1": {"name": "Colômbia"},
            "team2": {"name": "Jordânia"},
        }
    ],
}

PLAYER_STATS_SSE = {
    "p1": {
        "stats": {
            "1": {"6": {"val": "1"}},
            "6": {"6": {"val": "2"}},
            "5": {"6": {"val": "3"}},
        },
        "meta": {
            "team_side": 1,
            "jersey_number": "10",
            "position": 4,
            "names": [{"type": 2, "name": "J. Quintero"}, {"type": 1, "name": "Juan Quintero"}],
            "team_names": [{"type": 1, "name": "Colômbia"}],
        },
    },
    "p2": {
        "stats": {
            "6": {"6": {"val": "1"}},
            "32": {"6": {"val": "4"}},
        },
        "meta": {
            "team_side": 2,
            "jersey_number": "1",
            "position": 1,
            "names": [{"type": 2, "name": "N. Ateyah"}],
            "team_names": [{"type": 1, "name": "Jordânia"}],
        },
    },
    "p3": {
        "stats": {"5": {"6": {"val": "0"}}, "1": {"6": {"val": "0"}}},
        "meta": {
            "team_side": 1,
            "jersey_number": "2",
            "position": 2,
            "names": [{"type": 2, "name": "D. Muñoz"}],
        },
    },
}
