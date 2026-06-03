from pipelines.wc_kxl_fept import (
    fecl_is_synthetic,
    fecl_is_wet,
    flatten_titulares_estruturados,
    scheme_modifiers,
    weighted_squad_energy,
)
from schemas.wc_kxl_dynamic import (
    FeclAmbiente,
    FeptEscalacao,
    FeptJogador,
    FeptTitularesEstruturados,
)


def test_fecl_wet_by_previsao_chuva():
    assert fecl_is_wet(FeclAmbiente(previsao_chuva_pct=50))


def test_fecl_synthetic():
    assert fecl_is_synthetic(FeclAmbiente(estado_gramado="Sintético"))


def test_scheme_offensive_boosts_vcar():
    vcar, vesc, note = scheme_modifiers("4-3-3")
    assert vcar > 1.0
    assert note


def test_flatten_structured_titulares():
    block = FeptTitularesEstruturados(
        goleiro={"nome": "GK", "nota_sofascore": 7.0},
        defensores=[{"nome": "CB", "nota_sofascore": 6.8}],
        meio_campistas=[FeptJogador(nome="CM", nota_sofascore=7.1, linha="meio")],
        atacantes=[{"nome": "ST", "nota_sofascore": 7.5}],
    )
    players = flatten_titulares_estruturados(block)
    assert len(players) == 4
    assert players[0].linha == "goleiro"
    assert players[-1].linha == "ataque"


def test_weighted_squad_energy():
    players = [
        FeptJogador(nome="A", linha="ataque", nota_sofascore=8.0),
        FeptJogador(nome="D", linha="defesa", nota_sofascore=7.0),
    ]
    e = weighted_squad_energy(players)
    assert e is not None
    assert 0.5 <= e <= 1.35


def test_fept_players_prefers_structured():
    from pipelines.wc_kxl_fept import fept_players_for_side

    fept = FeptEscalacao(
        mandante_titulares_notas=FeptTitularesEstruturados(
            atacantes=[{"nome": "Vini", "nota_sofascore": 8.0}],
        ),
        titulares_mandante=[FeptJogador(nome="Legado", linha="ataque", nota_sofascore=5.0)],
    )
    home = fept_players_for_side(fept, is_home=True)
    assert home[0].nome == "Vini"
