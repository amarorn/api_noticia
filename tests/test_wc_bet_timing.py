from models.wc_bet_timing import assess_bet_timing, build_fundamentacao


def test_assess_bet_timing_aguardar_when_edge_low():
    result = assess_bet_timing(
        event_id=None,
        market="over_2_5",
        outcome="yes",
        model_prob=0.52,
        implied_prob=0.50,
    )
    assert result["timing"] == "aguardar"
    assert "pp" in result["timing_reason"]


def test_build_fundamentacao_mentions_model_prob():
    text = build_fundamentacao(
        confidence={"score": 0.72, "label": "alta", "reason": "Elo e forma disponíveis."},
        market="2h_over_0_5",
        model_prob=0.68,
        implied_prob=0.55,
        edge_pp=13.0,
        minute=52,
    )
    assert "68%" in text or "0.68" in text.lower() or "68" in text
    assert "13.0 pp" in text or "13" in text
    assert "Confiança alta" in text
