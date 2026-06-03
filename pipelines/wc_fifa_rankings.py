"""Ranking FIFA (estático) para features do modelo WC."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from schemas.national_teams import normalize_national_team

DEFAULT_PATH = Path("data/wc/fifa_rankings_2026.json")
NEUTRAL_POINTS = 1500.0


@lru_cache(maxsize=1)
def load_fifa_rankings(path: str | None = None) -> dict[str, float]:
    p = Path(path) if path else DEFAULT_PATH
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    teams = data.get("teams", data)
    out: dict[str, float] = {}
    if isinstance(teams, list):
        for row in teams:
            name = normalize_national_team(str(row["team"]))
            out[name.casefold()] = float(row.get("points", NEUTRAL_POINTS))
    elif isinstance(teams, dict):
        for name, pts in teams.items():
            out[normalize_national_team(name).casefold()] = float(pts)
    return out


def fifa_points(team: str, rankings: dict[str, float] | None = None) -> float:
    table = rankings if rankings is not None else load_fifa_rankings()
    return table.get(normalize_national_team(team).casefold(), NEUTRAL_POINTS)


def fifa_rankings_fingerprint(path: Path | None = None) -> str:
    p = path or DEFAULT_PATH
    if not p.exists():
        return "missing"
    st = p.stat()
    return f"{p.name}:{st.st_mtime_ns}:{st.st_size}"
