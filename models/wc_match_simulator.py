from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import structlog

from ingest.fifa.client import FifaClient
from ingest.fifa.match_ingest import ingest_match_details, ingest_window_matches
from ingest.fifa.teams import fifa_country_code
from ingest.fifa.rankings_live import get_team_points_live, load_fifa_rankings_live
from ingest.sofascore.client import SofascoreClient
from ingest.sofascore.enrich import build_enrich_payload
from ingest.sofascore.fept_ingest import build_fept_payload
from ingest.sofascore.stats_ingest import build_match_stats_payload
from schemas.wc_kxl_dynamic import FeptEscalacao, FeptTitularesEstruturados
from models.wc_predictor import WcPredictor
from pipelines.wc_stats import build_match_features

logger = structlog.get_logger()


@dataclass
class MatchSimulationResult:
    home_team: str
    away_team: str
    match_date: str | None

    # Predição do modelo principal (sem simulação fictícia)
    prediction: str
    confidence: float
    prob_home: float
    prob_draw: float
    prob_away: float

    # Dados reais da FIFA
    fifa_match: dict[str, Any] | None = None
    fifa_home_lineup: list[dict] | None = None
    fifa_away_lineup: list[dict] | None = None
    fifa_home_bench: list[dict] | None = None
    fifa_away_bench: list[dict] | None = None
    fifa_home_goals: list[dict] | None = None
    fifa_away_goals: list[dict] | None = None
    fifa_home_tactics: str | None = None
    fifa_away_tactics: str | None = None
    fifa_home_coach: str | None = None
    fifa_away_coach: str | None = None
    fifa_stadium: str | None = None
    fifa_attendance: int | None = None

    # Rankings FIFA ao vivo
    fifa_home_points: float | None = None
    fifa_away_points: float | None = None
    fifa_points_diff: float | None = None

    # Dados enriquecidos Sofascore
    enrich_features: dict[str, Any] = field(default_factory=dict)
    stats_features: dict[str, Any] = field(default_factory=dict)

    # Model breakdown
    model_breakdown: dict[str, Any] = field(default_factory=dict)

    # Escalações: fifa | sofascore
    lineup_source: str | None = None

    # Avisos honestos
    warnings: list[str] = field(default_factory=list)


def _find_fifa_match_id(
    home_team_code: str,
    away_team_code: str,
    client: FifaClient | None = None,
) -> str | None:
    """Busca o IdMatch de um confronto na janela atual da FIFA."""
    fifa = client or FifaClient()
    try:
        matches = ingest_window_matches(client=fifa)
    except Exception as exc:
        logger.warning("fifa_window_fetch_failed", error=str(exc))
        return None

    for m in matches:
        home = m.get("Home", {}).get("IdCountry", "")
        away = m.get("Away", {}).get("IdCountry", "")
        if (home.upper() == home_team_code.upper() and away.upper() == away_team_code.upper()):
            return m.get("IdMatch")
        if (home.upper() == away_team_code.upper() and away.upper() == home_team_code.upper()):
            return m.get("IdMatch")

    return None


def _parse_event_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _normalize_line_code(raw: Any) -> str | None:
    if raw is None:
        return None
    key = str(raw).strip().upper()
    mapping = {
        "G": "goleiro",
        "GK": "goleiro",
        "D": "defesa",
        "DF": "defesa",
        "M": "meio",
        "MF": "meio",
        "MID": "meio",
        "F": "ataque",
        "FW": "ataque",
        "ST": "ataque",
    }
    if key in mapping:
        return mapping[key]
    lowered = str(raw).strip().lower()
    if lowered in ("goleiro", "defesa", "meio", "ataque"):
        return lowered
    return str(raw).strip() or None


def _normalize_fept_player(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    data = raw.model_dump() if hasattr(raw, "model_dump") else raw
    if not isinstance(data, dict):
        return None
    name = data.get("nome")
    if not name:
        return None
    line = _normalize_line_code(data.get("linha") or data.get("posicao"))
    position = data.get("posicao") or line
    return {
        "name": name,
        "shirt_number": None,
        "position": position,
        "line": line,
        "is_captain": False,
        "picture_url": None,
        "sofascore_rating": data.get("nota_sofascore"),
        "yellow_cards": 0,
        "red_cards": 0,
    }


def _lineup_from_fept_structured(structured: FeptTitularesEstruturados | None) -> list[dict[str, Any]]:
    if structured is None:
        return []
    players: list[dict[str, Any]] = []
    for raw in (
        structured.goleiro,
        *structured.defensores,
        *structured.meio_campistas,
        *structured.atacantes,
        *structured.defesa_extra,
    ):
        mapped = _normalize_fept_player(raw)
        if mapped:
            mapped["is_starter"] = True
            players.append(mapped)
    return players


def _lineup_from_fept(fept: FeptEscalacao, *, for_home: bool) -> list[dict[str, Any]]:
    structured = fept.mandante_titulares_notas if for_home else fept.visitante_titulares_notas
    return _lineup_from_fept_structured(structured)


def _bench_from_fept_payload(bench: list[Any]) -> list[dict[str, Any]]:
    players: list[dict[str, Any]] = []
    for raw in bench:
        mapped = _normalize_fept_player(raw)
        if mapped:
            mapped["is_starter"] = False
            players.append(mapped)
    return players


def _tactics_from_fept(fept: FeptEscalacao, *, for_home: bool) -> str | None:
    return fept.esquema_mandante if for_home else fept.esquema_visitante


def _resolve_sofascore_context(
    home_team: str,
    away_team: str,
    *,
    sofascore_event_id: int | None,
    match_date: date | None,
    phase: str,
    client: SofascoreClient,
) -> tuple[int | None, date | None]:
    """Garante event_id ou match_date para enriquecimento Sofascore."""
    if sofascore_event_id is not None:
        if match_date is None:
            try:
                from ingest.sofascore.event_helpers import match_date_from_event

                event = client.event(sofascore_event_id)
                match_date = _parse_event_date(match_date_from_event(event))
            except Exception as exc:
                logger.warning("simulate_resolve_event_date_failed", error=str(exc))
        return sofascore_event_id, match_date

    if match_date is not None:
        return None, match_date

    if phase != "group":
        filter_year = datetime.now(timezone.utc).year
        for team in (home_team, away_team):
            try:
                from ingest.sofascore.friendlies import list_team_friendlies

                rows = list_team_friendlies(
                    team,
                    year=filter_year,
                    include_finished=True,
                    include_upcoming=True,
                    pages=1,
                    upcoming_pages=2,
                    client=client,
                )
            except Exception as exc:
                logger.warning("simulate_friendlies_lookup_failed", team=team, error=str(exc))
                continue

            for row in rows:
                if {row.home_team, row.away_team} == {home_team, away_team} and row.event_id is not None:
                    resolved_date = _parse_event_date(row.match_date) or match_date
                    return row.event_id, resolved_date

        return None, datetime.now(timezone.utc).date()

    return None, match_date


def simulate_match(
    home_team: str,
    away_team: str,
    match_date: date | None = None,
    phase: str = "group",
    is_neutral: bool = True,
    season: int | None = None,
    group_name: str | None = None,
    predictor: WcPredictor | None = None,
    sofascore_client: SofascoreClient | None = None,
    fifa_client: FifaClient | None = None,
    fifa_match_id: str | None = None,
    sofascore_event_id: int | None = None,
) -> MatchSimulationResult:
    """Analisa um confronto entre duas seleções usando dados reais da FIFA e modelos.

    Args:
        home_team: Nome canônico da seleção mandante
        away_team: Nome canônico da seleção visitante
        match_date: Data do confronto
        phase: Fase da competição
        is_neutral: Jogo em campo neutro
        season: Edição da Copa
        group_name: Nome do grupo
        predictor: Instância de WcPredictor
        sofascore_client: Cliente Sofascore para dados enriquecidos
        fifa_client: Cliente FIFA para dados oficiais

    Returns:
        MatchSimulationResult com dados reais da FIFA + predição dos modelos
    """
    warnings: list[str] = []
    fifa = fifa_client or FifaClient()
    sofascore = sofascore_client or SofascoreClient()

    # 1. Predição do modelo principal (ensemble histórico)
    from ingest.fixtures.world_cup import load_wc_fixtures

    fixtures = load_wc_fixtures()
    features = build_match_features(
        fixtures,
        home_team=home_team,
        away_team=away_team,
        phase=phase,
        is_neutral=is_neutral,
        season=season,
        group_name=group_name,
    )

    pred = predictor.predict(home_team, away_team) if predictor else None
    if pred is None:
        warnings.append("Predictor não disponível — usando apenas dados reais da FIFA")
        model_probs = {"1": 0.33, "X": 0.34, "2": 0.33}
    else:
        model_probs = {
            "1": pred.prob_home,
            "X": pred.prob_draw,
            "2": pred.prob_away,
        }

    # 2. Dados da FIFA
    fifa_match_dict: dict[str, Any] | None = None
    home_lineup: list[dict] | None = None
    away_lineup: list[dict] | None = None
    home_bench: list[dict] | None = None
    away_bench: list[dict] | None = None
    home_goals: list[dict] | None = None
    away_goals: list[dict] | None = None
    home_tactics: str | None = None
    away_tactics: str | None = None
    home_coach: str | None = None
    away_coach: str | None = None
    stadium: str | None = None
    attendance: int | None = None

    home_code = fifa_country_code(home_team)
    away_code = fifa_country_code(away_team)

    match_id = fifa_match_id
    if not match_id and home_code and away_code:
        match_id = _find_fifa_match_id(home_code, away_code, client=fifa)

    if match_id:
        try:
            details = ingest_match_details(match_id, client=fifa)
            fifa_match_dict = details.to_dict()
            home_lineup = [
                {
                    "name": p.name,
                    "shirt_number": p.shirt_number,
                    "position": p.position,
                    "is_captain": p.is_captain,
                    "picture_url": p.picture_url,
                }
                for p in details.home_team.players
            ]
            away_lineup = [
                {
                    "name": p.name,
                    "shirt_number": p.shirt_number,
                    "position": p.position,
                    "is_captain": p.is_captain,
                    "picture_url": p.picture_url,
                }
                for p in details.away_team.players
            ]
            home_goals = [
                {"minute": g.minute, "player": g.player_name, "type": g.goal_type}
                for g in details.home_team.goals
            ]
            away_goals = [
                {"minute": g.minute, "player": g.player_name, "type": g.goal_type}
                for g in details.away_team.goals
            ]
            home_tactics = details.home_team.tactics
            away_tactics = details.away_team.tactics
            home_coach = details.home_team.coach
            away_coach = details.away_team.coach
            stadium = details.stadium
            attendance = details.attendance
        except Exception as exc:
            logger.warning("fifa_match_details_failed", error=str(exc))
            warnings.append(f"Detalhes da FIFA indisponíveis: {exc}")
    pending_fifa_warning: str | None = None
    if not match_id:
        if home_code and away_code:
            if phase == "group":
                pending_fifa_warning = (
                    f"Jogo {home_team} x {away_team} não encontrado na janela atual da FIFA"
                )
            else:
                pending_fifa_warning = (
                    f"Amistoso {home_team} x {away_team} fora da janela FIFA"
                )
        else:
            pending_fifa_warning = f"Códigos FIFA não mapeados para {home_team} ou {away_team}"
    else:
        pending_fifa_warning = None

    lineup_source: str | None = "fifa" if home_lineup else None

    # 3. Rankings FIFA ao vivo
    home_points: float | None = None
    away_points: float | None = None
    points_diff: float | None = None

    try:
        rankings = load_fifa_rankings_live(client=fifa)
        home_points = get_team_points_live(home_team, rankings)
        away_points = get_team_points_live(away_team, rankings)
        if home_points is not None and away_points is not None:
            points_diff = round(home_points - away_points, 2)
    except Exception as exc:
        logger.warning("fifa_rankings_failed", error=str(exc))
        warnings.append(f"Rankings FIFA ao vivo indisponíveis: {exc}")

    # 4. Dados enriquecidos Sofascore
    enrich_features: dict[str, Any] = {}
    stats_features: dict[str, Any] = {}

    resolved_event_id, resolved_match_date = _resolve_sofascore_context(
        home_team,
        away_team,
        sofascore_event_id=sofascore_event_id,
        match_date=match_date,
        phase=phase,
        client=sofascore,
    )
    if match_date is None and resolved_match_date is not None:
        match_date = resolved_match_date

    if not home_lineup and resolved_event_id is not None:
        try:
            fept_result = build_fept_payload(
                home_team=home_team,
                away_team=away_team,
                event_id=resolved_event_id,
                match_date=resolved_match_date,
                client=sofascore,
            )
            home_lineup = _lineup_from_fept(fept_result.fept, for_home=True)
            away_lineup = _lineup_from_fept(fept_result.fept, for_home=False)
            home_bench = _bench_from_fept_payload(fept_result.home_bench)
            away_bench = _bench_from_fept_payload(fept_result.away_bench)
            home_tactics = _tactics_from_fept(fept_result.fept, for_home=True)
            away_tactics = _tactics_from_fept(fept_result.fept, for_home=False)
            if home_lineup or away_lineup:
                lineup_source = "sofascore"
                pending_fifa_warning = None
        except LookupError:
            logger.info(
                "simulate_sofascore_lineups_unpublished",
                event_id=resolved_event_id,
                home=home_team,
                away=away_team,
            )
        except Exception as exc:
            logger.warning("simulate_fept_failed", error=str(exc))
            warnings.append(f"Escalações Sofascore indisponíveis: {exc}")

    if pending_fifa_warning and not home_lineup:
        warnings.append(
            f"{pending_fifa_warning} — escalações oficiais indisponíveis"
            if phase != "group"
            else pending_fifa_warning
        )

    try:
        enrich_result = build_enrich_payload(
            home_team=home_team,
            away_team=away_team,
            event_id=resolved_event_id,
            match_date=resolved_match_date,
            client=sofascore,
        )
        enrich_features = enrich_result.features
    except Exception as exc:
        logger.warning("simulate_enrich_failed", error=str(exc))
        warnings.append(f"Dados enriquecidos indisponíveis: {exc}")

    try:
        stats_result = build_match_stats_payload(
            home_team=home_team,
            away_team=away_team,
            event_id=resolved_event_id,
            match_date=resolved_match_date,
            client=sofascore,
        )
        stats_features = stats_result.stats
    except Exception as exc:
        msg = str(exc)
        if "404" in msg and "statistics" in msg:
            logger.info(
                "simulate_stats_not_started",
                event_id=resolved_event_id,
                home=home_team,
                away=away_team,
            )
        else:
            logger.warning("simulate_stats_failed", error=str(exc))
            warnings.append(f"Estatísticas de jogo indisponíveis: {exc}")

    probs = model_probs
    prediction = max(probs, key=probs.get)
    confidence = probs[prediction]

    return MatchSimulationResult(
        home_team=home_team,
        away_team=away_team,
        match_date=match_date.isoformat() if match_date else None,
        prediction=prediction,
        confidence=round(confidence, 4),
        prob_home=round(probs["1"], 4),
        prob_draw=round(probs["X"], 4),
        prob_away=round(probs["2"], 4),
        fifa_match=fifa_match_dict,
        fifa_home_lineup=home_lineup,
        fifa_away_lineup=away_lineup,
        fifa_home_bench=home_bench,
        fifa_away_bench=away_bench,
        fifa_home_goals=home_goals,
        fifa_away_goals=away_goals,
        fifa_home_tactics=home_tactics,
        fifa_away_tactics=away_tactics,
        fifa_home_coach=home_coach,
        fifa_away_coach=away_coach,
        fifa_stadium=stadium,
        fifa_attendance=attendance,
        fifa_home_points=home_points,
        fifa_away_points=away_points,
        fifa_points_diff=points_diff,
        lineup_source=lineup_source,
        enrich_features=enrich_features,
        stats_features=stats_features,
        model_breakdown={
            "ensemble_model": model_probs,
            "lambda_home": round(features.home_goals_rate, 3),
            "lambda_away": round(features.away_goals_rate, 3),
        },
        warnings=warnings,
    )
