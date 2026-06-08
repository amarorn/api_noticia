"""Testes do módulo de momentum ao vivo (P1.1)."""
from models.wc_live_momentum import (
    MomentumContext,
    MomentumResult,
    GameEvent,
    adjust_lambdas,
    compute_momentum,
)


def test_momentum_neutral_0x0():
    """Jogo 0×0 antes de 70' → sem ajuste significativo."""
    ctx = MomentumContext(home_score=0, away_score=0, minute=30)
    result = compute_momentum(ctx)
    assert abs(result.home_factor - 1.0) < 0.01
    assert abs(result.away_factor - 1.0) < 0.01


def test_momentum_home_leading_2x0():
    """Casa na frente 2×0: casa recua (λ cai), fora pressiona (λ sobe)."""
    ctx = MomentumContext(home_score=2, away_score=0, minute=50)
    result = compute_momentum(ctx)
    assert result.home_factor < 1.0  # casa recua
    assert result.away_factor > 1.0  # fora pressiona
    assert len(result.reasons) > 0


def test_momentum_away_leading():
    """Fora na frente 0×1: casa pressiona, fora recua."""
    ctx = MomentumContext(home_score=0, away_score=1, minute=60)
    result = compute_momentum(ctx)
    assert result.home_factor > 1.0  # casa pressiona
    assert result.away_factor < 1.0  # fora recua


def test_momentum_late_game_compress():
    """Após 75' ambos os λ são comprimidos (reta final)."""
    ctx_early = MomentumContext(home_score=1, away_score=1, minute=50)
    ctx_late = MomentumContext(home_score=1, away_score=1, minute=80)
    r_early = compute_momentum(ctx_early)
    r_late = compute_momentum(ctx_late)
    # Em empate: reta final comprime ambos igualmente
    assert r_late.home_factor < r_early.home_factor
    assert r_late.away_factor < r_early.away_factor


def test_momentum_red_card_home():
    """Cartão vermelho para casa: casa perde ataque, fora ganha."""
    events = [GameEvent(event_type="red_card", minute=55, team="home")]
    ctx = MomentumContext(home_score=0, away_score=0, minute=60, events=events)
    result = compute_momentum(ctx)
    assert result.home_factor < 1.0
    assert result.away_factor > 1.0


def test_momentum_offensive_sub():
    """Substituição ofensiva da casa: λ_casa sobe."""
    events = [GameEvent(event_type="sub_offensive", minute=70, team="home")]
    ctx = MomentumContext(home_score=0, away_score=1, minute=72, events=events)
    result = compute_momentum(ctx)
    # Casa atrás E fez sub ofensiva → λ_casa deve subir bastante
    assert result.home_factor > 1.1


def test_momentum_clamp_limits():
    """Fatores nunca saem da faixa 0.50–1.80."""
    # Cenário extremo: fora ganhando de 4, com 2 reds da casa, min 87
    events = [
        GameEvent(event_type="red_card", minute=30, team="home"),
        GameEvent(event_type="red_card", minute=50, team="home"),
    ]
    ctx = MomentumContext(home_score=0, away_score=4, minute=87, events=events)
    result = compute_momentum(ctx)
    assert result.home_factor >= 0.50
    assert result.away_factor <= 1.80


def test_adjust_lambdas_integration():
    """adjust_lambdas retorna lambdas ajustados corretamente."""
    ctx = MomentumContext(home_score=2, away_score=0, minute=65)
    lam_h, lam_a, result = adjust_lambdas(1.5, 1.0, ctx)
    # Casa na frente: λ_home cai, λ_away sobe
    assert lam_h < 1.5
    assert lam_a > 1.0
    assert isinstance(result, MomentumResult)


def test_simulate_inplay_with_momentum():
    """simulate_inplay integra momentum sem erros."""
    from models.wc_inplay import simulate_inplay

    r = simulate_inplay(
        home_team="Brasil",
        away_team="Egito",
        home_score=2,
        away_score=0,
        minute=70,
        lambda_full_home=1.5,
        lambda_full_away=1.0,
        n_simulations=2000,
        random_seed=42,
        momentum_events=[
            {"event_type": "red_card", "minute": 60, "team": "away"},
        ],
    )
    # Com momentum: casa lidera + fora com red card
    # Prob casa deve ser alta
    assert r.prob_final_home > 0.7
    # λ_full reflete ajuste
    assert r.lambda_full_home != 1.5  # modificado por bayesian + momentum
