from __future__ import annotations

from ingest.sofascore.fede_mapper import map_lineups_to_fede
from ingest.sofascore.feju_mapper import map_referee_to_feju
from ingest.sofascore.kxl_merge import merge_sofascore_fept
from ingest.sofascore.kxl_sofascore_ingest import KxlSofascoreIngestResult
from schemas.wc_kxl_dynamic import (
    FejuArbitro,
    FedeDesfalque,
    FedeElenco,
    FeptEscalacao,
    WcKxlMatchInput,
)


def test_map_referee_punitivista():
    feju = map_referee_to_feju(
        {
            "name": "Piero Maza",
            "games": 212,
            "yellowCards": 1200,
            "redCards": 49,
            "yellowRedCards": 40,
        }
    )
    assert feju is not None
    assert feju.nome_arbitro == "Piero Maza"
    assert feju.perfil == "punitivista"
    assert feju.cartoes_media is not None
    assert feju.cartoes_media > 5.0


def test_map_referee_pacificador():
    feju = map_referee_to_feju(
        {
            "name": "Calm Ref",
            "games": 100,
            "yellowCards": 250,
            "redCards": 5,
            "yellowRedCards": 2,
        }
    )
    assert feju is not None
    assert feju.perfil == "pacificador"


def test_map_lineups_to_fede_missing_players():
    lineups = {
        "home": {
            "missingPlayers": [
                {
                    "player": {
                        "id": 1,
                        "name": "Casemiro",
                        "position": "M",
                        "shortName": "Casemiro",
                    },
                    "type": "missing",
                }
            ]
        },
        "away": {"missingPlayers": []},
    }
    fede = map_lineups_to_fede(
        lineups,
        home_is_event_home=True,
        fetch_statistics=lambda _pid: [],
        rating_cache={},
    )
    assert len(fede.desfalques_mandante) == 1
    assert fede.desfalques_mandante[0].jogador == "Casemiro"
    assert fede.desfalques_mandante[0].posicao == "Meio"
    assert len(fede.desfalques_visitante) == 0


def test_merge_adds_fede_feju_when_absent(monkeypatch):
    fept = FeptEscalacao(esquema_mandante="4-2-3-1")
    fede = FedeElenco(
        desfalques_mandante=[
            FedeDesfalque(jogador="Casemiro", posicao="Meio", impacto=0.05),
        ],
    )
    feju = FejuArbitro(nome_arbitro="Piero Maza", perfil="punitivista", cartoes_media=6.1)

    def fake_build(**_kwargs):
        return KxlSofascoreIngestResult(
            home_team="Brasil",
            away_team="Argentina",
            event_id=99,
            match_date=None,
            fept=fept,
            fede=fede,
            feju=feju,
            ratings_found=1,
            ratings_missing=0,
            absences_home=1,
            absences_away=0,
        )

    monkeypatch.setattr(
        "ingest.sofascore.kxl_merge.build_kxl_sofascore_payload",
        fake_build,
    )
    kxl, meta = merge_sofascore_fept(
        kxl_match=None,
        sofascore_event_id=99,
        home_team="Brasil",
        away_team="Argentina",
    )
    assert kxl is not None
    assert kxl.fept is not None
    assert kxl.fede is not None
    assert len(kxl.fede.desfalques_mandante) == 1
    assert kxl.feju is not None
    assert meta["referee_profile"] == "punitivista"
    assert meta["absences_home"] == 1


def test_merge_preserves_manual_fede_feju(monkeypatch):
    manual = WcKxlMatchInput(
        fede=FedeElenco(
            desfalques_mandante=[FedeDesfalque(jogador="Manual", posicao="Ataque")],
        ),
        feju=FejuArbitro(nome_arbitro="Manual Ref", perfil="equilibrado"),
    )

    def fake_build(**_kwargs):
        return KxlSofascoreIngestResult(
            home_team="Brasil",
            away_team="Argentina",
            event_id=99,
            match_date=None,
            fept=FeptEscalacao(esquema_mandante="4-3-3"),
            fede=FedeElenco(
                desfalques_mandante=[FedeDesfalque(jogador="Casemiro", posicao="Meio")],
            ),
            feju=FejuArbitro(nome_arbitro="Piero Maza", perfil="punitivista"),
            ratings_found=1,
            ratings_missing=0,
            absences_home=1,
            absences_away=0,
        )

    monkeypatch.setattr(
        "ingest.sofascore.kxl_merge.build_kxl_sofascore_payload",
        fake_build,
    )
    kxl, meta = merge_sofascore_fept(
        kxl_match=manual,
        sofascore_event_id=99,
        home_team="Brasil",
        away_team="Argentina",
    )
    assert kxl.fede.desfalques_mandante[0].jogador == "Manual"
    assert kxl.feju.nome_arbitro == "Manual Ref"
    assert meta["auto_merged"] is False
