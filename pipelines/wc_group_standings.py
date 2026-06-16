"""Classificação simulada por grupo a partir dos palpites 1/X/2."""
from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

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


def _init_team_row(team: str) -> dict:
    return {
        "team": normalize_national_team(team),
        "played": 0,
        "won": 0,
        "drawn": 0,
        "lost": 0,
        "points": 0,
        "gf": 0,
        "ga": 0,
    }


def _parse_kickoff(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


def _apply_match_result(
    tables: dict[str, dict[str, dict]],
    *,
    group_id: str,
    home: str,
    away: str,
    home_score: int,
    away_score: int,
) -> None:
    """Atualiza tabela com placar real (gols reais, não projeção 2-0)."""
    if group_id not in tables:
        return
    home_n = normalize_national_team(home)
    away_n = normalize_national_team(away)
    if home_n not in tables[group_id] or away_n not in tables[group_id]:
        return

    for side, opp, gf, ga, outcome in (
        (home_n, away_n, home_score, away_score, _result_outcome(home_score, away_score, True)),
        (away_n, home_n, away_score, home_score, _result_outcome(home_score, away_score, False)),
    ):
        row = tables[group_id][side]
        row["played"] += 1
        row["gf"] += gf
        row["ga"] += ga
        if outcome == "win":
            row["won"] += 1
            row["points"] += 3
        elif outcome == "draw":
            row["drawn"] += 1
            row["points"] += 1
        else:
            row["lost"] += 1


def _result_outcome(home_score: int, away_score: int, is_home: bool) -> str:
    if home_score == away_score:
        return "draw"
    home_win = home_score > away_score
    if is_home:
        return "win" if home_win else "loss"
    return "win" if not home_win else "loss"


def build_group_standings_from_results(
    groups: list[dict],
    results: list[dict],
) -> list[dict]:
    """Classificação real a partir de placares (home_score/away_score)."""
    tables: dict[str, dict[str, dict]] = {}
    for group in groups:
        gid = group["id"]
        tables[gid] = {normalize_national_team(t): _init_team_row(t) for t in group["teams"]}

    for res in results:
        gid = res.get("group")
        if not gid or gid not in tables:
            continue
        _apply_match_result(
            tables,
            group_id=str(gid),
            home=res["home_team"],
            away=res["away_team"],
            home_score=int(res["home_score"]),
            away_score=int(res["away_score"]),
        )

    return _finalize_standings(tables)


def load_wc_group_results(
    round_data: dict,
    *,
    as_of: datetime | None = None,
    fixtures_df: pd.DataFrame | None = None,
) -> list[dict]:
    """Placares reais dos jogos oficiais da fase de grupos até ``as_of`` (UTC)."""
    as_of = as_of or datetime.now(UTC)
    as_of_ts = pd.Timestamp(as_of)
    if as_of_ts.tzinfo is None:
        as_of_ts = as_of_ts.tz_localize("UTC")

    matches = round_data.get("matches", [])
    schedule: dict[tuple[str, str], dict] = {}
    for match in matches:
        if match.get("phase", round_data.get("phase", "group")) != "group":
            continue
        home = normalize_national_team(match["home_team"])
        away = normalize_national_team(match["away_team"])
        schedule[(home, away)] = match

    results: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def _append(home: str, away: str, hs: int, as_: int, group: str | None) -> None:
        key = (home, away)
        if key in seen:
            return
        seen.add(key)
        results.append(
            {
                "home_team": home,
                "away_team": away,
                "home_score": hs,
                "away_score": as_,
                "group": group,
            }
        )

    for key, match in schedule.items():
        home, away = key
        hs = match.get("home_score")
        as_ = match.get("away_score")
        if hs is not None and as_ is not None:
            kickoff = _parse_kickoff(match.get("kickoff"))
            if kickoff is not None and kickoff > as_of:
                continue
            _append(home, away, int(hs), int(as_), match.get("group"))

    if fixtures_df is None:
        try:
            from ingest.fixtures.world_cup import load_wc_fixtures

            season = int(round_data.get("season", 2026))
            fixtures_df = load_wc_fixtures(seasons=[season])
        except Exception:
            fixtures_df = pd.DataFrame()

    if fixtures_df is not None and not fixtures_df.empty:
        for _, row in fixtures_df.iterrows():
            if pd.isna(row.get("home_score")) or pd.isna(row.get("away_score")):
                continue
            fh = normalize_national_team(str(row["home_team"]))
            fa = normalize_national_team(str(row["away_team"]))
            match_meta = schedule.get((fh, fa))
            if match_meta is None:
                match_meta = schedule.get((fa, fh))
                if match_meta is None:
                    continue
                home = normalize_national_team(match_meta["home_team"])
                away = normalize_national_team(match_meta["away_team"])
                hs = int(row["away_score"])
                as_ = int(row["home_score"])
            else:
                home = fh
                away = fa
                hs = int(row["home_score"])
                as_ = int(row["away_score"])

            md = pd.to_datetime(row["match_date"], utc=True)
            if md > as_of_ts:
                continue
            _append(home, away, hs, as_, match_meta.get("group"))

    return results


def merge_real_into_simulated(sim_blocks: list[dict], real_blocks: list[dict]) -> list[dict]:
    """Anexa pontos reais (``real_*``) às linhas da classificação simulada."""
    real_map = {
        block["group"]: {row["team"]: row for row in block["standings"]} for block in real_blocks
    }
    for block in sim_blocks:
        by_team = real_map.get(block["group"], {})
        for row in block["standings"]:
            real = by_team.get(row["team"], {})
            row["real_points"] = int(real.get("points", 0))
            row["real_played"] = int(real.get("played", 0))
            row["real_gd"] = int(real.get("gd", 0))
    return sim_blocks


def _finalize_standings(tables: dict[str, dict[str, dict]]) -> list[dict]:
    result: list[dict] = []
    for gid in sorted(tables.keys()):
        rows = list(tables[gid].values())
        rows.sort(key=lambda r: (-r["points"], -(r["gf"] - r["ga"]), r["team"]))
        for i, row in enumerate(rows, 1):
            row["position"] = i
            row["gd"] = row["gf"] - row["ga"]
        result.append({"group": gid, "standings": rows})
    return result


def build_group_standings(
    groups: list[dict],
    predictions: list[dict],
) -> list[dict]:
    """groups: [{id, teams}], predictions: [{home_team, away_team, prediction, group?}]"""
    tables: dict[str, dict[str, dict]] = {}

    for group in groups:
        gid = group["id"]
        tables[gid] = {normalize_national_team(t): _init_team_row(t) for t in group["teams"]}

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

    return _finalize_standings(tables)
