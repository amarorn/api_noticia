from __future__ import annotations

from typing import Any


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _form_sequence_to_metrics(form: list[str] | None) -> dict[str, int | float]:
    """Converte sequência W/D/L em métricas numéricas."""
    if not form:
        return {
            "form_points_last5": 0,
            "form_wins_last5": 0,
            "form_draws_last5": 0,
            "form_losses_last5": 0,
            "form_win_pct_last5": 0.0,
            "form_unbeaten_last5": 0,
        }

    # Sofascore retorna form como lista de strings ex: ["W", "W", "D", "L", "W"]
    sequence = [str(x).strip().upper() for x in form if x]
    if not sequence:
        sequence = form

    wins = sum(1 for r in sequence if r == "W")
    draws = sum(1 for r in sequence if r == "D")
    losses = sum(1 for r in sequence if r == "L")
    total = len(sequence)

    # Pontos (3 por vitória, 1 por empate)
    points = wins * 3 + draws * 1

    return {
        "form_points_last5": points,
        "form_wins_last5": wins,
        "form_draws_last5": draws,
        "form_losses_last5": losses,
        "form_win_pct_last5": round(wins / total, 3) if total > 0 else 0.0,
        "form_unbeaten_last5": 1 if losses == 0 else 0,
    }


def map_pregame_form(payload: dict[str, Any]) -> dict[str, Any]:
    """Converte resposta do endpoint /pregame-form em features numéricas."""
    out: dict[str, Any] = {}

    for side in ("home", "away"):
        team_data = payload.get(f"{side}Team") or {}
        prefix = f"{side}_"

        out[f"{prefix}position_competition"] = _safe_int(team_data.get("position"))
        out[f"{prefix}points_competition"] = _safe_int(team_data.get("value"))
        out[f"{prefix}avgrating_last5"] = _safe_float(team_data.get("avgRating"))

        form = team_data.get("form")
        if isinstance(form, list):
            metrics = _form_sequence_to_metrics(form)
            for key, value in metrics.items():
                out[f"{prefix}{key}"] = value

    # Diferenciais (home - away)
    out["position_diff"] = (
        out.get("home_position_competition", 0)
        - out.get("away_position_competition", 0)
    )
    out["points_diff"] = (
        out.get("home_points_competition", 0)
        - out.get("away_points_competition", 0)
    )
    out["avgrating_diff"] = round(
        out.get("home_avgrating_last5", 0.0)
        - out.get("away_avgrating_last5", 0.0),
        3,
    )
    out["form_points_diff"] = (
        out.get("home_form_points_last5", 0)
        - out.get("away_form_points_last5", 0)
    )

    return out


def map_team_streaks(payload: dict[str, Any]) -> dict[str, Any]:
    """Converte resposta do endpoint /team-streaks em features numéricas."""
    out: dict[str, Any] = {}

    # Inicializa com zeros
    for side in ("home", "away"):
        prefix = f"{side}_"
        out[f"{prefix}streak_unbeaten"] = 0
        out[f"{prefix}streak_wins"] = 0
        out[f"{prefix}streak_draws"] = 0
        out[f"{prefix}streak_losses"] = 0
        out[f"{prefix}streak_goals_scored"] = 0
        out[f"{prefix}streak_goals_conceded"] = 0
        out[f"{prefix}streak_clean_sheets"] = 0
        out[f"{prefix}streak_both_teams_scored"] = 0
        out[f"{prefix}streak_over_25"] = 0
        out[f"{prefix}streak_under_25"] = 0
        out[f"{prefix}streak_continued"] = 0

    for streak in payload.get("general") or []:
        team = str(streak.get("team") or "").lower()
        if team not in ("home", "away"):
            continue

        name = str(streak.get("name") or "").lower().replace(" ", "_")
        value = _safe_int(streak.get("value"))
        continued = 1 if streak.get("continued") else 0

        prefix = f"{team}_"

        # Mapeamento de nomes de streaks comuns do Sofascore
        streak_map = {
            "unbeaten": "streak_unbeaten",
            "wins": "streak_wins",
            "winning": "streak_wins",
            "draws": "streak_draws",
            "drawing": "streak_draws",
            "losses": "streak_losses",
            "losing": "streak_losses",
            "goals_scored": "streak_goals_scored",
            "scoring": "streak_goals_scored",
            "goals_conceded": "streak_goals_conceded",
            "conceding": "streak_goals_conceded",
            "clean_sheets": "streak_clean_sheets",
            "both_teams_scored": "streak_both_teams_scored",
            "over_2.5": "streak_over_25",
            "over_25": "streak_over_25",
            "under_2.5": "streak_under_25",
            "under_25": "streak_under_25",
        }

        for token, col in streak_map.items():
            if token in name:
                out[f"{prefix}{col}"] = value
                out[f"{prefix}streak_continued"] = continued
                break

    # Diferenciais
    out["streak_unbeaten_diff"] = (
        out.get("home_streak_unbeaten", 0) - out.get("away_streak_unbeaten", 0)
    )
    out["streak_wins_diff"] = (
        out.get("home_streak_wins", 0) - out.get("away_streak_wins", 0)
    )
    out["streak_clean_sheets_diff"] = (
        out.get("home_streak_clean_sheets", 0)
        - out.get("away_streak_clean_sheets", 0)
    )

    return out


def map_h2h(payload: dict[str, Any]) -> dict[str, Any]:
    """Converte resposta do endpoint /h2h em features numéricas."""
    out: dict[str, Any] = {}

    team_duel = payload.get("teamDuel") or {}
    out["h2h_home_wins_all"] = _safe_int(team_duel.get("homeWins"))
    out["h2h_away_wins_all"] = _safe_int(team_duel.get("awayWins"))
    out["h2h_draws_all"] = _safe_int(team_duel.get("draws"))

    total = (
        out["h2h_home_wins_all"]
        + out["h2h_away_wins_all"]
        + out["h2h_draws_all"]
    )
    out["h2h_total_all"] = total

    if total > 0:
        out["h2h_home_win_rate"] = round(out["h2h_home_wins_all"] / total, 3)
        out["h2h_away_win_rate"] = round(out["h2h_away_wins_all"] / total, 3)
        out["h2h_draw_rate"] = round(out["h2h_draws_all"] / total, 3)
    else:
        out["h2h_home_win_rate"] = 0.0
        out["h2h_away_win_rate"] = 0.0
        out["h2h_draw_rate"] = 0.0

    # Últimos confrontos (tendência recente)
    matches = payload.get("matches") or payload.get("events") or []
    recent_matches = matches[:5]
    if recent_matches:
        home_wins_recent = 0
        away_wins_recent = 0
        draws_recent = 0
        for m in recent_matches:
            winner = str(m.get("winnerCode") or "")
            if winner == "1":
                home_wins_recent += 1
            elif winner == "2":
                away_wins_recent += 1
            elif winner == "3":
                draws_recent += 1

        out["h2h_home_wins_recent5"] = home_wins_recent
        out["h2h_away_wins_recent5"] = away_wins_recent
        out["h2h_draws_recent5"] = draws_recent
    else:
        out["h2h_home_wins_recent5"] = 0
        out["h2h_away_wins_recent5"] = 0
        out["h2h_draws_recent5"] = 0

    return out


def map_incidents_extended(payload: dict[str, Any]) -> dict[str, Any]:
    """Extrai métricas temporais de incidentes (gols por período, etc)."""
    out: dict[str, Any] = {
        "incident_first_goal_minute": None,
        "incident_goals_ht_home": 0,
        "incident_goals_ht_away": 0,
        "incident_goals_ft_home": 0,
        "incident_goals_ft_away": 0,
        "incident_red_cards_before_60_home": 0,
        "incident_red_cards_before_60_away": 0,
    }

    first_goal_set = False
    for item in payload.get("incidents") or []:
        is_home = bool(item.get("isHome"))
        side = "home" if is_home else "away"
        incident_type = str(item.get("incidentType") or "").lower()
        incident_class = str(item.get("incidentClass") or "").lower()
        minute = _safe_int(item.get("time"))

        if incident_type == "goal":
            if not first_goal_set:
                out["incident_first_goal_minute"] = minute
                first_goal_set = True

            if minute <= 45:
                out[f"incident_goals_ht_{side}"] += 1
            else:
                out[f"incident_goals_ft_{side}"] += 1

        elif incident_type == "card" and incident_class == "red":
            if minute < 60:
                out[f"incident_red_cards_before_60_{side}"] += 1

    return out


def flatten_enrich_features(
    *,
    event_id: int,
    home_team: str,
    away_team: str,
    match_date: str | None,
    pregame_form: dict[str, Any] | None,
    team_streaks: dict[str, Any] | None,
    h2h: dict[str, Any] | None,
    incidents: dict[str, Any] | None,
) -> dict[str, Any]:
    """Combina todos os dados enriquecidos em uma única linha de features."""
    row: dict[str, Any] = {
        "event_id": event_id,
        "home_team": home_team,
        "away_team": away_team,
        "match_date": match_date,
        "source": "sofascore",
    }

    if pregame_form:
        row.update(map_pregame_form(pregame_form))
    if team_streaks:
        row.update(map_team_streaks(team_streaks))
    if h2h:
        row.update(map_h2h(h2h))
    if incidents:
        row.update(map_incidents_extended(incidents))

    return row
