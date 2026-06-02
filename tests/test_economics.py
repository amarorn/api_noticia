from models.economics import (
    bootstrap_accuracy_ci,
    ces_blend_probabilities,
    coase_effective_min_edge,
    lgn_min_sample_warning,
)


def test_lgn_warning_small_sample():
    assert lgn_min_sample_warning(10, "test", min_n=30) is not None
    assert lgn_min_sample_warning(50, "test", min_n=30) is None


def test_coase_raises_min_edge():
    edge = coase_effective_min_edge(base_min_edge=0.03, bookmaker_margin=0.05)
    assert edge >= 0.08


def test_ces_blend_sums_to_one():
    models = {
        "a": {"1": 0.5, "X": 0.3, "2": 0.2},
        "b": {"1": 0.4, "X": 0.2, "2": 0.4},
    }
    out = ces_blend_probabilities(models, weights={"a": 0.5, "b": 0.5}, sigma=2.0)
    assert abs(sum(out.values()) - 1.0) < 1e-6


def test_bootstrap_ci():
    y = ["1", "2", "1", "X", "2"] * 20
    p = ["1", "2", "2", "X", "2"] * 20
    ci = bootstrap_accuracy_ci(y, p, n_bootstrap=100, seed=1)
    assert ci["mean"] is not None
    assert ci["ci_low"] <= ci["mean"] <= ci["ci_high"]
