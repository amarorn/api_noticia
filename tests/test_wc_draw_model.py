from models.wc_draw_model import apply_two_stage_probs


def test_two_stage_increases_draw_mass():
    base = {"1": 0.55, "X": 0.10, "2": 0.35}
    out = apply_two_stage_probs(base, p_draw=0.28, blend=1.0, knockout=False)
    assert out["X"] > base["X"]
    assert abs(sum(out.values()) - 1.0) < 1e-6


def test_knockout_discounts_draw():
    out = apply_two_stage_probs(
        {"1": 0.4, "X": 0.25, "2": 0.35},
        p_draw=0.30,
        blend=1.0,
        knockout=True,
    )
    group = apply_two_stage_probs(
        {"1": 0.4, "X": 0.25, "2": 0.35},
        p_draw=0.30,
        blend=1.0,
        knockout=False,
    )
    assert out["X"] <= group["X"]


def test_resolve_wc_outcome_balanced_draw():
    from models.wc_draw_model import resolve_wc_outcome

    probs = {"1": 0.415, "X": 0.267, "2": 0.318}
    assert resolve_wc_outcome(probs, phase="group") == "X"


def test_resolve_wc_outcome_clear_home_win():
    from models.wc_draw_model import resolve_wc_outcome

    probs = {"1": 0.565, "X": 0.267, "2": 0.167}
    assert resolve_wc_outcome(probs, phase="group") == "1"


def test_resolve_wc_outcome_knockout_stricter():
    from models.wc_draw_model import resolve_wc_outcome

    probs = {"1": 0.415, "X": 0.267, "2": 0.318}
    assert resolve_wc_outcome(probs, phase="round_16") != "X"


def test_resolve_wc_outcome_competitive_margin():
    from models.wc_draw_model import resolve_wc_outcome

    # Portugal x USA style: favorito visitante por pouco, P(X) alta
    probs = {"1": 0.361, "X": 0.265, "2": 0.374}
    assert resolve_wc_outcome(probs, phase="group") == "X"
