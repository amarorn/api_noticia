"""Classificação de palpites Superbet → mercado canônico."""
from __future__ import annotations

from models.bet_pick_classify import (
    classify_superbet_pick,
    detect_period,
    handicap_line_key,
)


def test_handicap_line_key():
    assert handicap_line_key(-1.5) == "m1_5"
    assert handicap_line_key(0.5) == "p0_5"
    assert handicap_line_key(0.0) == "0"
    assert handicap_line_key(-0.5) == "m0_5"


def test_detect_period():
    assert detect_period("1º Tempo - Total de Gols") == "1h"
    assert detect_period("2º Tempo - Handicap") == "2h"
    assert detect_period("Total de Gols") == "ft"
    assert detect_period("Total de Gols (1º Tempo)") == "1h"


def test_classify_ft_handicap_asian():
    out = classify_superbet_pick(
        "Handicap Asiático",
        "Brasil -1.5",
        home_team="Brasil",
        away_team="Argentina",
    )
    assert out["market"] == "ft_ah_home_m1_5"
    assert out["outcome"] == "yes"
    assert out["target_value"] == "-1.5"


def test_classify_1h_handicap():
    out = classify_superbet_pick(
        "1º Tempo - Handicap",
        "México +0.5",
        home_team="México",
        away_team="África do Sul",
    )
    assert out["market"] == "1h_hcap_home_p0_5"
    assert out["outcome"] == "yes"


def test_classify_2h_handicap_away():
    out = classify_superbet_pick(
        "2º Tempo - Handicap Asiático",
        "Argentina -0.5",
        home_team="Brasil",
        away_team="Argentina",
    )
    assert out["market"] == "2h_ah_away_m0_5"
    assert out["outcome"] == "yes"


def test_classify_1h_totals_over():
    out = classify_superbet_pick(
        "1º Tempo - Total de Gols",
        "Mais de 0.5",
    )
    assert out["market"] == "1h_over_0_5"
    assert out["outcome"] == "yes"
    assert out["target_value"] == "0.5"


def test_classify_2h_totals_under():
    out = classify_superbet_pick(
        "2º Tempo - Total de Gols",
        "Menos de 1.5",
    )
    assert out["market"] == "2h_over_1_5"
    assert out["outcome"] == "no"


def test_classify_1h_h2h():
    out = classify_superbet_pick(
        "1º Tempo - Resultado Final",
        "X",
    )
    assert out["market"] == "1h_h2h"
    assert out["outcome"] == "draw"


def test_classify_ft_totals_legacy():
    out = classify_superbet_pick(
        "Total de Gols",
        "Mais de 2.5",
    )
    assert out["market"] == "totals_2.5"
    assert out["outcome"] == "over"


def test_classify_handicap_without_side_keeps_line():
    out = classify_superbet_pick("Handicap", "-1.5")
    assert out["market"] == "handicap"
    assert out["target_value"] == "-1.5"
