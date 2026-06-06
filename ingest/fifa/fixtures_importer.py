from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from config import settings
from schemas.models import MatchResult
from schemas.national_teams import normalize_national_team

logger = structlog.get_logger()


def _extract_name(names: list[dict]) -> str:
    """Extrai nome em português ou inglês da lista de nomes localizados."""
    for n in names:
        if n.get("Locale", "").lower().startswith("pt"):
            return n.get("Description", "")
    for n in names:
        if n.get("Locale", "").lower().startswith("en"):
            return n.get("Description", "")
    return names[0].get("Description", "") if names else ""


def _guess_season_year(season_name: str, match_date: str) -> int:
    """Extrai ano da temporada a partir do nome ou da data do jogo."""
    # Tenta 4 dígitos primeiro
    years = re.findall(r"20\d{2}", season_name)
    if years:
        return int(years[0])

    # Tenta 2 dígitos (ex: "Copa do Mundo 26")
    two_digit = re.findall(r"[^0-9]([0-9]{2})[^0-9]", " " + season_name + " ")
    for td in two_digit:
        val = int(td)
        if val >= 20:
            return 2000 + val
        elif val < 50:
            return 2000 + val  # assume 2000+

    # Fallback para ano da data do jogo
    try:
        return int(match_date[:4])
    except Exception:
        return datetime.now(timezone.utc).year


def _build_label(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "1"
    elif home_score < away_score:
        return "2"
    return "X"


def _build_match_id(
    season: int,
    competition: str,
    home_team: str,
    away_team: str,
    match_date: str,
) -> str:
    base = f"fifa|{season}|{competition}|{home_team}|{away_team}|{match_date}"
    return hashlib.sha256(base.encode()).hexdigest()[:16]


def _normalize_for_search(text: str) -> str:
    """Remove acentos e converte para minúsculas."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _infer_phase(season_name: str, stage_name: str) -> str:
    """Infere a fase do jogo para o schema MatchResult."""
    s = _normalize_for_search(season_name + " " + stage_name)
    if "friendly" in s or "amistoso" in s or "series" in s:
        return "friendly"
    # Eliminatórias devem ser detectadas ANTES de "group" porque
    # fases como "Round Three" ou "Group E" aparecem em qualificatórias
    if "eliminatoria" in s or "qualif" in s or "prel." in s:
        return "qualifier"
    if "nations league" in s:
        return "nations_league"
    if "play-off" in s or "playoff" in s:
        return "playoff"
    if "group" in s or "grupo" in s or "fase" in s:
        return "group"
    if "round" in s or "oitava" in s or "quarter" in s or "semi" in s or "final" in s:
        return "knockout"
    return "other"


def _infer_is_neutral(phase: str, season_name: str) -> bool:
    """Determina se o jogo é em campo neutro.

    Amistosos e torneios finais (Copa do Mundo, Copa Árabe, etc.)
    são neutros. Eliminatórias e Nations League geralmente têm
    mandante/real.
    """
    s = season_name.lower()
    # Amistosos e séries geralmente são neutros (exceto quando explicitamente não)
    if phase == "friendly":
        return True
    # Eliminatórias e Nations League têm mandante
    if phase in ("qualifier", "nations_league"):
        return False
    # Playoffs podem ser neutros ou não; assume neutro por padrão
    if phase == "playoff":
        return True
    # Copas continentais e finais FIFA são neutros
    if "cup" in s or "copa" in s or "world cup" in s:
        return True
    return True


def _parse_fifa_window_match(raw: dict[str, Any]) -> MatchResult | None:
    """Converte um jogo raw da FIFA window em MatchResult."""
    period = raw.get("Period", 0)
    match_status = raw.get("MatchStatus", 0)

    # Só importa jogos finalizados
    if period != 10 and match_status != 10:
        return None

    # Dados dos times (FIFA usa HomeTeam/AwayTeam ou Home/Away)
    home_raw = raw.get("HomeTeam") or raw.get("Home") or {}
    away_raw = raw.get("AwayTeam") or raw.get("Away") or {}

    home_name = _extract_name(home_raw.get("TeamName", []))
    away_name = _extract_name(away_raw.get("TeamName", []))

    if not home_name or not away_name:
        return None

    home_team = normalize_national_team(home_name)
    away_team = normalize_national_team(away_name)

    season_name = _extract_name(raw.get("SeasonName", []))
    stage_name = _extract_name(raw.get("StageName", []))
    match_date = raw.get("Date", "")

    season = _guess_season_year(season_name, match_date)
    competition = season_name or "FIFA"

    home_score = int(raw.get("HomeTeamScore", 0) or 0)
    away_score = int(raw.get("AwayTeamScore", 0) or 0)

    # Não importa jogos sem resultado (0-0 pode ser real, mas deixa passar)
    # O period == 10 já garante que terminou

    phase = _infer_phase(season_name, stage_name)
    match_id = _build_match_id(season, competition, home_team, away_team, match_date)

    return MatchResult(
        match_id=match_id,
        season=season,
        competition=competition,
        round_number=0,
        match_date=match_date,
        home_team=home_team,
        away_team=away_team,
        home_team_raw=home_name,
        away_team_raw=away_name,
        home_score=home_score,
        away_score=away_score,
        label=_build_label(home_score, away_score),
        imported_at=datetime.now(timezone.utc),
        phase=phase,
        group_name=_extract_name(raw.get("GroupName", [])) or None,
        is_neutral=_infer_is_neutral(phase, season_name),
    )


def import_fifa_window_matches(
    window_matches: list[dict[str, Any]] | None = None,
    *,
    output_path: Path | None = None,
    skip_existing: bool = True,
) -> pd.DataFrame:
    """Importa jogos da janela FIFA para Parquet no lake.

    Args:
        window_matches: lista raw de jogos da FIFA window. Se None, lê do cache local.
        output_path: caminho do Parquet de saída. Padrão: fixtures_path/fifa_matches.parquet
        skip_existing: se True, não sobrescreve arquivo existente.

    Returns:
        DataFrame com os jogos importados.
    """
    out_path = output_path or (settings.fixtures_path / "fifa_matches.parquet")

    if skip_existing and out_path.exists():
        logger.info("fifa_fixtures_import_skipped_existing", path=str(out_path))
        return pd.read_parquet(out_path)

    if window_matches is None:
        from ingest.fifa.match_ingest import load_fifa_window_matches

        window_matches = load_fifa_window_matches()

    results: list[MatchResult] = []
    skipped = 0
    for raw in window_matches:
        parsed = _parse_fifa_window_match(raw)
        if parsed is None:
            skipped += 1
            continue
        results.append(parsed)

    if not results:
        logger.warning("fifa_fixtures_import_empty", total=len(window_matches), skipped=skipped)
        return pd.DataFrame()

    records = [r.model_dump(mode="json") for r in results]
    df = pd.DataFrame(records)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    logger.info(
        "fifa_fixtures_import_done",
        total=len(window_matches),
        imported=len(results),
        skipped=skipped,
        path=str(out_path),
    )
    return df


def load_fifa_fixtures() -> pd.DataFrame:
    """Carrega jogos FIFA importados do Parquet local."""
    path = settings.fixtures_path / "fifa_matches.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)
