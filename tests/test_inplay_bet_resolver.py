"""Testes de resolução de apostas in-play a partir do placar final."""

from pipelines.inplay_bet_resolver import GameResult, resolve_bet


# ---------------------------------------------------------------------------
# Fixtures de resultado
# ---------------------------------------------------------------------------

R_1_0 = GameResult(ft_home=1, ft_away=0, ht_home=1, ht_away=0)
R_0_0 = GameResult(ft_home=0, ft_away=0, ht_home=0, ht_away=0)
R_2_1 = GameResult(ft_home=2, ft_away=1, ht_home=1, ht_away=0)
R_1_3 = GameResult(ft_home=1, ft_away=3, ht_home=1, ht_away=2)
R_3_0 = GameResult(ft_home=3, ft_away=0, ht_home=2, ht_away=0)
# Sem placar de intervalo
R_2_1_NO_HT = GameResult(ft_home=2, ft_away=1)


# ---------------------------------------------------------------------------
# H2H
# ---------------------------------------------------------------------------

def test_h2h_casa_vence():
    assert resolve_bet("h2h", "1", R_1_0) is True

def test_h2h_empate():
    assert resolve_bet("h2h", "X", R_0_0) is True

def test_h2h_fora_vence():
    assert resolve_bet("h2h", "2", R_1_3) is True

def test_h2h_errado():
    assert resolve_bet("h2h", "2", R_1_0) is False

def test_ft_h2h():
    assert resolve_bet("ft_h2h", "1", R_1_0) is True

def test_1h_h2h():
    # 1T: ht_home=1, ht_away=0 → casa vence 1T
    assert resolve_bet("1h_h2h", "1", R_1_0) is True
    assert resolve_bet("1h_h2h", "X", R_1_0) is False

def test_1h_h2h_sem_intervalo():
    assert resolve_bet("1h_h2h", "1", R_2_1_NO_HT) is None

def test_2h_h2h():
    # 2T: ft=2-1, ht=1-0 → 2T=1-1 empate
    assert resolve_bet("2h_h2h", "X", R_2_1) is True
    assert resolve_bet("2h_h2h", "1", R_2_1) is False


# ---------------------------------------------------------------------------
# Handicap europeu
# ---------------------------------------------------------------------------

def test_hcap_away_p0_5_ganha():
    # ft=1-0, away+0.5: adjusted = 0+0.5-1 = -0.5 → perde
    assert resolve_bet("ft_hcap_away_p0_5", "yes", R_1_0) is False

def test_hcap_away_p0_5_empate():
    # ft=0-0, away+0.5: adjusted = 0+0.5-0 = 0.5 → ganha
    assert resolve_bet("ft_hcap_away_p0_5", "yes", R_0_0) is True

def test_hcap_home_m0_5_ganha():
    # ft=1-0, home-0.5: adjusted = 1-0.5-0 = 0.5 → ganha
    assert resolve_bet("ft_hcap_home_m0_5", "yes", R_1_0) is True

def test_hcap_home_m0_5_perde():
    # ft=0-0, home-0.5: adjusted = 0-0.5-0 = -0.5 → perde
    assert resolve_bet("ft_hcap_home_m0_5", "yes", R_0_0) is False

def test_hcap_away_p1_5_1t():
    # ht=1-0, away+1.5: adjusted = 0+1.5-1 = 0.5 → ganha (casa não vence por 2+)
    assert resolve_bet("1h_hcap_away_p1_5", "yes", R_1_0) is True

def test_hcap_2t():
    # ft=2-1, ht=1-0 → 2T=1-1; home-0.5 no 2T: 1-0.5-1 = -0.5 → perde
    assert resolve_bet("2h_hcap_home_m0_5", "yes", R_2_1) is False

def test_hcap_2t_sem_intervalo():
    assert resolve_bet("2h_hcap_away_p0_5", "yes", R_2_1_NO_HT) is None


# ---------------------------------------------------------------------------
# Handicap asiático
# ---------------------------------------------------------------------------

def test_ah_away_m0_25_ganha():
    # ft=1-3, away-0.25: margin = 3-1=2; adjusted = 2-0.25=1.75 → win total
    assert resolve_bet("ft_ah_away_m0_25", "yes", R_1_3) is True

def test_ah_away_m0_25_perde():
    # ft=1-0, away-0.25: margin = 0-1=-1; adjusted = -1-0.25=-1.25 → lose total
    assert resolve_bet("ft_ah_away_m0_25", "yes", R_1_0) is False

def test_ah_home_m0_25_empate_vira_meio_derrota():
    # ft=0-0, home-0.25: margin = 0-0=0 → -0.25 split: floor=0→push, ceil=-0.5→lose → -0.5 → False
    assert resolve_bet("ft_ah_home_m0_25", "yes", R_0_0) is False

def test_ah_empate_na_linha_zero_push():
    # ft=1-0, home 0 (linha inteira 0): margin = 1-0=1; ajustado = 1+0=1 → ganha
    result = GameResult(ft_home=1, ft_away=0)
    assert resolve_bet("ft_ah_home_0", "yes", result) is True


# ---------------------------------------------------------------------------
# Over/Under
# ---------------------------------------------------------------------------

def test_over_2_5_ganha():
    assert resolve_bet("over_2_5", "yes", R_2_1) is True  # total = 3

def test_over_2_5_perde():
    assert resolve_bet("over_2_5", "yes", R_1_0) is False  # total = 1

def test_under_2_5():
    assert resolve_bet("over_2_5", "no", R_1_0) is True   # total = 1 < 2.5

def test_over_1t():
    # ht=1-0 → total 1T = 1 → over_0_5 ganha
    assert resolve_bet("1h_over_0_5", "yes", R_1_0) is True
    assert resolve_bet("1h_over_1_5", "yes", R_1_0) is False

def test_over_2t():
    # ft=2-1, ht=1-0 → 2T=1-1 → total 2T=2 → over_1_5 ganha, over_2_5 perde
    assert resolve_bet("2h_over_1_5", "yes", R_2_1) is True
    assert resolve_bet("2h_over_2_5", "yes", R_2_1) is False

def test_over_2t_sem_intervalo():
    assert resolve_bet("2h_over_0_5", "yes", R_2_1_NO_HT) is None

def test_team_over():
    # ft=3-0, home gols=3 → over_2_5 ganha
    assert resolve_bet("home_over_2_5", "yes", R_3_0) is True
    assert resolve_bet("away_over_0_5", "yes", R_3_0) is False


# ---------------------------------------------------------------------------
# BTTS
# ---------------------------------------------------------------------------

def test_btts_yes_ganha():
    assert resolve_bet("btts", "yes", R_2_1) is True

def test_btts_yes_perde():
    assert resolve_bet("btts", "yes", R_1_0) is False

def test_btts_no():
    assert resolve_bet("btts", "no", R_1_0) is True


# ---------------------------------------------------------------------------
# Combos
# ---------------------------------------------------------------------------

def test_combo_btts_over():
    # ft=2-1: btts=True, total=3 > 2.5 → True
    assert resolve_bet("combo_btts_over_2_5", "yes", R_2_1) is True
    # ft=1-0: btts=False → False
    assert resolve_bet("combo_btts_over_2_5", "yes", R_1_0) is False


# ---------------------------------------------------------------------------
# Placar exato
# ---------------------------------------------------------------------------

def test_correct_score_ft():
    assert resolve_bet("ft_cs_2_1", "yes", R_2_1) is True
    assert resolve_bet("ft_cs_1_0", "yes", R_2_1) is False

def test_correct_score_2t():
    # ft=2-1, ht=1-0 → 2T=1-1
    assert resolve_bet("2h_cs_1_1", "yes", R_2_1) is True
    assert resolve_bet("2h_cs_0_0", "yes", R_2_1) is False


# ---------------------------------------------------------------------------
# Mercados não suportados
# ---------------------------------------------------------------------------

def test_mercado_desconhecido():
    assert resolve_bet("next_goal", "home", R_1_0) is None

def test_mercado_vazio():
    assert resolve_bet("", "yes", R_1_0) is None
