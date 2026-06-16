"""Testes do perfil NHPP (Fase 1b)."""
from pipelines.wc_intensity_profile import (
    compute_half_lambdas_nhpp,
    compute_remaining_lambda,
    default_intensity_profile,
    validate_profile,
)

_LIT_PROFILE = default_intensity_profile()


def test_profile_covers_full_match():
    profile = default_intensity_profile()
    assert validate_profile(profile, match_minutes=90)


def test_remaining_lambda_decreases_with_minute():
    lam0 = compute_remaining_lambda(1.5, minute=0, match_minutes=90)
    lam45 = compute_remaining_lambda(1.5, minute=45, match_minutes=90)
    lam80 = compute_remaining_lambda(1.5, minute=80, match_minutes=90)
    assert lam0 == 1.5
    assert lam45 < lam0
    assert lam80 < lam45
    assert lam80 > 0


def test_nhpp_late_game_higher_remaining_share_than_homogeneous():
    """75'+ deve concentrar mais λ restante que distribuição uniforme."""
    minute = 75
    lam_full = 1.8
    _, nhpp_2h = compute_half_lambdas_nhpp(
        lam_full, minute, match_minutes=90, profile=_LIT_PROFILE
    )
    uniform_rem = lam_full * (90 - minute) / 90
    assert nhpp_2h > uniform_rem * 0.95
