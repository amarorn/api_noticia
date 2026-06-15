"""Testes do painel de mercados viáveis do 2º tempo."""

from models.wc_viable_2h_markets import build_viable_2h_markets


def _row(market: str, *, prob: float = 0.22, ev: float = 0.08, odd: float = 3.5):
    return {
        "market": market,
        "outcome": "yes",
        "label": market,
        "model_prob": prob,
        "market_odd": odd,
        "expected_value": ev,
        "edge_pp": 8.0,
        "implied_prob": 0.14,
        "meets_threshold": ev > 0.05,
    }


def test_fechado_antes_intervalo():
    out = build_viable_2h_markets([_row("2h_over_0_5")], minute=30)
    assert out["closed"] is True
    assert out["markets"] == []


def test_lista_mercados_2t_no_segundo_tempo():
    scan = [
        {**_row("2h_over_0_5", prob=0.55), "label": "2º Tempo: mais de 0.5 gols"},
        _row("2h_cs_1_0", prob=0.12),
        _row("h2h", prob=0.4),
        _row("2h_hcap_home_m0_5", prob=0.03),
    ]
    out = build_viable_2h_markets(scan, minute=60, remaining_fraction=0.33)
    assert out["available"] is True
    assert out["minutes_remaining"] == 30
    assert all(m["market"].startswith("2h_") for m in out["markets"])
    assert out["markets"][0]["model_prob"] >= 0.06
    assert len(out["chart"]["categories"]) >= 1


def test_fechado_apos_corte_2t():
    out = build_viable_2h_markets([_row("2h_over_0_5")], minute=85)
    assert out["closed"] is True
