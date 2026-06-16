"""Filtro de amistosos/seleções no poll Superbet."""
from pipelines.poll_superbet_live import is_international_match


def test_international_match_accepts_selecoes():
    assert is_international_match("Brasil", "Egito") is True
    assert is_international_match("Brazil", "Egypt") is True


def test_international_match_rejects_clubes():
    assert is_international_match("Loudoun United FC (F)", "Patuxent FA (F)") is False
    assert is_international_match("Augnablik Kopavogur", "KV Vesturbaer") is False
    assert is_international_match("Independiente Juniors", "Club Deportivo Cuenca Juniors") is False
