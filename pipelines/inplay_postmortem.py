"""Post-mortem automático de eventos Superbet finalizados."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from config import settings
from ingest.superbet.live_ticks import live_ticks_path
from models.inplay_tip_settle import evaluate_inplay_tip

logger = structlog.get_logger()


def _gold_event_dir(event_id: int) -> Path:
    return settings.gold_path / "superbet" / "events" / str(event_id)


def postmortem_json_path(event_id: int) -> Path:
    return _gold_event_dir(event_id) / "postmortem.json"


def _parse_score_pair(score: str | None) -> tuple[int | None, int | None]:
    if not score:
        return None, None
    normalized = score.lower().replace("×", "x").strip()
    if "x" not in normalized:
        return None, None
    left, right = normalized.split("x", 1)
    try:
        return int(left), int(right)
    except ValueError:
        return None, None


def load_inplay_postmortem(event_id: int) -> dict[str, Any] | None:
    """Lê postmortem.json do gold, se existir."""
    path = postmortem_json_path(event_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def get_or_build_inplay_postmortem(
    event_id: int,
    *,
    regenerate: bool = False,
) -> dict[str, Any] | None:
    """Retorna post-mortem em cache ou gera a partir de final.json + live_ticks."""
    if not regenerate:
        cached = load_inplay_postmortem(event_id)
        if cached is not None:
            return cached

    final_path = _gold_event_dir(event_id) / "final.json"
    if not final_path.exists():
        return load_inplay_postmortem(event_id)

    final = json.loads(final_path.read_text(encoding="utf-8"))
    home_score = final.get("home_score")
    away_score = final.get("away_score")
    if home_score is None or away_score is None:
        return load_inplay_postmortem(event_id)

    ht_home, ht_away = _parse_score_pair(final.get("ht_score"))
    report = build_inplay_postmortem(
        event_id,
        home_score=int(home_score),
        away_score=int(away_score),
        ht_home=ht_home,
        ht_away=ht_away,
        home_team=final.get("home_team"),
        away_team=final.get("away_team"),
    )
    out_dir = _gold_event_dir(event_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = postmortem_json_path(event_id)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "inplay_postmortem_saved",
        event_id=event_id,
        path=str(out_path),
        regenerated=regenerate,
        issues=len(report.get("issues") or []),
    )
    return report


def _detect_issues(
    *,
    ticks: pd.DataFrame,
    tip_rows: list[dict[str, Any]],
    home_score: int,
    away_score: int,
    ht_home: int | None,
    ht_away: int | None,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if ticks.empty:
        return issues

    kickoff = ticks.sort_values("minute").iloc[0]
    pre_home = float(kickoff.get("prob_final_home") or 0)
    final_draw = home_score == away_score

    if pre_home >= 0.55 and home_score < away_score and final_draw:
        max_away = float(ticks["prob_final_away"].max())
        issues.append({
            "code": "favorite_trailing_overreaction",
            "detail": (
                f"Mandante era favorito ({pre_home:.0%}) mas após gol visitante "
                f"modelo chegou a {max_away:.0%} vitória fora; resultado foi empate."
            ),
        })

    lost_2h_away = [
        r for r in tip_rows
        if r.get("market") == "2h_hcap_away_m0_5"
        and r.get("won") is False
        and int(r.get("n_recommended") or 0) >= 5
    ]
    if lost_2h_away:
        row = lost_2h_away[0]
        issues.append({
            "code": "bad_2h_away_minus_half",
            "detail": (
                f"Egito/visitante −0,5 no 2T recomendado {row['n_recommended']}× "
                f"(min {row['first_minute']}–{row['last_minute']}) e perdeu no FT {home_score}×{away_score}."
            ),
        })

    if ht_home is not None and ht_away is not None:
        ht_draw_ticks = ticks[ticks["minute"] == 45]
        if not ht_draw_ticks.empty and home_score == away_score:
            p_draw_ht = float(ht_draw_ticks.iloc[-1].get("prob_final_draw") or 0)
            if p_draw_ht < 0.30:
                issues.append({
                    "code": "draw_underpriced_at_ht",
                    "detail": (
                        f"No intervalo ({ht_home}×{ht_away}) empate FT estava em "
                        f"só {p_draw_ht:.0%}; fechou {home_score}×{away_score}."
                    ),
                })

    return issues


def build_inplay_postmortem(
    event_id: int,
    *,
    home_score: int,
    away_score: int,
    ht_home: int | None = None,
    ht_away: int | None = None,
    home_team: str | None = None,
    away_team: str | None = None,
) -> dict[str, Any]:
    """Gera relatório pós-jogo a partir de live_ticks."""
    path = live_ticks_path()
    ticks = pd.DataFrame()
    if path.exists():
        df = pd.read_parquet(path)
        if "event_id" in df.columns:
            ticks = df[df["event_id"] == event_id].copy()

    if ticks.empty:
        report = {
            "event_id": event_id,
            "final_score": f"{home_score}x{away_score}",
            "ht_score": f"{ht_home}x{ht_away}" if ht_home is not None else None,
            "n_ticks": 0,
            "tip_summary": {"total_ticks_with_tip": 0, "won": 0, "lost": 0, "unknown": 0},
            "tips_by_market": [],
            "model_timeline": [],
            "issues": [{"code": "no_ticks", "detail": "Sem ticks live_poll para este evento."}],
        }
        return report

    if home_team and ticks["home_team"].notna().any():
        pass
    elif not ticks.empty:
        home_team = str(ticks.iloc[0]["home_team"])
        away_team = str(ticks.iloc[0]["away_team"])

    tip_ticks = ticks.dropna(subset=["top_aporte_market", "top_aporte_outcome"])
    grouped: dict[tuple[str, str], dict[str, Any]] = {}

    for _, row in tip_ticks.iterrows():
        market = str(row["top_aporte_market"])
        outcome = str(row["top_aporte_outcome"])
        key = (market, outcome)
        won = evaluate_inplay_tip(
            market,
            outcome,
            home_score=home_score,
            away_score=away_score,
            ht_home=ht_home,
            ht_away=ht_away,
        )
        if key not in grouped:
            grouped[key] = {
                "market": market,
                "outcome": outcome,
                "n_recommended": 0,
                "max_ev": None,
                "avg_ev": None,
                "first_minute": int(row["minute"]),
                "last_minute": int(row["minute"]),
                "won": won,
                "_ev_sum": 0.0,
            }
        g = grouped[key]
        g["n_recommended"] += 1
        g["last_minute"] = int(row["minute"])
        ev = row.get("top_aporte_ev")
        if pd.notna(ev):
            ev_f = float(ev)
            g["_ev_sum"] += ev_f
            g["max_ev"] = ev_f if g["max_ev"] is None else max(g["max_ev"], ev_f)

    tips_by_market: list[dict[str, Any]] = []
    won_n = lost_n = unknown_n = 0
    for g in grouped.values():
        ev_sum = g.pop("_ev_sum", 0.0)
        n = g["n_recommended"]
        g["avg_ev"] = round(ev_sum / n, 4) if n and ev_sum else None
        if g["max_ev"] is not None:
            g["max_ev"] = round(float(g["max_ev"]), 4)
        if g["won"] is True:
            won_n += 1
            g["result"] = "won"
        elif g["won"] is False:
            lost_n += 1
            g["result"] = "lost"
        else:
            unknown_n += 1
            g["result"] = "unknown"
        tips_by_market.append(g)

    tips_by_market.sort(key=lambda x: (-x["n_recommended"], -(x["max_ev"] or 0)))

    timeline: list[dict[str, Any]] = []
    for _, row in ticks.sort_values("minute").drop_duplicates("minute", keep="last").iterrows():
        timeline.append({
            "minute": int(row["minute"]),
            "score": f"{int(row['home_score'])}x{int(row['away_score'])}",
            "prob_home": round(float(row["prob_final_home"]), 4)
            if pd.notna(row.get("prob_final_home"))
            else None,
            "prob_draw": round(float(row["prob_final_draw"]), 4)
            if pd.notna(row.get("prob_final_draw"))
            else None,
            "prob_away": round(float(row["prob_final_away"]), 4)
            if pd.notna(row.get("prob_final_away"))
            else None,
            "top_tip": (
                f"{row['top_aporte_market']}:{row['top_aporte_outcome']}"
                if pd.notna(row.get("top_aporte_market"))
                else None
            ),
        })

    issues = _detect_issues(
        ticks=ticks,
        tip_rows=tips_by_market,
        home_score=home_score,
        away_score=away_score,
        ht_home=ht_home,
        ht_away=ht_away,
    )

    kickoff = ticks.sort_values("minute").iloc[0]
    final_tick = ticks.sort_values("minute").iloc[-1]

    return {
        "event_id": event_id,
        "home_team": home_team,
        "away_team": away_team,
        "final_score": f"{home_score}x{away_score}",
        "ht_score": f"{ht_home}x{ht_away}" if ht_home is not None else None,
        "n_ticks": int(len(ticks)),
        "kickoff_probs": {
            "home": round(float(kickoff["prob_final_home"]), 4)
            if pd.notna(kickoff.get("prob_final_home"))
            else None,
            "draw": round(float(kickoff["prob_final_draw"]), 4)
            if pd.notna(kickoff.get("prob_final_draw"))
            else None,
            "away": round(float(kickoff["prob_final_away"]), 4)
            if pd.notna(kickoff.get("prob_final_away"))
            else None,
        },
        "final_probs": {
            "home": round(float(final_tick["prob_final_home"]), 4)
            if pd.notna(final_tick.get("prob_final_home"))
            else None,
            "draw": round(float(final_tick["prob_final_draw"]), 4)
            if pd.notna(final_tick.get("prob_final_draw"))
            else None,
            "away": round(float(final_tick["prob_final_away"]), 4)
            if pd.notna(final_tick.get("prob_final_away"))
            else None,
        },
        "tip_summary": {
            "total_ticks_with_tip": int(len(tip_ticks)),
            "unique_tips": len(tips_by_market),
            "won": won_n,
            "lost": lost_n,
            "unknown": unknown_n,
        },
        "tips_by_market": tips_by_market,
        "model_timeline": timeline,
        "issues": issues,
    }


def save_inplay_postmortem(
    event_id: int,
    *,
    home_score: int,
    away_score: int,
    ht_home: int | None = None,
    ht_away: int | None = None,
    home_team: str | None = None,
    away_team: str | None = None,
) -> Path:
    """Persiste postmortem.json no gold do evento."""
    report = build_inplay_postmortem(
        event_id,
        home_score=home_score,
        away_score=away_score,
        ht_home=ht_home,
        ht_away=ht_away,
        home_team=home_team,
        away_team=away_team,
    )
    out_dir = _gold_event_dir(event_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "postmortem.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "inplay_postmortem_saved",
        event_id=event_id,
        path=str(out_path),
        issues=len(report.get("issues") or []),
        tips_won=report["tip_summary"]["won"],
        tips_lost=report["tip_summary"]["lost"],
    )
    return out_path


def list_finalized_superbet_event_ids() -> list[int]:
    """Event_ids com final.json em gold/superbet/events/."""
    base = settings.gold_path / "superbet" / "events"
    if not base.exists():
        return []
    ids: list[int] = []
    for final_path in sorted(base.glob("*/final.json")):
        try:
            ids.append(int(final_path.parent.name))
        except ValueError:
            continue
    return ids


def regenerate_inplay_postmortems(
    *,
    event_ids: list[int] | None = None,
    only_missing: bool = True,
    regenerate: bool = False,
) -> list[dict[str, Any]]:
    """Gera post-mortem para eventos finalizados (backfill em lote)."""
    targets = event_ids or list_finalized_superbet_event_ids()
    results: list[dict[str, Any]] = []

    for event_id in targets:
        if only_missing and not regenerate and load_inplay_postmortem(event_id) is not None:
            results.append({
                "event_id": event_id,
                "status": "skipped",
                "reason": "postmortem_exists",
            })
            continue

        try:
            report = get_or_build_inplay_postmortem(event_id, regenerate=True)
        except Exception as exc:
            logger.warning("postmortem_backfill_failed", event_id=event_id, error=str(exc))
            results.append({
                "event_id": event_id,
                "status": "error",
                "error": str(exc),
            })
            continue

        if report is None:
            results.append({
                "event_id": event_id,
                "status": "error",
                "error": "sem final.json",
            })
            continue

        tip_summary = report.get("tip_summary") or {}
        results.append({
            "event_id": event_id,
            "status": "ok",
            "final_score": report.get("final_score"),
            "n_ticks": report.get("n_ticks"),
            "tips_won": tip_summary.get("won"),
            "tips_lost": tip_summary.get("lost"),
            "issues": len(report.get("issues") or []),
        })

    return results


def main() -> None:
    """CLI: regenerate-inplay-postmortem --all | --event-id ID [--force]."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Gera post-mortem in-play para eventos Superbet finalizados.",
    )
    parser.add_argument("--all", action="store_true", help="Todos com final.json no gold")
    parser.add_argument("--event-id", type=int, action="append", dest="event_ids")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regera mesmo se postmortem.json já existir",
    )
    args = parser.parse_args()

    if not args.all and not args.event_ids:
        parser.error("Informe --all ou --event-id")

    results = regenerate_inplay_postmortems(
        event_ids=args.event_ids,
        only_missing=not args.force,
        regenerate=args.force,
    )
    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")
    print(f"Post-mortem: {ok} gerados, {skipped} ignorados, {errors} erros")
    for row in results:
        if row["status"] == "ok":
            print(
                f"  OK {row['event_id']} {row.get('final_score')} "
                f"ticks={row.get('n_ticks')} won={row.get('tips_won')} lost={row.get('tips_lost')}"
            )
        elif row["status"] == "skipped":
            print(f"  SKIP {row['event_id']}")
        else:
            print(f"  ERR {row['event_id']}: {row.get('error')}")


if __name__ == "__main__":
    main()


__all__ = [
    "build_inplay_postmortem",
    "get_or_build_inplay_postmortem",
    "list_finalized_superbet_event_ids",
    "load_inplay_postmortem",
    "postmortem_json_path",
    "regenerate_inplay_postmortems",
    "save_inplay_postmortem",
]
