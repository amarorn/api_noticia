"""Testes para KXL dinâmico ao vivo."""
from __future__ import annotations

import pytest

from models.wc_kxl_dynamic import (
    KXLState,
    KXLDynamic,
    apply_kxl_dynamic_to_lambda,
)


def test_kxl_state_defaults():
    s = KXLState()
    assert s.attack_factor == 1.0
    assert s.defense_factor == 1.0
    assert s.energy == 1.0


def test_kxl_from_empty_context():
    kxl = KXLDynamic.from_match_context(None)
    assert kxl.home_state.attack_factor == 1.0
    assert kxl.away_state.attack_factor == 1.0


def test_kxl_from_context_with_factors():
    ctx = {
        "kxl_factors": {
            "home_attack": 1.15,
            "home_defense": 0.95,
            "away_attack": 0.90,
            "away_defense": 1.05,
        },
        "home_energy": 1.1,
        "away_energy": 0.95,
    }
    kxl = KXLDynamic.from_match_context(ctx)
    assert kxl.home_state.attack_factor == 1.15
    assert kxl.home_state.energy == 1.1
    assert kxl.away_state.attack_factor == 0.90


def test_kxl_apply_goal():
    kxl = KXLDynamic()
    kxl.apply_event("goal", team="home", minute=23)
    # Home: ataque +8%, moral +10%
    assert kxl.home_state.attack_factor == pytest.approx(1.08, abs=0.01)
    assert kxl.home_state.morale == pytest.approx(1.10, abs=0.01)
    # Away: defesa -5%, moral -8%
    assert kxl.away_state.defense_factor == pytest.approx(0.95, abs=0.01)
    assert kxl.away_state.morale == pytest.approx(0.92, abs=0.01)


def test_kxl_apply_red_card():
    kxl = KXLDynamic()
    kxl.apply_event("red_card", team="away", minute=38)
    # Away: ataque -20%, defesa -15%
    assert kxl.away_state.attack_factor == pytest.approx(0.80, abs=0.01)
    # Home: ataque +7.5% (aproveita vantagem)
    assert kxl.home_state.attack_factor == pytest.approx(1.075, abs=0.01)


def test_kxl_apply_substitution_offensive():
    kxl = KXLDynamic()
    kxl.apply_event("substitution", team="home", minute=60, detail="offensive")
    assert kxl.home_state.attack_factor == pytest.approx(1.06, abs=0.01)


def test_kxl_apply_substitution_defensive():
    kxl = KXLDynamic()
    kxl.apply_event("substitution", team="home", minute=60, detail="defensive")
    assert kxl.home_state.defense_factor == pytest.approx(1.05, abs=0.01)


def test_kxl_compute_factors():
    kxl = KXLDynamic()
    kxl.apply_event("goal", team="home", minute=23)
    factors = kxl.compute_factors(minute=45)
    assert "home_attack" in factors
    assert "away_defense" in factors
    assert factors["home_attack"] > 1.0  # gol home aumenta ataque
    assert factors["away_defense"] < 1.0  # away sofreu gol = defesa pior


def test_kxl_compute_factors_clamped():
    """Garante que fatores não saem dos limites."""
    kxl = KXLDynamic()
    # 10 gols = boost excessivo
    for _ in range(10):
        kxl.apply_event("goal", team="home", minute=23)
    factors = kxl.compute_factors(minute=45)
    assert factors["home_attack"] <= 2.0
    assert factors["home_attack"] >= 0.5


def test_apply_kxl_to_lambda():
    factors = {
        "home_attack": 1.2,
        "home_defense": 1.0,
        "away_attack": 0.9,
        "away_defense": 0.95,
    }
    lam_h, lam_a, meta = apply_kxl_dynamic_to_lambda(1.5, 1.2, factors)
    # home λ = 1.5 * (1.2 / 0.95) = 1.5 * 1.263 = 1.895
    assert lam_h > 1.5
    # away λ = 1.2 * (0.9 / 1.0) = 1.08
    assert lam_a < 1.2
    assert meta["applied"] is True
    assert meta["source"] == "kxl_dynamic"


def test_kxl_multiple_events():
    kxl = KXLDynamic()
    kxl.apply_event("goal", team="home", minute=15)
    kxl.apply_event("red_card", team="away", minute=38)
    kxl.apply_event("substitution", team="home", minute=60, detail="offensive")
    factors = kxl.compute_factors(minute=75)
    assert len(kxl.events) == 3
    assert factors["n_events"] == 3
    # Home deve estar fortemente favorecido
    assert factors["home_attack"] > 1.2


def test_kxl_time_decay():
    kxl = KXLDynamic()
    kxl.home_state.energy = 1.0
    factors_60 = kxl.compute_factors(minute=60)
    factors_85 = kxl.compute_factors(minute=85)
    # Após 70', energia decai
    assert factors_85["home_energy"] < factors_60["home_energy"]
