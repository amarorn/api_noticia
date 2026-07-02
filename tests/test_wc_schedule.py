from pathlib import Path

from pipelines.wc_schedule import build_schedule_response, load_wc_schedule, official_match_exists

WC_JSON = Path("data/rounds/wc_2026.json")


def test_wc_schedule_has_12_groups_and_72_matches() -> None:
    data = load_wc_schedule(WC_JSON)
    out = build_schedule_response(data)
    assert out["season"] == 2026
    assert len(out["groups"]) == 12
    group_matches = [m for m in out["matches"] if m["phase"] == "group"]
    assert len(group_matches) == 72
    # total_matches pode ser > 72 depois que o mata-mata é sincronizado (sync-wc-knockout-schedule)
    assert out["total_matches"] >= 72
    assert {1, 2, 3}.issubset(set(out["matchdays"]))
    group_ids = {g["id"] for g in out["groups"]}
    assert group_ids == set("ABCDEFGHIJKL")


def test_each_group_has_four_teams_and_six_matches() -> None:
    data = load_wc_schedule(WC_JSON)
    out = build_schedule_response(data)
    for group in out["groups"]:
        gid = group["id"]
        assert len(group["teams"]) == 4
        group_matches = [m for m in out["matches"] if m["group"] == gid]
        assert len(group_matches) == 6
        teams_in_matches = set()
        for m in group_matches:
            teams_in_matches.add(m["home_team"])
            teams_in_matches.add(m["away_team"])
        assert teams_in_matches == set(group["teams"])


def test_schedule_includes_scores_when_present() -> None:
    data = load_wc_schedule(WC_JSON)
    out = build_schedule_response(data)
    scored = [m for m in out["matches"] if m.get("played")]
    assert len(scored) >= 1
    first = scored[0]
    assert first["home_score"] is not None
    assert first["away_score"] is not None
    assert first["played"] is True


def test_official_match_exists_respects_home_away() -> None:
    assert official_match_exists("Brasil", "Marrocos", phase="group", path=WC_JSON)
    assert not official_match_exists("Marrocos", "Brasil", phase="group", path=WC_JSON)
    assert not official_match_exists("Brasil", "França", phase="group", path=WC_JSON)
