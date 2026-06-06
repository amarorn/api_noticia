"""Testes de normalização de linha para escalação (espelha frontend pitchPlacement)."""

from models.wc_match_simulator import _normalize_fept_player, _normalize_line_code


def test_normalize_line_code_sofascore_letters():
    assert _normalize_line_code("G") == "goleiro"
    assert _normalize_line_code("D") == "defesa"
    assert _normalize_line_code("M") == "meio"
    assert _normalize_line_code("F") == "ataque"


def test_normalize_fept_player_maps_forward_line():
    raw = {"nome": "Vinícius Jr.", "posicao": "F", "nota_sofascore": 6.9}
    mapped = _normalize_fept_player(raw)
    assert mapped is not None
    assert mapped["line"] == "ataque"
    assert mapped["sofascore_rating"] == 6.9
