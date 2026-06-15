"""Testes de bilhetes in-play por período."""

from models.wc_inplay_half_tickets import build_inplay_half_tickets


def _row(market: str, *, ev: float = 0.12, edge: float = 6.0, odd: float = 2.1, prob: float = 0.52):
    return {
        "market": market,
        "outcome": "yes",
        "label": market,
        "model_prob": prob,
        "market_odd": odd,
        "expected_value": ev,
        "edge_pp": edge,
        "meets_threshold": True,
        "suggested_stake_pct": 2.0,
        "suggested_stake_value": 20.0,
    }


def test_separa_1t_e_2t():
    scan = [
        {**_row("1h_h2h"), "outcome": "1", "label": "1T casa"},
        _row("2h_over_0_5"),
        _row("h2h", ev=0.05),
    ]
    tickets = build_inplay_half_tickets(scan, minute=30, bankroll=1000)
    assert len(tickets["first_half"]["singles"]) == 1
    assert len(tickets["second_half"]["singles"]) == 1
    assert tickets["first_half"]["available"] is True


def test_1t_fechado_no_intervalo():
    scan = [_row("1h_h2h")]
    scan[0]["market"] = "1h_h2h"
    tickets = build_inplay_half_tickets(scan, minute=46, bankroll=1000)
    assert tickets["first_half"]["closed"] is True
    assert tickets["first_half"]["combos"] == []


def test_nao_monta_dupla_under_aninhado_1t():
    """Menos 0.5 e menos 1.5 no 1T são correlacionados — não podem ir juntos."""
    scan = [
        {**_row("1h_over_0_5", odd=3.25), "outcome": "no", "label": "1T menos 0.5"},
        {**_row("1h_over_1_5", odd=13.0), "outcome": "no", "label": "1T menos 1.5"},
        _row("1h_h2h", odd=2.85),
    ]
    tickets = build_inplay_half_tickets(scan, minute=20, bankroll=1000)
    for combo in tickets["first_half"]["combos"]:
        markets = {leg["market"] for leg in combo["legs"]}
        assert not {"1h_over_0_5", "1h_over_1_5"}.issubset(markets)


def test_monta_dupla_mista():
    scan = [
        {**_row("1h_over_0_5"), "outcome": "yes", "label": "1T over 0.5"},
        {**_row("2h_over_0_5"), "outcome": "yes", "label": "2T over 0.5"},
    ]
    tickets = build_inplay_half_tickets(scan, minute=20, bankroll=1000)
    assert len(tickets["mixed_combos"]) >= 1
    assert len(tickets["mixed_combos"][0]["legs"]) == 2


def test_2t_disponivel_no_segundo_tempo():
    scan = [{**_row("2h_over_0_5"), "label": "2T over 0.5"}]
    tickets = build_inplay_half_tickets(scan, minute=60, bankroll=1000)
    assert tickets["second_half"]["closed"] is False
    assert len(tickets["second_half"]["singles"]) == 1
