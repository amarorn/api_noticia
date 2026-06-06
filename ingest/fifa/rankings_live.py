from __future__ import annotations

import functools
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from config import settings
from ingest.fifa.client import FifaClient

logger = structlog.get_logger()


@dataclass(frozen=True)
class FifaRankingEntry:
    team_id: str
    country_code: str
    team_name: str
    points: float
    points_before: float
    rank: int | None = None


def extract_rankings_from_window(
    matches: list[dict[str, Any]],
) -> dict[str, FifaRankingEntry]:
    """Extrai pontos FIFA atualizados da lista de jogos da janela.

    Cada jogo tem TeamAPoints (atual) e TeamAPointsBefore (antes do jogo).
    """
    rankings: dict[str, FifaRankingEntry] = {}

    for m in matches:
        for side, letter in (("Home", "A"), ("Away", "B")):
            team = m.get(side, {})
            team_id = team.get("IdTeam", "")
            country = team.get("IdCountry", "")
            name = team.get("TeamName", [{}])[0].get("Description", "") if team.get("TeamName") else ""

            # Pontos atuais (após o jogo)
            points_key = f"Team{letter}Points"  # TeamAPoints ou TeamBPoints
            points_before_key = f"Team{letter}PointsBefore"

            points = m.get(points_key)
            points_before = m.get(points_before_key)

            if team_id and points is not None:
                # Se já temos entrada, mantemos a mais recente (último jogo processado)
                rankings[team_id] = FifaRankingEntry(
                    team_id=team_id,
                    country_code=country,
                    team_name=name,
                    points=float(points),
                    points_before=float(points_before) if points_before is not None else float(points),
                )

    return rankings


def _load_rankings_cache_any_age(cache_path: Path) -> dict[str, FifaRankingEntry]:
    if not cache_path.is_file():
        return {}
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        return {tid: FifaRankingEntry(**entry) for tid, entry in data.items()}
    except Exception as exc:
        logger.warning("fifa_rankings_cache_error", error=str(exc))
        return {}


@functools.lru_cache(maxsize=1)
def _load_fifa_rankings_live_cached(
    force_refresh: bool = False,
) -> dict[str, FifaRankingEntry]:
    """Versão cacheada em memória (1 entry) de load_fifa_rankings_live.

    Evita reler o JSON do disco a cada chamada durante treinamento.
    """
    cache_path = settings.fifa_rankings_cache_path

    if cache_path.is_file():
        try:
            mtime = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - mtime).total_seconds() / 3600
            if age_hours < 24:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                logger.info("fifa_rankings_loaded_from_cache", age_hours=round(age_hours, 1))
                return {
                    tid: FifaRankingEntry(**entry)
                    for tid, entry in data.items()
                }
        except Exception as exc:
            logger.warning("fifa_rankings_cache_error", error=str(exc))

    # Busca da API
    fifa = FifaClient()
    from ingest.fifa.match_ingest import load_fifa_window_matches

    matches = load_fifa_window_matches(client=fifa)
    if not matches:
        logger.error("fifa_window_matches_unavailable")
        stale = _load_rankings_cache_any_age(cache_path)
        if stale:
            logger.info("fifa_rankings_using_stale_cache", teams=len(stale))
        return stale

    rankings = extract_rankings_from_window(matches)

    # Salva cache
    try:
        cache_data = {
            tid: {
                "team_id": entry.team_id,
                "country_code": entry.country_code,
                "team_name": entry.team_name,
                "points": entry.points,
                "points_before": entry.points_before,
            }
            for tid, entry in rankings.items()
        }
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("fifa_rankings_cached", teams=len(rankings))
    except Exception as exc:
        logger.warning("fifa_rankings_cache_save_failed", error=str(exc))

    return rankings


def load_fifa_rankings_live(
    *,
    force_refresh: bool = False,
    client: FifaClient | None = None,
) -> dict[str, FifaRankingEntry]:
    """Carrega rankings FIFA ao vivo.

    Se houver cache recente (< 24h), usa do disco. Senão, busca da API.
    Resultado é cacheado em memória (LRU de 1 entry) para evitar reler
    o JSON do disco a cada chamada durante loops de treinamento.
    """
    # O parâmetro client é ignorado na versão cacheada em memória;
    # em caso de force_refresh, invalidamos o cache e refazemos.
    if force_refresh:
        _load_fifa_rankings_live_cached.cache_clear()
    return _load_fifa_rankings_live_cached(force_refresh=force_refresh)


def get_team_points_live(
    team_name_or_code: str,
    rankings: dict[str, FifaRankingEntry] | None = None,
) -> float | None:
    """Busca pontos FIFA ao vivo de uma seleção pelo nome ou código do país.

    Args:
        team_name_or_code: Nome (ex: "Brasil") ou código ISO (ex: "BRA")
        rankings: Dict de rankings (se None, carrega do cache/API)

    Returns:
        Pontos FIFA ou None se não encontrado
    """
    if rankings is None:
        rankings = load_fifa_rankings_live()

    # Tenta buscar por código primeiro
    code_upper = team_name_or_code.upper()
    for entry in rankings.values():
        if entry.country_code.upper() == code_upper:
            return entry.points

    # Tenta buscar por nome
    from schemas.national_teams import normalize_national_team
    canonical = normalize_national_team(team_name_or_code).lower()

    name_mapping = {
        "brasil": "Brazil",
        "argentina": "Argentina",
        "franca": "France",
        "espanha": "Spain",
        "portugal": "Portugal",
        "alemanha": "Germany",
        "italia": "Italy",
        "inglaterra": "England",
        "belgica": "Belgium",
        "holanda": "Netherlands",
        "croacia": "Croatia",
        "uruguai": "Uruguay",
        "colômbia": "Colombia",
        "marrocos": "Morocco",
        "senegal": "Senegal",
        "japao": "Japan",
        "coreia do sul": "Korea Republic",
        "méxico": "Mexico",
        "estados unidos": "USA",
        "canadá": "Canada",
        "austrália": "Australia",
        "costa do marfim": "Côte d'Ivoire",
        "equador": "Ecuador",
        "peru": "Peru",
        "chile": "Chile",
        "paraguai": "Paraguay",
        "bolívia": "Bolivia",
        "venezuela": "Venezuela",
        "panamá": "Panama",
        "honduras": "Honduras",
        "guatemala": "Guatemala",
        "jamaica": "Jamaica",
        "costa rica": "Costa Rica",
        "el salvador": "El Salvador",
    }

    fifa_name = name_mapping.get(canonical, canonical)

    for entry in rankings.values():
        if entry.team_name.lower() == fifa_name.lower():
            return entry.points

    return None
