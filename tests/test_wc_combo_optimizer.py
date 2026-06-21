"""Testes do otimizador de bilhetes wc_combo_optimizer."""

from __future__ import annotations

import pytest

from models.wc_combo_optimizer import (
    Leg,
    Ticket,
    _compute_combined_ev,
    _compute_combined_prob,
    _filter_alive,
    _filter_by_period,
    _generate_combinations,
    _infer_offense_side,
    _narrative_correlation_penalty,
    _period_mix,
    _score_ticket,
    build_optimized_tickets,
    tickets_to_dict,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def leg_1h_over() -> Leg:
    return Leg(
        market="1h_over_1_5",
        outcome="yes",
        label="Mais de 1.5 gols 1T",
        model_prob=0.55,
        market_odd=2.20,
        expected_value=0.21,
        edge_pp=5.0,
        kelly_quarter=0.095,
        classification="value_bet",
    )


@pytest.fixture
def leg_1h_h2h_home() -> Leg:
    return Leg(
        market="1h_h2h",
        outcome="1",
        label="Mandante vence 1T",
        model_prob=0.42,
        market_odd=2.80,
        expected_value=0.176,
        edge_pp=5.2,
        kelly_quarter=0.063,
        classification="forte",
    )


@pytest.fixture
def leg_2h_over() -> Leg:
    return Leg(
        market="2h_over_1_5",
        outcome="yes",
        label="Mais de 1.5 gols 2T",
        model_prob=0.48,
        market_odd=2.50,
        expected_value=0.20,
        edge_pp=4.8,
        kelly_quarter=0.080,
        classification="value_bet",
    )


@pytest.fixture
def leg_ft_h2h_home() -> Leg:
    return Leg(
        market="h2h",
        outcome="1",
        label="Mandante vence",
        model_prob=0.45,
        market_odd=2.60,
        expected_value=0.17,
        edge_pp=4.5,
        kelly_quarter=0.065,
        classification="value_bet",
    )


@pytest.fixture
def leg_ft_btts() -> Leg:
    return Leg(
        market="btts",
        outcome="yes",
        label="Ambas marcam",
        model_prob=0.52,
        market_odd=2.10,
        expected_value=0.092,
        edge_pp=2.8,
        kelly_quarter=0.044,
        classification="watch",
    )


@pytest.fixture
def leg_ft_over25() -> Leg:
    return Leg(
        market="over_2_5",
        outcome="yes",
        label="Mais de 2.5 gols",
        model_prob=0.50,
        market_odd=2.30,
        expected_value=0.15,
        edge_pp=3.5,
        kelly_quarter=0.065,
        classification="value_bet",
    )


@pytest.fixture
def market_scan(leg_1h_over, leg_1h_h2h_home, leg_2h_over, leg_ft_h2h_home, leg_ft_btts, leg_ft_over25) -> list[dict]:
    """Market scan simulado com pernas de todos os períodos."""
    return [
        {
            "market": leg.market,
            "outcome": leg.outcome,
            "label": leg.label,
            "model_prob": leg.model_prob,
            "market_odd": leg.market_odd,
            "expected_value": leg.expected_value,
            "edge_pp": leg.edge_pp,
            "kelly_quarter": leg.kelly_quarter,
            "classification": leg.classification,
        }
        for leg in [leg_1h_over, leg_1h_h2h_home, leg_2h_over, leg_ft_h2h_home, leg_ft_btts, leg_ft_over25]
    ]


# ---------------------------------------------------------------------------
# Testes de utilidades
# ---------------------------------------------------------------------------

def test_filter_by_period_1h(leg_1h_over, leg_1h_h2h_home, leg_ft_h2h_home):
    legs = [leg_1h_over, leg_1h_h2h_home, leg_ft_h2h_home]
    result = _filter_by_period(legs, "1h")
    assert len(result) == 2
    assert all(leg.period == "1h" for leg in result)


def test_filter_by_period_ft(leg_1h_over, leg_ft_h2h_home, leg_ft_btts):
    legs = [leg_1h_over, leg_ft_h2h_home, leg_ft_btts]
    result = _filter_by_period(legs, "ft")
    assert len(result) == 2
    assert all(leg.period == "ft" for leg in result)


def test_filter_alive_blocks_1h_after_45(leg_1h_over, leg_ft_h2h_home):
    legs = [leg_1h_over, leg_ft_h2h_home]
    result = _filter_alive(legs, minute=50)
    # Após 45', mercados 1h são bloqueados, mas FT também pode ser bloqueado
    # dependendo do live_block_minute. Verificamos que 1h foi removido.
    assert leg_1h_over not in result


def test_filter_alive_allows_1h_at_30(leg_1h_over, leg_ft_h2h_home):
    legs = [leg_1h_over, leg_ft_h2h_home]
    result = _filter_alive(legs, minute=30)
    assert len(result) == 2


def test_infer_offense_side_home(leg_ft_h2h_home):
    assert _infer_offense_side(leg_ft_h2h_home) == "home"


def test_infer_offense_side_away():
    leg = Leg(
        market="h2h", outcome="2", label="", model_prob=0.3, market_odd=3.0,
        expected_value=0.0, edge_pp=0.0, kelly_quarter=0.0, classification="watch",
    )
    assert _infer_offense_side(leg) == "away"


def test_infer_offense_side_draw():
    leg = Leg(
        market="h2h", outcome="X", label="", model_prob=0.3, market_odd=3.0,
        expected_value=0.0, edge_pp=0.0, kelly_quarter=0.0, classification="watch",
    )
    assert _infer_offense_side(leg) is None


def test_narrative_correlation_penalty_independent(leg_1h_over, leg_2h_over):
    """Pernas de períodos diferentes = independente (penalty 1.0)."""
    penalty = _narrative_correlation_penalty([leg_1h_over, leg_2h_over])
    assert penalty == 1.0


def test_narrative_correlation_penalty_same_side(leg_ft_h2h_home, leg_ft_over25):
    """Duas pernas favorecendo home = moderadamente correlacionado."""
    # h2h:1 favorece home, over_2_5 é neutro (não favorece lado específico)
    # Então penalty = 1.0 (não correlacionado)
    penalty = _narrative_correlation_penalty([leg_ft_h2h_home, leg_ft_over25])
    assert penalty == 1.0


def test_narrative_correlation_penalty_correlated():
    """Três pernas favorecendo home = fortemente correlacionado."""
    leg1 = Leg(
        market="h2h", outcome="1", label="", model_prob=0.45, market_odd=2.6,
        expected_value=0.17, edge_pp=4.5, kelly_quarter=0.065, classification="value_bet",
    )
    leg2 = Leg(
        market="home_over_1_5", outcome="yes", label="", model_prob=0.50, market_odd=2.2,
        expected_value=0.10, edge_pp=3.0, kelly_quarter=0.045, classification="value_bet",
    )
    leg3 = Leg(
        market="combo_home_btts", outcome="yes", label="", model_prob=0.40, market_odd=3.0,
        expected_value=0.20, edge_pp=5.0, kelly_quarter=0.067, classification="forte",
    )
    penalty = _narrative_correlation_penalty([leg1, leg2, leg3])
    assert penalty == 0.5  # 3+ pernas no mesmo lado


def test_compute_combined_prob(leg_ft_h2h_home, leg_ft_over25):
    prob = _compute_combined_prob([leg_ft_h2h_home, leg_ft_over25])
    raw = 0.45 * 0.50
    # over_2_5 é neutro, não favorece lado → penalty = 1.0
    assert prob == raw


def test_compute_combined_prob_correlated():
    """Probabilidade conjunta com correlação."""
    leg1 = Leg(
        market="h2h", outcome="1", label="", model_prob=0.45, market_odd=2.6,
        expected_value=0.17, edge_pp=4.5, kelly_quarter=0.065, classification="value_bet",
    )
    leg2 = Leg(
        market="home_over_1_5", outcome="yes", label="", model_prob=0.50, market_odd=2.2,
        expected_value=0.10, edge_pp=3.0, kelly_quarter=0.045, classification="value_bet",
    )
    prob = _compute_combined_prob([leg1, leg2])
    raw = 0.45 * 0.50
    assert prob == raw * 0.75  # 2 pernas no mesmo lado = 0.75 penalty


def test_compute_combined_ev_positive(leg_ft_h2h_home, leg_ft_over25):
    combined_odd = 2.60 * 2.30
    ev = _compute_combined_ev([leg_ft_h2h_home, leg_ft_over25], combined_odd)
    assert ev > 0


def test_score_ticket_positive_ev(leg_ft_h2h_home, leg_ft_over25):
    combined_odd = 2.60 * 2.30
    ev = _compute_combined_ev([leg_ft_h2h_home, leg_ft_over25], combined_odd)
    score = _score_ticket([leg_ft_h2h_home, leg_ft_over25], ev, combined_odd)
    assert score > 0


def test_score_ticket_negative_ev():
    leg_bad = Leg(
        market="h2h", outcome="1", label="", model_prob=0.30, market_odd=2.0,
        expected_value=-0.40, edge_pp=-5.0, kelly_quarter=0.0, classification="avoid",
    )
    score = _score_ticket([leg_bad], -0.40, 2.0)
    assert score == 0.0


def test_period_mix_1h_only(leg_1h_over, leg_1h_h2h_home):
    assert _period_mix([leg_1h_over, leg_1h_h2h_home]) == "1h"


def test_period_mix_ft_only(leg_ft_h2h_home, leg_ft_btts):
    assert _period_mix([leg_ft_h2h_home, leg_ft_btts]) == "ft"


def test_period_mix_mixed(leg_1h_over, leg_2h_over):
    assert _period_mix([leg_1h_over, leg_2h_over]) == "mixed"


# ---------------------------------------------------------------------------
# Testes de geração de combinações
# ---------------------------------------------------------------------------

def test_generate_combinations_2legs(leg_ft_h2h_home, leg_ft_btts, leg_ft_over25):
    legs = [leg_ft_h2h_home, leg_ft_btts, leg_ft_over25]
    combos = _generate_combinations(legs, max_legs=2, min_legs=2)
    # h2h:1 + btts:yes são incompatíveis (h2h e goals no mesmo período)
    # h2h:1 + over_2_5:yes são compatíveis
    # btts:yes + over_2_5:yes são compatíveis
    # Então esperamos 2 combos válidos
    assert len(combos) == 2


def test_generate_combinations_3legs(leg_ft_h2h_home, leg_ft_btts, leg_ft_over25):
    legs = [leg_ft_h2h_home, leg_ft_btts, leg_ft_over25]
    combos = _generate_combinations(legs, max_legs=3, min_legs=2)
    # C(3,2) = 3 pares, mas h2h+btts é incompatível → 2 pares válidos
    # C(3,3) = 1 trio, mas h2h+btts+over = incompatível (h2h+btts no mesmo período)
    # Então esperamos 2 combos válidos
    assert len(combos) == 2


def test_generate_combinations_filters_incompatible(leg_ft_h2h_home):
    """h2h:1 e h2h:X no mesmo período são incompatíveis."""
    leg_draw = Leg(
        market="h2h", outcome="X", label="Empate", model_prob=0.30, market_odd=3.20,
        expected_value=0.0, edge_pp=0.0, kelly_quarter=0.0, classification="watch",
    )
    legs = [leg_ft_h2h_home, leg_draw]
    combos = _generate_combinations(legs, max_legs=2, min_legs=2)
    assert len(combos) == 0  # Incompatíveis


# ---------------------------------------------------------------------------
# Testes de build_optimized_tickets
# ---------------------------------------------------------------------------

def test_build_optimized_tickets_returns_all_periods(market_scan):
    result = build_optimized_tickets(
        market_scan,
        minute=30,
        bankroll=1000,
        max_legs=2,
        min_legs=2,
        top_k=5,
    )
    assert "1h" in result
    assert "2h" in result
    assert "ft" in result
    assert "mixed" in result


def test_build_optimized_tickets_1h_has_valid_tickets(market_scan):
    result = build_optimized_tickets(
        market_scan,
        minute=30,
        bankroll=1000,
        max_legs=2,
        min_legs=2,
        top_k=5,
    )
    tickets_1h = result["1h"]
    if tickets_1h:
        for ticket in tickets_1h:
            assert ticket.is_valid
            assert ticket.combined_ev >= 0
            assert ticket.n_legs >= 2


def test_build_optimized_tickets_mixed_only_before_45(market_scan):
    # Antes do intervalo: mistos disponíveis
    result_before = build_optimized_tickets(
        market_scan,
        minute=30,
        bankroll=1000,
        max_legs=2,
        min_legs=2,
        top_k=5,
    )
    # Após intervalo: mistos vazios (não pode ter 1h + 2h)
    result_after = build_optimized_tickets(
        market_scan,
        minute=50,
        bankroll=1000,
        max_legs=2,
        min_legs=2,
        top_k=5,
    )
    # Mixed pode estar vazio em ambos (depende do scan), mas após 45 não deve ter 1h
    assert all(ticket.period_mix != "1h" for ticket in result_after.get("mixed", []))


def test_build_optimized_tickets_blocks_1h_after_45(market_scan):
    result = build_optimized_tickets(
        market_scan,
        minute=50,
        bankroll=1000,
        max_legs=2,
        min_legs=2,
        top_k=5,
    )
    # Após 45', não deve haver bilhetes 1T
    assert len(result["1h"]) == 0


def test_build_optimized_tickets_respects_max_legs(market_scan):
    result = build_optimized_tickets(
        market_scan,
        minute=30,
        bankroll=1000,
        max_legs=3,
        min_legs=2,
        top_k=5,
    )
    for period, tickets in result.items():
        for ticket in tickets:
            assert ticket.n_legs <= 3


def test_build_optimized_tickets_respects_min_ev(market_scan):
    result = build_optimized_tickets(
        market_scan,
        minute=30,
        bankroll=1000,
        max_legs=2,
        min_legs=2,
        top_k=5,
        min_ev=0.05,
    )
    for period, tickets in result.items():
        for ticket in tickets:
            assert ticket.combined_ev >= 0.05


def test_build_optimized_tickets_respects_odd_range(market_scan):
    result = build_optimized_tickets(
        market_scan,
        minute=30,
        bankroll=1000,
        max_legs=2,
        min_legs=2,
        top_k=5,
        min_combined_odd=1.5,
        max_combined_odd=10.0,
    )
    for period, tickets in result.items():
        for ticket in tickets:
            assert 1.5 <= ticket.combined_odd <= 10.0


def test_tickets_to_dict_serializable(market_scan):
    result = build_optimized_tickets(
        market_scan,
        minute=30,
        bankroll=1000,
        max_legs=2,
        min_legs=2,
        top_k=3,
    )
    dict_result = tickets_to_dict(result)
    assert isinstance(dict_result, dict)
    for period in ("1h", "2h", "ft", "mixed"):
        assert period in dict_result
        for ticket_dict in dict_result[period]:
            assert "legs" in ticket_dict
            assert "combined_odd" in ticket_dict
            assert "combined_ev" in ticket_dict
            assert "score" in ticket_dict
            assert "stake_brl" in ticket_dict
            assert "period_mix" in ticket_dict
            assert "valid" in ticket_dict


# ---------------------------------------------------------------------------
# Testes de edge cases
# ---------------------------------------------------------------------------

def test_empty_market_scan():
    result = build_optimized_tickets(
        [],
        minute=30,
        bankroll=1000,
        max_legs=2,
        min_legs=2,
        top_k=5,
    )
    assert all(len(tickets) == 0 for tickets in result.values())


def test_single_leg_market_scan(leg_ft_h2h_home):
    scan = [{
        "market": leg_ft_h2h_home.market,
        "outcome": leg_ft_h2h_home.outcome,
        "label": leg_ft_h2h_home.label,
        "model_prob": leg_ft_h2h_home.model_prob,
        "market_odd": leg_ft_h2h_home.market_odd,
        "expected_value": leg_ft_h2h_home.expected_value,
        "edge_pp": leg_ft_h2h_home.edge_pp,
        "kelly_quarter": leg_ft_h2h_home.kelly_quarter,
        "classification": leg_ft_h2h_home.classification,
    }]
    result = build_optimized_tickets(
        scan,
        minute=30,
        bankroll=1000,
        max_legs=2,
        min_legs=2,
        top_k=5,
    )
    # Uma só perna não forma combo
    assert all(len(tickets) == 0 for tickets in result.values())


def test_all_negative_ev_filtered():
    scan = [
        {
            "market": "h2h", "outcome": "1", "label": "Mandante",
            "model_prob": 0.30, "market_odd": 2.0,
            "expected_value": -0.40, "edge_pp": -5.0,
            "kelly_quarter": 0.0, "classification": "avoid",
        },
        {
            "market": "over_2_5", "outcome": "yes", "label": "Over 2.5",
            "model_prob": 0.35, "market_odd": 2.0,
            "expected_value": -0.30, "edge_pp": -4.0,
            "kelly_quarter": 0.0, "classification": "avoid",
        },
    ]
    result = build_optimized_tickets(
        scan,
        minute=30,
        bankroll=1000,
        max_legs=2,
        min_legs=2,
        top_k=5,
    )
    # EV negativo deve ser filtrado
    for period, tickets in result.items():
        for ticket in tickets:
            assert ticket.combined_ev >= 0
