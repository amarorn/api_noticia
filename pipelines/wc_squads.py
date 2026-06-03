import json
from pathlib import Path

DEFAULT_SQUADS = Path("data/wc/squads_2026.json")


def load_wc_squads(path: Path = DEFAULT_SQUADS) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Convocações WC não encontradas: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_squad_teams(data: dict) -> list[dict]:
    return [
        {
            "team": squad["team"],
            "player_count": squad["player_count"],
        }
        for squad in data.get("squads", [])
    ]


def get_squad_by_team(data: dict, team: str) -> dict | None:
    target = team.casefold()
    for squad in data.get("squads", []):
        if squad["team"].casefold() == target:
            return squad
    return None
