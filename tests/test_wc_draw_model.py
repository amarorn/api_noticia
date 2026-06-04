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
