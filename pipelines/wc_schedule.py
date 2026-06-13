import json
from pathlib import Path

from schemas.national_teams import normalize_national_team

DEFAULT_SCHEDULE = Path("data/rounds/wc_2026.json")
LATEST_PREDICTIONS = Path("data/lake/reports/wc_2026_predictions_latest.json")


def load_wc_schedule(path: Path = DEFAULT_SCHEDULE) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Calendário WC não encontrado: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_schedule_response(data: dict) -> dict:
    groups_raw = data.get("groups") or _groups_from_matches(data.get("matches", []))
    matches = [_normalize_match(m, data) for m in data.get("matches", [])]
    matches.sort(key=lambda m: (m["round"], m.get("group") or "", m.get("kickoff") or ""))
    predictions_map = _load_schedule_predictions_map()
    dist = {"1": 0, "X": 0, "2": 0}
    for match in matches:
        key = (normalize_national_team(match["home_team"]), normalize_national_team(match["away_team"]))
        pred = predictions_map.get(key)
        if pred:
            match["prediction"] = pred["prediction"]
            match["confidence"] = pred["confidence"]
            match["prob_home"] = pred["prob_home"]
            match["prob_draw"] = pred["prob_draw"]
            match["prob_away"] = pred["prob_away"]
            dist[pred["prediction"]] = dist.get(pred["prediction"], 0) + 1

    return {
        "season": data.get("season", 2026),
        "competition": data.get("competition", "Copa do Mundo"),
        "phase": data.get("phase", "group"),
        "groups": groups_raw,
        "matchdays": sorted({m["round"] for m in matches}),
        "matches": matches,
        "total_matches": len(matches),
        "predictions_summary": {
            "loaded": len(predictions_map),
            "distribution": dist,
            "draws": dist.get("X", 0),
        },
    }


def _load_schedule_predictions_map() -> dict[tuple[str, str], dict]:
    """Mapa (mandante, visitante) → palpite a partir do JSON mais recente."""
    from config import settings

    candidates = [
        settings.lake_root / "reports" / "wc_2026_predictions_latest.json",
        settings.lake_root / "reports" / "wc_2026_predictions.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        out: dict[tuple[str, str], dict] = {}
        for row in rows:
            home = normalize_national_team(row.get("home_team", ""))
            away = normalize_national_team(row.get("away_team", ""))
            probs = row.get("probabilities") or {}
            out[(home, away)] = {
                "prediction": row.get("prediction"),
                "confidence": row.get("confidence"),
                "prob_home": probs.get("1", row.get("prob_home")),
                "prob_draw": probs.get("X", row.get("prob_draw")),
                "prob_away": probs.get("2", row.get("prob_away")),
            }
        if out:
            return out
    return {}


def _groups_from_matches(matches: list[dict]) -> list[dict]:
    grouped: dict[str, set[str]] = {}
    for match in matches:
        group = match.get("group")
        if not group:
            continue
        grouped.setdefault(str(group), set())
        grouped[str(group)].add(match["home_team"])
        grouped[str(group)].add(match["away_team"])
    return [{"id": gid, "teams": sorted(teams)} for gid, teams in sorted(grouped.items())]


def _normalize_match(match: dict, data: dict) -> dict:
    home = match["home_team"]
    away = match["away_team"]
    match_id = match.get("id") or _slug_match(home, away, match.get("round", 1))
    return {
        "match_id": match_id,
        "home_team": home,
        "away_team": away,
        "group": match.get("group"),
        "round": int(match.get("round", data.get("round", 1))),
        "phase": match.get("phase", data.get("phase", "group")),
        "kickoff": match.get("kickoff"),
        "venue": match.get("venue"),
        "city": match.get("city"),
    }


def _slug_match(home: str, away: str, round_no: int) -> str:
    base = f"{home}_{away}_r{round_no}".lower().replace(" ", "_")
    return base


def official_match_exists(
    home: str,
    away: str,
    phase: str = "group",
    path: Path = DEFAULT_SCHEDULE,
) -> bool:
    data = load_wc_schedule(path)
    for match in data.get("matches", []):
        if match.get("phase", data.get("phase", "group")) != phase:
            continue
        if match["home_team"] == home and match["away_team"] == away:
            return True
    return False
