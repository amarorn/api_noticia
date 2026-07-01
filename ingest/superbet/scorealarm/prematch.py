"""Parser de forma pré-jogo e H2H a partir do overview + endpoint H2H ScoreAlarm."""
from __future__ import annotations

from typing import Any


def _ft_score(scores: list[dict[str, Any]] | None) -> tuple[int, int]:
    """Placar final (type=0) ou primeiro score disponível."""
    for row in scores or []:
        if int(row.get("type") or -1) == 0:
            return int(row.get("team1") or 0), int(row.get("team2") or 0)
    if scores:
        row = scores[0]
        return int(row.get("team1") or 0), int(row.get("team2") or 0)
    return 0, 0


def _result_char(goals_for: int, goals_against: int) -> str:
    if goals_for > goals_against:
        return "V"
    if goals_for == goals_against:
        return "E"
    return "D"


def parse_manager(raw: dict[str, Any] | None) -> str | None:
    """Nome do treinador em ``team1_manager`` / ``team2_manager`` do overview."""
    if not raw:
        return None
    name = str(raw.get("name") or "").strip()
    if name:
        return name
    for item in raw.get("names") or []:
        value = item.get("value") or {}
        if isinstance(value, dict):
            alt = value.get("string_value")
            if alt:
                return str(alt).strip()
    return None


def parse_team_form_from_events(
    events: list[dict[str, Any]],
    *,
    focal_team_id: str | None = None,
    focal_team_name: str | None = None,
    focal_side: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Últimos jogos de um time (``team1_events`` / ``team2_events`` do H2H)."""
    matches: list[dict[str, Any]] = []
    for ev in (events or [])[:limit]:
        t1 = ev.get("team1") or {}
        t2 = ev.get("team2") or {}
        g1, g2 = _ft_score(ev.get("scores"))
        side = focal_side
        if side is None:
            if focal_team_id and str(t1.get("id") or "") == focal_team_id:
                side = "team1"
            elif focal_team_id and str(t2.get("id") or "") == focal_team_id:
                side = "team2"
            elif focal_team_name:
                name = focal_team_name.casefold()
                if str(t1.get("name") or "").casefold() == name:
                    side = "team1"
                elif str(t2.get("name") or "").casefold() == name:
                    side = "team2"
        if side == "team1":
            goals_for, goals_against = g1, g2
            opponent = str(t2.get("name") or "")
        elif side == "team2":
            goals_for, goals_against = g2, g1
            opponent = str(t1.get("name") or "")
        else:
            continue
        matches.append(
            {
                "opponent": opponent,
                "score": f"{goals_for}-{goals_against}",
                "result": _result_char(goals_for, goals_against),
                "goals_for": goals_for,
                "goals_against": goals_against,
            }
        )

    n = len(matches) or 1
    form = "-".join(m["result"] for m in matches)
    return {
        "form": form,
        "wins": sum(1 for m in matches if m["result"] == "V"),
        "draws": sum(1 for m in matches if m["result"] == "E"),
        "losses": sum(1 for m in matches if m["result"] == "D"),
        "goals_avg": round(sum(m["goals_for"] for m in matches) / n, 2),
        "conceded_avg": round(sum(m["goals_against"] for m in matches) / n, 2),
        "last_matches": matches,
    }


def parse_h2h_recent_matches(
    events: list[dict[str, Any]],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Confrontos diretos recentes (``h2h_events``)."""
    out: list[dict[str, Any]] = []
    for ev in (events or [])[:limit]:
        t1 = ev.get("team1") or {}
        t2 = ev.get("team2") or {}
        g1, g2 = _ft_score(ev.get("scores"))
        out.append(
            {
                "home_team": str(t1.get("name") or ""),
                "away_team": str(t2.get("name") or ""),
                "score": f"{g1}-{g2}",
            }
        )
    return out


def build_prematch_context(
    overview: dict[str, Any],
    h2h_payload: dict[str, Any] | None,
    *,
    home_team: str,
    away_team: str,
) -> dict[str, Any] | None:
    """Monta bloco ``prematch`` para o payload do advice."""
    if not h2h_payload:
        return None

    home = parse_team_form_from_events(
        h2h_payload.get("team1_events") or [],
        focal_team_name=home_team,
    )
    away = parse_team_form_from_events(
        h2h_payload.get("team2_events") or [],
        focal_team_name=away_team,
    )
    home["coach"] = parse_manager(overview.get("team1_manager"))
    away["coach"] = parse_manager(overview.get("team2_manager"))
    home["team"] = home_team
    away["team"] = away_team

    h2h_matches = parse_h2h_recent_matches(h2h_payload.get("h2h_events") or [])
    if not home["form"] and not away["form"] and not h2h_matches:
        return None

    return {
        "home": home,
        "away": away,
        "h2h_matches": h2h_matches,
    }


def _confidence_label_from_score(score: float) -> str:
    if score >= 0.7:
        return "alta"
    if score >= 0.4:
        return "media"
    if score >= 0.2:
        return "baixa"
    return "especulativa"


def apply_prematch_confidence_boost(
    confidence: dict[str, Any] | None,
    prematch: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Sobe confiança quando há forma recente ScoreAlarm (até +0,15)."""
    if not confidence or not prematch:
        return confidence

    boost = 0.0
    notes: list[str] = []
    home = prematch.get("home") or {}
    away = prematch.get("away") or {}

    if len(str(home.get("form") or "")) >= 5:
        boost += 0.05
        notes.append("forma recente do mandante")
    if len(str(away.get("form") or "")) >= 5:
        boost += 0.05
        notes.append("forma do visitante")
    if len(prematch.get("h2h_matches") or []) >= 1:
        boost += 0.05
        notes.append("confronto direto ScoreAlarm")
    if home.get("coach") or away.get("coach"):
        boost += 0.02
        notes.append("escalação técnica disponível")

    if boost <= 0:
        return confidence

    boost = min(0.15, boost)
    base = float(confidence.get("score") or 0)
    new_score = round(min(1.0, base + boost), 3)
    reason = str(confidence.get("reason") or "")
    note = "Dados pré-jogo ScoreAlarm: " + ", ".join(notes) + "."
    if note not in reason:
        reason = f"{reason} {note}".strip()

    out = dict(confidence)
    out["score"] = new_score
    out["label"] = _confidence_label_from_score(new_score)
    out["reason"] = reason
    out["prematch_boost"] = round(boost, 3)
    return out


__all__ = [
    "apply_prematch_confidence_boost",
    "build_prematch_context",
    "parse_h2h_recent_matches",
    "parse_manager",
    "parse_team_form_from_events",
]
