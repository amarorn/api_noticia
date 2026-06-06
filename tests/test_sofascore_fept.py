from __future__ import annotations

from ingest.sofascore.fept_mapper import (
    map_lineups_to_fept,
    pick_player_rating_from_statistics,
)
from ingest.sofascore.fept_ingest import build_fept_payload
from ingest.sofascore.kxl_sofascore_ingest import KxlSofascoreIngestResult
from ingest.sofascore.kxl_merge import merge_sofascore_fept
from ingest.sofascore.teams import sides_for_event
from schemas.wc_kxl_dynamic import (
    FedeElenco,
    FeptEscalacao,
    FeptTitularesEstruturados,
    WcKxlMatchInput,
)


class FakeSofascoreClient:
    def __init__(self, event: dict, lineups: dict, player_stats: dict[int, list]):
        self._event = event
        self._lineups = lineups
        self._player_stats = player_stats

    def event(self, event_id: int) -> dict:
        return self._event

    def event_lineups(self, event_id: int) -> dict:
        return self._lineups

    def player_statistics(self, player_id: int) -> list[dict]:
        return self._player_stats.get(player_id, [])


def test_pick_player_rating_prefers_world_cup():
    seasons = [
        {
            "uniqueTournament": {"slug": "laliga"},
            "statistics": {"rating": 7.9, "countRating": 20},
        },
        {
            "uniqueTournament": {"slug": "world-championship"},
            "statistics": {"rating": 7.2, "countRating": 6},
        },
    ]
    assert pick_player_rating_from_statistics(seasons) == 7.2


def test_map_lineups_to_fept_structured():
    lineups = {
        "home": {
            "formation": "4-3-3",
            "players": [
                {
                    "substitute": False,
                    "position": "G",
                    "player": {"id": 1, "name": "GK"},
                    "statistics": {"rating": 7.0},
                },
                {
                    "substitute": False,
                    "position": "D",
                    "player": {"id": 2, "name": "CB"},
                    "statistics": {"rating": 6.8},
                },
                {
                    "substitute": False,
                    "position": "M",
                    "player": {"id": 3, "name": "CM"},
                    "statistics": {"rating": 7.1},
                },
                {
                    "substitute": False,
                    "position": "F",
                    "player": {"id": 4, "name": "ST"},
                    "statistics": {"rating": 7.5},
                },
                {
                    "substitute": True,
                    "position": "F",
                    "player": {"id": 5, "name": "Bench"},
                    "statistics": {"rating": 6.0},
                },
            ],
        },
        "away": {
            "formation": "4-4-2",
            "players": [
                {
                    "substitute": False,
                    "position": "G",
                    "player": {"id": 6, "name": "GK2"},
                    "statistics": {"rating": 6.9},
                },
            ],
        },
    }

    fept = map_lineups_to_fept(
        lineups,
        home_is_event_home=True,
        fetch_statistics=lambda _pid: [],
        rating_cache={},
    )
    assert fept.esquema_mandante == "4-3-3"
    assert fept.esquema_visitante == "4-4-2"
    assert fept.mandante_titulares_notas is not None
    assert fept.mandante_titulares_notas.goleiro["nome"] == "GK"
    assert len(fept.mandante_titulares_notas.atacantes) == 1


def test_build_fept_payload_with_event_id():
    team_map = {
        "Brasil": {"sofascore_id": 4748},
        "Argentina": {"sofascore_id": 4819},
    }
    event = {
        "id": 99,
        "homeTeam": {"id": 4748, "name": "Brazil"},
        "awayTeam": {"id": 4819, "name": "Argentina"},
    }
    lineups = {
        "home": {
            "formation": "4-2-3-1",
            "players": [
                {
                    "substitute": False,
                    "position": "G",
                    "player": {"id": 10, "name": "Alisson"},
                    "statistics": {"rating": 6.4},
                },
            ],
        },
        "away": {
            "formation": "4-4-2",
            "players": [
                {
                    "substitute": False,
                    "position": "G",
                    "player": {"id": 11, "name": "Martinez"},
                    "statistics": {"rating": 7.0},
                },
            ],
        },
    }
    client = FakeSofascoreClient(event, lineups, {})
    result = build_fept_payload(
        event_id=99,
        client=client,
        team_map=team_map,
    )
    assert result.home_team == "Brasil"
    assert result.away_team == "Argentina"
    assert result.fept.esquema_mandante == "4-2-3-1"
    assert result.ratings_found == 2


def test_merge_sofascore_fept_creates_kxl_match(monkeypatch):
    fept = FeptEscalacao(
        esquema_mandante="4-2-3-1",
        mandante_titulares_notas=FeptTitularesEstruturados(
            goleiro={"nome": "Alisson", "nota_sofascore": 7.0},
        ),
    )

    def fake_build(**_kwargs):
        return KxlSofascoreIngestResult(
            home_team="Brasil",
            away_team="Argentina",
            event_id=99,
            match_date=None,
            fept=fept,
            fede=FedeElenco(),
            feju=None,
            ratings_found=1,
            ratings_missing=0,
            absences_home=0,
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
    assert meta is not None
    assert meta["auto_merged"] is True


def test_merge_sofascore_fept_preserves_manual_fept(monkeypatch):
    from schemas.wc_kxl_dynamic import FejuArbitro, FedeDesfalque

    manual = WcKxlMatchInput(
        fept=FeptEscalacao(esquema_mandante="3-5-2"),
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
    assert kxl.fept.esquema_mandante == "3-5-2"
    assert kxl.fede is not None
    assert kxl.feju is not None
    assert meta["auto_merged"] is False


def test_sides_for_event_swapped():
    event = {
        "id": 1,
        "homeTeam": {"id": 4819, "name": "Argentina"},
        "awayTeam": {"id": 4748, "name": "Brazil"},
    }
    team_map = {
        "Brasil": {"sofascore_id": 4748},
        "Argentina": {"sofascore_id": 4819},
    }
    home_is_event_home, home_id, away_id = sides_for_event(
        event,
        home_team="Brasil",
        away_team="Argentina",
        team_map=team_map,
    )
    assert home_is_event_home is False
    assert home_id == 4748
    assert away_id == 4819
