from datetime import datetime, timezone

import pandas as pd

from ingest.fixtures.world_cup import WC_EDITIONS, edition_label
from models.wc_predictor import WcPrediction, WcPredictor
from schemas.national_teams import normalize_national_team

PHASE_LABELS: dict[str, str] = {
    "group": "Fase de grupos",
    "round_16": "Oitavas de final",
    "quarter": "Quartas de final",
    "semi": "Semifinal",
    "third_place": "Disputa 3º lugar",
    "final": "Final",
    "knockout": "Mata-mata",
}


def _parse_match_date(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return pd.to_datetime(value, utc=True).to_pydatetime()


def _optional_str(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return str(value)


def list_wc_editions(fixtures_df: pd.DataFrame) -> list[dict]:
    if fixtures_df.empty:
        return []

    seasons = sorted(fixtures_df["season"].dropna().unique().astype(int))
    editions: list[dict] = []
    for season in seasons:
        if season not in WC_EDITIONS:
            continue
        count = int((fixtures_df["season"] == season).sum())
        editions.append(
            {
                "season": season,
                "label": edition_label(season),
                "match_count": count,
            }
        )
    return editions


def list_edition_matches(fixtures_df: pd.DataFrame, season: int) -> list[dict]:
    edition = fixtures_df[fixtures_df["season"] == season].copy()
    if edition.empty:
        return []

    edition = edition.sort_values("match_date")
    matches: list[dict] = []
    for _, row in edition.iterrows():
        phase = str(row.get("phase", "group"))
        matches.append(
            {
                "match_id": row["match_id"],
                "season": int(row["season"]),
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "match_date": _parse_match_date(row["match_date"]).isoformat(),
                "phase": phase,
                "phase_label": PHASE_LABELS.get(phase, phase),
                "group_name": _optional_str(row.get("group_name")),
                "home_score": int(row["home_score"]),
                "away_score": int(row["away_score"]),
                "result": row["label"],
                "result_label": _result_label(row["label"]),
                "score": f"{int(row['home_score'])}x{int(row['away_score'])}",
            }
        )
    return matches


def _result_label(label: str) -> str:
    return {"1": "Vitória mandante", "X": "Empate", "2": "Vitória visitante"}.get(
        label, label
    )


def find_historical_match(
    fixtures_df: pd.DataFrame,
    season: int,
    *,
    match_id: str | None = None,
    home_team: str | None = None,
    away_team: str | None = None,
) -> pd.Series:
    edition = fixtures_df[fixtures_df["season"] == season]
    if edition.empty:
        raise ValueError(f"Edição {season} sem jogos nos fixtures")

    if match_id:
        found = edition[edition["match_id"] == match_id]
        if found.empty:
            raise ValueError(f"Jogo não encontrado: {match_id}")
        return found.iloc[0]

    if not home_team or not away_team:
        raise ValueError("Informe match_id ou home_team e away_team")

    home = normalize_national_team(home_team)
    away = normalize_national_team(away_team)
    found = edition[
        (edition["home_team"] == home) & (edition["away_team"] == away)
    ]
    if found.empty:
        raise ValueError(f"Jogo não encontrado: {home} x {away} ({season})")
    if len(found) > 1:
        found = found.sort_values("match_date")
    return found.iloc[-1]


def validate_historical_match(
    predictor: WcPredictor,
    fixtures_df: pd.DataFrame,
    season: int,
    *,
    match_id: str | None = None,
    home_team: str | None = None,
    away_team: str | None = None,
) -> dict:
    row = find_historical_match(
        fixtures_df,
        season,
        match_id=match_id,
        home_team=home_team,
        away_team=away_team,
    )
    match_date = _parse_match_date(row["match_date"])
    home = row["home_team"]
    away = row["away_team"]
    phase = str(row.get("phase", "group"))
    is_neutral = bool(row.get("is_neutral", True))
    actual_result = row["label"]

    pred: WcPrediction = predictor.predict(
        home,
        away,
        phase=phase,
        is_neutral=is_neutral,
        before_date=match_date,
    )

    return {
        "match": {
            "match_id": row["match_id"],
            "season": int(row["season"]),
            "home_team": home,
            "away_team": away,
            "match_date": match_date.isoformat(),
            "phase": phase,
            "phase_label": PHASE_LABELS.get(phase, phase),
            "group_name": _optional_str(row.get("group_name")),
            "home_score": int(row["home_score"]),
            "away_score": int(row["away_score"]),
            "actual_result": actual_result,
            "actual_result_label": _result_label(actual_result),
            "actual_score": f"{int(row['home_score'])}x{int(row['away_score'])}",
        },
        "prediction": pred.prediction,
        "confidence": pred.confidence,
        "prob_home": pred.prob_home,
        "prob_draw": pred.prob_draw,
        "prob_away": pred.prob_away,
        "poisson_score": pred.poisson_score,
        "expected_goals": pred.expected_goals,
        "correct": pred.prediction == actual_result,
        "context": pred.context,
        "h2h_summary": pred.h2h_summary,
        "model_breakdown": pred.model_breakdown,
        "cutoff_date": match_date.isoformat(),
        "cutoff_note": (
            f"Modelo treinado apenas com dados anteriores a "
            f"{match_date.strftime('%d/%m/%Y')}"
        ),
    }
