import json
from pathlib import Path

DEFAULT_SCHEDULE = Path("data/rounds/wc_2026.json")


def load_wc_schedule(path: Path = DEFAULT_SCHEDULE) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Calendário WC não encontrado: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_schedule_response(data: dict) -> dict:
    groups_raw = data.get("groups") or _groups_from_matches(data.get("matches", []))
    matches = [_normalize_match(m, data) for m in data.get("matches", [])]
    matches.sort(key=lambda m: (m["round"], m.get("group") or "", m.get("kickoff") or ""))

    return {
        "season": data.get("season", 2026),
        "competition": data.get("competition", "Copa do Mundo"),
        "phase": data.get("phase", "group"),
        "groups": groups_raw,
        "matchdays": sorted({m["round"] for m in matches}),
        "matches": matches,
        "total_matches": len(matches),
    }


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
