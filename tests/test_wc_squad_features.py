from pipelines.wc_squad_features import (
    SQUAD_FEATURE_NAMES,
    profile_from_squad,
    squad_feature_vector,
)


def test_profile_from_squad_counts_positions():
    squad = {
        "player_count": 26,
        "sections": [
            {"position": "GK", "players": [{"name": "A", "club": "X"}] * 3},
            {"position": "DEF", "players": [{"name": "B", "club": "Bayern"}] * 8},
            {"position": "MID", "players": [{"name": "C", "club": "Brighton"}] * 8},
            {"position": "ATK", "players": [{"name": "D", "club": "PSG"}] * 7},
        ],
    }
    profile = profile_from_squad(squad)
    assert profile.depth_norm > 0.9
    assert profile.top5_league_share > 0.5
    assert len(SQUAD_FEATURE_NAMES) == 6


def test_squad_feature_vector_neutral_for_unknown_team():
    vec = squad_feature_vector("Time Inexistente", "Outro Time")
    assert len(vec) == 6
    assert all(abs(v) < 0.5 for v in vec)
