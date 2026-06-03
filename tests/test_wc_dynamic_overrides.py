from pipelines.wc_dynamic_overrides import apply_dynamic_overrides
from schemas.wc_kxl_dynamic import (
    FeclAmbiente,
    FedeDesfalque,
    FedeElenco,
    FeptEscalacao,
    FeptJogador,
    WcKxlMatchInput,
)


def test_rain_increases_draw():
    out = apply_dynamic_overrides(
        0.55,
        0.25,
        0.20,
        WcKxlMatchInput(fecl=FeclAmbiente(chuva_mm=5, gramado="molhado")),
    )
    assert out.prob_draw > 0.25
    assert out.notes


def test_home_absence_hurts_home():
    out = apply_dynamic_overrides(
        0.60,
        0.22,
        0.18,
        WcKxlMatchInput(
            fede=FedeElenco(
                desfalques_mandante=[
                    FedeDesfalque(jogador="Neymar", impacto=0.12),
                ],
            ),
        ),
    )
    assert out.prob_home < 0.60
    assert out.prob_away > 0.18


def test_sofascore_gap_boosts_home():
    out = apply_dynamic_overrides(
        0.50,
        0.28,
        0.22,
        WcKxlMatchInput(
            fept=FeptEscalacao(
                titulares_mandante=[
                    FeptJogador(nome="A", linha="ataque", nota_sofascore=8.2),
                    FeptJogador(nome="B", linha="ataque", nota_sofascore=8.0),
                ],
                titulares_visitante=[
                    FeptJogador(nome="C", linha="defesa", nota_sofascore=6.0),
                    FeptJogador(nome="D", linha="defesa", nota_sofascore=6.2),
                ],
            ),
        ),
    )
    assert out.prob_home > 0.50
    assert any("mandante" in n for n in out.notes)


def test_no_input_unchanged():
    out = apply_dynamic_overrides(0.4, 0.3, 0.3, None)
    assert out.prob_home == 0.4
    assert out.notes == []
