"""
Features derivadas das convocações Copa 2026 (data/wc/squads_2026.json).
Valores neutros quando a seleção não está no arquivo.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from config import settings

DEFAULT_SQUADS = Path("data/wc/squads_2026.json")

TOP_LEAGUE_PATTERNS = re.compile(
    r"premier|liverpool|manchester|chelsea|arsenal|tottenham|newcastle|brighton|"
    r"real madrid|barcelona|atletico|atlético|sevilla|"
    r"bayern|dortmund|leipzig|frankfurt|stuttgart|hoffenheim|munique|munich|"
    r"juventus|inter|milan|napoli|roma|"
    r"psg|paris saint|marseille|lyon|monaco|ligue",
    re.IGNORECASE,
)


MID_TIER_PATTERNS = re.compile(
    r"liga|serie|bundesliga|ligue|eredivisie|primeira|brasileir|argentin|mls|"
    r"flamengo|palmeiras|boca|river|porto|benfica|sporting|ajax|fenerbah",
    re.IGNORECASE,
)


def _club_strength_score(club: str | None) -> float:
    if not club:
        return 0.35
    if TOP_LEAGUE_PATTERNS.search(club):
        return 1.0
    if MID_TIER_PATTERNS.search(club):
        return 0.65
    return 0.4


@dataclass(frozen=True)
class SquadProfile:
    depth_norm: float
    def_share: float
    mid_share: float
    atk_share: float
    top5_league_share: float
    league_strength_avg: float

    @classmethod
    def neutral(cls) -> SquadProfile:
        return cls(
            depth_norm=1.0,
            def_share=0.35,
            mid_share=0.35,
            atk_share=0.30,
            top5_league_share=0.5,
            league_strength_avg=0.55,
        )


def _count_by_position(squad: dict) -> dict[str, int]:
    counts = {"GK": 0, "DEF": 0, "MID": 0, "ATK": 0, "MID_FWD": 0}
    for section in squad.get("sections", []):
        pos = section.get("position", "")
        n = len(section.get("players", []))
        if pos in counts:
            counts[pos] += n
        elif pos == "MID_FWD":
            counts["MID"] += n
    return counts


def _is_top_league_club(club: str | None) -> bool:
    if not club:
        return False
    return bool(TOP_LEAGUE_PATTERNS.search(club))


def profile_from_squad(squad: dict | None) -> SquadProfile:
    if not squad:
        return SquadProfile.neutral()

    total = max(int(squad.get("player_count", 0)), 1)
    counts = _count_by_position(squad)
    def_n = counts["DEF"]
    mid_n = counts["MID"] + counts["MID_FWD"]
    atk_n = counts["ATK"]
    gk_n = counts["GK"]

    top5 = 0
    players = 0
    strength_sum = 0.0
    for section in squad.get("sections", []):
        for player in section.get("players", []):
            players += 1
            club = player.get("club")
            if _is_top_league_club(club):
                top5 += 1
            strength_sum += _club_strength_score(club)

    field_players = max(players - gk_n, 1)
    return SquadProfile(
        depth_norm=min(total / 26.0, 1.15),
        def_share=def_n / field_players,
        mid_share=mid_n / field_players,
        atk_share=atk_n / field_players,
        top5_league_share=top5 / max(players, 1),
        league_strength_avg=strength_sum / max(players, 1),
    )


@lru_cache(maxsize=1)
def load_squads_index(path: str | None = None) -> dict[str, dict]:
    squads_path = Path(path) if path else DEFAULT_SQUADS
    if not squads_path.exists():
        return {}
    data = json.loads(squads_path.read_text(encoding="utf-8"))
    return {s["team"].casefold(): s for s in data.get("squads", [])}


def get_team_squad(team: str, path: str | None = None) -> dict | None:
    return load_squads_index(path).get(team.casefold())


def squad_feature_vector(home_team: str, away_team: str, path: str | None = None) -> list[float]:
    home = profile_from_squad(get_team_squad(home_team, path))
    away = profile_from_squad(get_team_squad(away_team, path))
    return [
        home.depth_norm - away.depth_norm,
        home.top5_league_share - away.top5_league_share,
        home.def_share - away.def_share,
        home.atk_share - away.atk_share,
        home.mid_share - away.mid_share,
        (home.def_share + home.mid_share * 0.5) - (away.def_share + away.mid_share * 0.5),
        home.league_strength_avg - away.league_strength_avg,
    ]


SQUAD_FEATURE_NAMES = [
    "squad_depth_diff",
    "squad_top5_league_diff",
    "squad_def_share_diff",
    "squad_atk_share_diff",
    "squad_mid_share_diff",
    "squad_structural_balance_diff",
    "squad_league_strength_diff",
]


def squads_fingerprint(path: Path | None = None) -> str:
    squads_path = path or settings.wc_squads_path
    if not squads_path.exists():
        return "missing"
    st = squads_path.stat()
    return f"{squads_path.name}:{st.st_mtime_ns}:{st.st_size}"
