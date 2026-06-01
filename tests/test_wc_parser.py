import pytest

from ingest.fixtures.wc_parser import parse_world_cup_txt

SAMPLE_GROUP = """
= World Cup 2022

▪ Group G
Sun Nov 20
 19:00 Qatar 0-2 (0-2) Ecuador @ Al Bayt Stadium, Al Khor

Thu Nov 24
 22:00 Brazil 2-0 (0-0) Serbia @ Lusail Iconic Stadium, Lusail
"""

SAMPLE_KNOCKOUT = """
= World Cup 2022

▪ Round of 16
Sat Dec 3
   18:00     Netherlands      3-1 (2-0)   USA  @ Khalifa International Stadium
Mon Dec 5
   18:00     Japan             1-1 a.e.t (1-1, 1-0), 1-3 pen.  Croatia  @ Al Janoub Stadium
"""

SAMPLE_1994 = """
▪ Group A
June 18
 USA 1-1 Switzerland @ Pontiac Silverdome, Pontiac
 Colombia 1-3 Romania @ Rose Bowl, Pasadena
"""

SAMPLE_1998 = """
▪ Group A
10 June    Brazil      2-1    Scotland    @ Stade de France, Saint-Denis
16 June    Scotland    1-1    Norway      @ Parc Lescure, Bordeaux
"""

SAMPLE_2006 = """
▪ Group A
Fri Jun 9     Germany     4-2 (2-1)  Costa Rica   @ Allianz Arena, München
Tue Jun 20   Ecuador     0-3 (0-2)  Germany      @ Olympiastadion, Berlin
"""

SAMPLE_1986 = """
▪ Group A
31 May   Bulgaria       1-1    Italy   @ Estadio Azteca, Mexico City
2 June   Argentina      3-1    South Korea  @ Estadio Olímpico, Mexico City
"""


def test_parse_group_matches():
    matches = parse_world_cup_txt(SAMPLE_GROUP, season=2022)
    assert len(matches) == 2
    assert matches[0].home_team == "Catar"
    assert matches[0].away_team == "Equador"
    assert matches[0].label == "2"
    assert matches[0].group_name == "G"
    assert matches[1].home_team == "Brasil"
    assert matches[1].label == "1"


def test_parse_knockout_penalties():
    matches = parse_world_cup_txt(SAMPLE_KNOCKOUT, season=2022, default_phase="round_16")
    assert len(matches) == 2
    assert matches[0].phase == "round_16"
    assert matches[0].label == "1"
    assert matches[1].home_team == "Japão"
    assert matches[1].away_team == "Croácia"
    assert matches[1].label == "2"


def test_parse_1994_format():
    matches = parse_world_cup_txt(SAMPLE_1994, season=1994)
    assert len(matches) == 2
    assert matches[0].home_team == "Estados Unidos"
    assert matches[0].label == "X"
    assert matches[1].label == "2"


def test_parse_1998_inline_date():
    matches = parse_world_cup_txt(SAMPLE_1998, season=1998)
    assert len(matches) == 2
    assert matches[0].home_team == "Brasil"
    assert matches[0].away_team == "Escócia"
    assert matches[0].label == "1"


def test_parse_2006_inline_date():
    matches = parse_world_cup_txt(SAMPLE_2006, season=2006)
    assert len(matches) == 2
    assert matches[0].home_team == "Alemanha"
    assert matches[1].label == "2"


def test_parse_1986_inline_date():
    matches = parse_world_cup_txt(SAMPLE_1986, season=1986)
    assert len(matches) == 2
    assert matches[0].label == "X"
    assert matches[1].home_team == "Argentina"
