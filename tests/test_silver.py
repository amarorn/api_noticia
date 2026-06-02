import pytest

from pipelines.ner import extract_teams
from pipelines.silver import _simple_sentiment


def test_extract_teams():
    text = "Flamengo vence Palmeiras no Maracanã"
    teams = extract_teams(text)
    assert "Flamengo" in teams
    assert "Palmeiras" in teams


def test_sentiment_positive():
    score = _simple_sentiment("Flamengo garante vitória e se aproxima da liderança")
    assert score > 0


def test_sentiment_negative():
    score = _simple_sentiment("Time entra em crise após derrota e risco de rebaixamento")
    assert score < 0
