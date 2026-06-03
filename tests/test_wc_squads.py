from pathlib import Path

from pipelines.wc_squads import get_squad_by_team, list_squad_teams, load_wc_squads

WC_SQUADS = Path("data/wc/squads_2026.json")


def test_wc_squads_has_48_teams() -> None:
    data = load_wc_squads(WC_SQUADS)
    teams = list_squad_teams(data)
    assert data["team_count"] == 48
    assert len(teams) == 48
    assert get_squad_by_team(data, "Brasil") is not None
    assert get_squad_by_team(data, "brasil") is not None
    assert get_squad_by_team(data, "Seleção Inexistente") is None
