"""Testes do resolvedor de times ao vivo."""
from ingest.superbet.team_resolver import (
    classify_live_match,
    is_brazilian_club,
    is_international_match,
    looks_like_club,
    resolve_live_team,
)


def test_resolve_brazilian_club():
    assert resolve_live_team("CR Flamengo") == "Flamengo"
    assert is_brazilian_club("Flamengo")


def test_international_match():
    assert is_international_match("Brasil", "Egito") is True
    assert is_international_match("Flamengo", "Palmeiras") is False


def test_classify_club_match():
    home, away, kind = classify_live_match("Flamengo", "Palmeiras")
    assert kind == "club"
    assert home == "Flamengo"
    assert away == "Palmeiras"


def test_classify_national_match():
    _, _, kind = classify_live_match("Brasil", "Egito")
    assert kind == "national"


def test_looks_like_club_marker():
    assert looks_like_club("Loudoun United FC (F)") is True
