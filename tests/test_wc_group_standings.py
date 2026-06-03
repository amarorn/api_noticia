from pipelines.wc_group_standings import build_group_standings


def test_build_group_standings_points():
    groups = [{"id": "C", "teams": ["Brasil", "Marrocos", "Haiti", "Escócia"]}]
    preds = [
        {"home_team": "Brasil", "away_team": "Marrocos", "prediction": "1", "group": "C"},
        {"home_team": "Brasil", "away_team": "Haiti", "prediction": "1", "group": "C"},
        {"home_team": "Escócia", "away_team": "Brasil", "prediction": "2", "group": "C"},
    ]
    blocks = build_group_standings(groups, preds)
    assert len(blocks) == 1
    brasil = next(r for r in blocks[0]["standings"] if r["team"] == "Brasil")
    assert brasil["points"] == 9
    assert brasil["won"] == 3
    assert brasil["position"] == 1
