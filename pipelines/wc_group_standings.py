"""Classificação simulada por grupo a partir dos palpites 1/X/2."""
from __future__ import annotations

from schemas.national_teams import normalize_national_team


def _points_for_prediction(prediction: str, home_team: str, away_team: str, team: str) -> int:
    team_cf = team.casefold()
    home_cf = normalize_national_team(home_team).casefold()
    away_cf = normalize_national_team(away_team).casefold()
    if team_cf not in (home_cf, away_cf):
        return 0
    is_home = team_cf == home_cf
    if prediction == "X":
        return 1
    if prediction == "1":
        return 3 if is_home else 0
    if prediction == "2":
        return 0 if is_home else 3
    return 0


def build_group_standings(
    groups: list[dict],
    predictions: list[dict],
) -> list[dict]:
    """groups: [{id, teams}], predictions: [{home_team, away_team, prediction, group?}]"""
    tables: dict[str, dict[str, dict]] = {}

    for group in groups:
        gid = group["id"]
        tables[gid] = {
            normalize_national_team(t): {
                "team": normalize_national_team(t),
                "played": 0,
                "won": 0,
                "drawn": 0,
                "lost": 0,
                "points": 0,
                "gf": 0,
                "ga": 0,
            }
            for t in group["teams"]
        }

    for pred in predictions:
        home = normalize_national_team(pred["home_team"])
        away = normalize_national_team(pred["away_team"])
        label = pred["prediction"]
        gid = pred.get("group")
        if not gid and pred.get("group_name"):
            gid = pred["group_name"]
        if not gid:
            for g_id, rows in tables.items():
                if home in rows and away in rows:
                    gid = g_id
                    break
        if not gid or gid not in tables:
            continue

        for side, opp, is_home in ((home, away, True), (away, home, False)):
            row = tables[gid][side]
            row["played"] += 1
            pts = _points_for_prediction(label, home, away, side)
            row["points"] += pts
            if label == "X":
                row["drawn"] += 1
                row["gf"] += 1
                row["ga"] += 1
            elif (label == "1" and is_home) or (label == "2" and not is_home):
                row["won"] += 1
                row["gf"] += 2
                row["ga"] += 0
            else:
                row["lost"] += 1
                row["gf"] += 0
                row["ga"] += 2

    result: list[dict] = []
    for gid in sorted(tables.keys()):
        rows = list(tables[gid].values())
        rows.sort(key=lambda r: (-r["points"], -r["gf"] + r["ga"], r["team"]))
        for i, row in enumerate(rows, 1):
            row["position"] = i
            row["gd"] = row["gf"] - row["ga"]
        result.append({"group": gid, "standings": rows})
    return result
