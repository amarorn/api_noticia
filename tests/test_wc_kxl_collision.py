from pipelines.wc_kxl_collision import collision_predict, collision_to_breakdown
from schemas.wc_kxl_dynamic import (
    FeclAmbiente,
    FedeDesfalque,
    FedeElenco,
    FejuArbitro,
    FeptEscalacao,
    FeptTitularesEstruturados,
    WcKxlMatchInput,
)


def test_collision_brasil_marrocos():
    r = collision_predict("Brasil", "Marrocos")
    assert r is not None
    assert r.prob_home > r.prob_away
    assert r.home.v_eff > 0
    assert len(r.home.sectors) == 3


def test_punitivist_boosts_vcar():
    base = collision_predict("Brasil", "Marrocos")
    pun = collision_predict(
        "Brasil",
        "Marrocos",
        WcKxlMatchInput(feju=FejuArbitro(perfil="punitivista")),
    )
    assert base and pun
    assert pun.home.vcar_raw >= base.home.vcar_raw


def test_rain_boosts_vesc_modulator():
    dry = collision_predict("Brasil", "Marrocos")
    wet = collision_predict(
        "Brasil",
        "Marrocos",
        WcKxlMatchInput(fecl=FeclAmbiente(chuva_mm=5, gramado="molhado")),
    )
    assert dry and wet
    assert wet.away.modulators.get("vesc", 1.0) >= dry.away.modulators.get("vesc", 1.0)


def test_breakdown_has_vcar():
    r = collision_predict("Brasil", "Marrocos")
    assert r
    b = collision_to_breakdown(r)
    assert "mandante" in b
    assert b["mandante"]["vcar_raw"] > 0


def test_lethality_matrix_four_methods():
    r = collision_predict("Brasil", "Marrocos")
    assert r
    assert len(r.home.lethality.cells) == 4
    assert r.home.lethality.dominant
    assert r.lethality_note


def test_holanda_inside_weakness_boosts_pressure():
    r = collision_predict("Senegal", "Holanda")
    assert r
    away_inside = next(c for c in r.away.lethality.cells if c.method == "dentro da área")
    assert away_inside.gk_weak_pct >= 60


def test_defensive_scheme_boosts_vesc():
    open_ = collision_predict(
        "Brasil",
        "Marrocos",
        WcKxlMatchInput(fept=FeptEscalacao(esquema_mandante="4-3-3")),
    )
    closed = collision_predict(
        "Brasil",
        "Marrocos",
        WcKxlMatchInput(fept=FeptEscalacao(esquema_visitante="5-4-1")),
    )
    assert open_ and closed
    assert closed.away.modulators.get("vesc", 1.0) >= open_.away.modulators.get("vesc", 1.0)


def test_structured_fept_changes_energy():
    base = collision_predict("Brasil", "Marrocos")
    rich = collision_predict(
        "Brasil",
        "Marrocos",
        WcKxlMatchInput(
            fept=FeptEscalacao(
                mandante_titulares_notas=FeptTitularesEstruturados(
                    goleiro={"nome": "Alisson", "nota_sofascore": 7.2},
                    defensores=[{"nome": "Marquinhos", "nota_sofascore": 7.4}],
                    meio_campistas=[{"nome": "Paquetá", "nota_sofascore": 7.6}],
                    atacantes=[
                        {"nome": "Vini Jr", "nota_sofascore": 8.2},
                        {"nome": "Richarlison", "nota_sofascore": 7.0},
                    ],
                ),
            ),
        ),
    )
    assert base and rich
    assert rich.home.energia != base.home.energia


def test_fede_impacto_nota_reduces_vcar():
    base = collision_predict("Brasil", "Marrocos")
    hurt = collision_predict(
        "Brasil",
        "Marrocos",
        WcKxlMatchInput(
            fede=FedeElenco(
                desfalques_mandante=[
                    FedeDesfalque(jogador="Neymar", impacto_nota_elenco=-1.2),
                ],
            ),
        ),
    )
    assert base and hurt
    assert hurt.home.vcar_raw < base.home.vcar_raw
