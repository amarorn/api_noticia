
from ingest.fixtures.parser import parse_football_txt, score_to_label


SAMPLE_TXT = """
= Brasileiro Série A 2024

▪ Matchday 1
  Sat Apr 13 2024
    18:30  SC Internacional        v EC Bahia                 2-1 (0-0)
    21:00  Fluminense FC           v RB Bragantino            2-2 (1-0)
  Sun Apr 14
    17:00  Cruzeiro EC             v Botafogo FR              3-2 (1-1)
    18:30  EC Vitória              v SE Palmeiras             0-1 (0-1)

▪ Matchday 2
  Wed Apr 17
    21:30  CR Flamengo             v São Paulo FC             2-1 (1-0)
"""


def test_score_to_label():
    assert score_to_label(2, 1) == "1"
    assert score_to_label(1, 1) == "X"
    assert score_to_label(0, 2) == "2"


def test_parse_football_txt():
    matches = parse_football_txt(SAMPLE_TXT, season=2024)
    assert len(matches) == 5
    assert matches[0].home_team == "Internacional"
    assert matches[0].away_team == "Bahia"
    assert matches[0].label == "1"
    assert matches[0].round_number == 1
    assert matches[0].home_score == 2
    assert matches[0].away_score == 1


def test_parse_date_without_year():
    from ingest.fixtures.parser import _parse_match_date

    dt = _parse_match_date("Jun 19", 2024)
    assert dt.year == 2024
    assert dt.month == 6
    assert dt.day == 19


COPA_SAMPLE = """
= Copa do Brasil 2025

▪ Round 1
  Tue Feb 18 2025
    18:00  Tocantinópolis TO       v Atlético Mineiro         0-2 (0-0)
           Boavista RJ             v CSA AL                   0-2 (0-2)
"""


def test_parse_copa_round():
    matches = parse_football_txt(COPA_SAMPLE, season=2025, competition="Copa do Brasil")
    assert len(matches) == 2
    assert matches[0].competition == "Copa do Brasil"
    assert matches[0].label == "2"
    assert matches[1].home_team_raw == "Boavista RJ"


def test_parse_fluminense_draw():
    matches = parse_football_txt(SAMPLE_TXT, season=2024)
    fluminense = next(m for m in matches if m.home_team == "Fluminense")
    assert fluminense.label == "X"
    assert fluminense.home_score == 2
    assert fluminense.away_score == 2
