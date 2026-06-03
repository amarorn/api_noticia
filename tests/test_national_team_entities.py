from pipelines.national_team_entities import extract_national_teams


def test_extract_brazil_portuguese():
    teams = extract_national_teams("Seleção brasileira convoca nove atletas para amistoso")
    assert "Brasil" in teams


def test_extract_multiple_aliases():
    text = "Brazil beat Mexico 2-0; Argentina watches World Cup draw"
    teams = extract_national_teams(text)
    assert "Brasil" in teams
    assert "México" in teams
    assert "Argentina" in teams
