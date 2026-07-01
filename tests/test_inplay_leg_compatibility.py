"""Testes de compatibilidade de pernas in-play (Criar Aposta Superbet)."""

from models.inplay_leg_compatibility import (
    btts_conflicts_correct_score,
    combo_legs_compatible,
    correct_scores_conflict,
    handicap_conflicts_opposite_offense,
    handicaps_conflict,
    h2h_conflicts_handicap,
    is_superbet_bet_builder_market,
    legs_compatible,
)


def test_handicap_espelho_m1_5_vs_p1_5():
    assert handicaps_conflict("ft_hcap_home_m1_5", "ft_hcap_away_p1_5") is True


def test_dois_handicaps_mesmo_periodo():
    assert legs_compatible("ft_hcap_home_m0_5", "yes", "ft_hcap_home_m1_5", "yes") is False


def test_h2h_fora_conflita_handicap_mandante_m0_5():
    assert h2h_conflicts_handicap("h2h", "2", "ft_hcap_home_m0_5") is True


def test_h2h_casa_conflita_handicap_visitante_m0_5():
    assert h2h_conflicts_handicap("h2h", "1", "ft_hcap_away_m0_5") is True


def test_h2h_mesmo_time_que_handicap_conflita():
    """NZ vence + NZ handicap +0,5 — Superbet anula uma perna."""
    assert h2h_conflicts_handicap("h2h", "2", "ft_hcap_away_p0_5") is True
    assert legs_compatible("h2h", "2", "ft_hcap_away_p0_5", "yes") is False
    assert legs_compatible("h2h", "1", "ft_hcap_home_m0_5", "yes") is False


def test_handicap_nao_combina_over_mesmo_time():
    assert legs_compatible("ft_hcap_away_p0_5", "yes", "away_over_1_5", "yes") is False
    assert legs_compatible("ft_hcap_home_m0_5", "yes", "home_over_1_5", "yes") is False


def test_handicap_continua_com_totais_de_periodo_diferente():
    assert legs_compatible("ft_hcap_away_p0_5", "yes", "1h_over_2_5", "no") is True
    assert legs_compatible("ft_hcap_away_p0_5", "yes", "2h_over_2_5", "yes") is True


def test_totais_1t_aninhados():
    assert legs_compatible("1h_over_0_5", "no", "1h_over_1_5", "no") is False


def test_ah_excluido_criar_aposta():
    assert is_superbet_bet_builder_market("ft_ah_away_m0_8") is False
    assert is_superbet_bet_builder_market("ft_hcap_home_m1_5") is True


def test_handicap_2t_excluido():
    assert is_superbet_bet_builder_market("2h_hcap_away_m0_5") is False


def test_combo_max_um_handicap():
    legs = [
        ("ft_hcap_home_m1_5", "yes"),
        ("over_2_5", "yes"),
        ("btts", "yes"),
    ]
    assert combo_legs_compatible(legs) is True
    legs_two_hcap = [
        ("ft_hcap_home_m1_5", "yes"),
        ("ft_hcap_away_p1_5", "yes"),
    ]
    assert combo_legs_compatible(legs_two_hcap) is False


def test_dois_placares_exatos_mesmo_periodo():
    assert correct_scores_conflict("2h_cs_0_0", "2h_cs_1_0") is True
    assert legs_compatible("2h_cs_0_0", "yes", "2h_cs_1_0", "yes") is False


def test_combo_max_um_placar_exato():
    legs = [
        ("2h_cs_0_0", "yes"),
        ("2h_cs_1_0", "yes"),
    ]
    assert combo_legs_compatible(legs) is False


def test_btts_nao_combina_resultado_correto():
    assert btts_conflicts_correct_score("btts", "2h_cs_1_0") is True
    assert legs_compatible("btts", "yes", "2h_cs_1_0", "yes") is False
    assert legs_compatible("btts", "no", "1h_cs_0_0", "yes") is False


def test_btts_com_over_continua_ok():
    assert legs_compatible("btts", "yes", "over_2_5", "yes") is True


def test_periodos_diferentes_ok():
    assert legs_compatible("1h_hcap_home_m0_5", "yes", "2h_hcap_away_m0_5", "yes") is True


def test_visitante_m0_5_nao_combina_proximo_gol_mandante():
    assert handicap_conflicts_opposite_offense("ft_hcap_away_m0_5", "next_goal", "home") is True
    assert legs_compatible("ft_hcap_away_m0_5", "yes", "next_goal", "home") is False


def test_visitante_m0_5_nao_combina_mandante_4_gols():
    assert legs_compatible("ft_hcap_away_m0_5", "yes", "home_over_3_5", "yes") is False
    assert legs_compatible("ft_hcap_away_m0_5", "yes", "ft_exact_home_4", "yes") is False


def test_visitante_m0_5_continua_com_over_total_e_mandante_baixo():
    assert legs_compatible("ft_hcap_away_m0_5", "yes", "over_3_5", "yes") is True
    assert legs_compatible("ft_hcap_away_m0_5", "yes", "home_over_2_5", "yes") is True
    assert legs_compatible("ft_hcap_away_m0_5", "yes", "2h_over_1_5", "yes") is True


def test_combo_longshot_suecia_tunisia_incompativel():
    legs = [
        ("ft_hcap_away_m0_5", "yes"),
        ("over_3_5", "yes"),
        ("2h_over_1_5", "yes"),
        ("next_goal", "home"),
    ]
    assert combo_legs_compatible(legs) is False
