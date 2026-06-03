from pipelines.wc_baselines import (
    baseline_outcome_probs,
    blend_with_baseline,
    get_baseline_snapshot,
    load_team_baselines,
    resolve_baseline_team,
)


def test_loads_48_teams():
    teams = load_team_baselines()
    assert len(teams) >= 45
    assert "Brasil" in teams
    assert "Holanda" in teams or "Países Baixos" in teams


def test_resolve_paises_baixos_to_holanda():
    assert resolve_baseline_team("Países Baixos") == "Holanda"


def test_brasil_marrocos_baseline():
    out = baseline_outcome_probs("Brasil", "Marrocos")
    assert out is not None
    assert out.prob_home > out.prob_away
    assert out.matchup.sector_note


def test_blend_keeps_normalization():
    ph, pd, pa, _ = blend_with_baseline(0.5, 0.25, 0.25, "Brasil", "Marrocos", weight=0.25)
    assert abs(ph + pd + pa - 1.0) < 1e-6


def test_snapshot_indices_in_range():
    snap = get_baseline_snapshot("Brasil")
    assert snap is not None
    assert 0 < snap.attack_index < 2
    assert 0 < snap.defense_index < 2
