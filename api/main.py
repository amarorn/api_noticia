from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from config import settings
from ingest.fixtures.store import load_fixtures
from ingest.odds.the_odds_api import fetch_live_h2h_odds, merge_schedule_with_odds, save_odds_file
from ingest.meta import collection_stats
from models.ev_value import MatchValueReport, evaluate_match
from models.bolao_predictor import BolaoPrediction, get_predictor
from models.wc_predictor import WcPredictor
from pipelines.current_round import load_round_schedule, predict_round
from pipelines.gold import build_gold_for_match
from pipelines.silver import load_silver

app = FastAPI(
    title="Bolão News API",
    description="API de contexto e previsão baseada em notícias esportivas",
    version="0.2.0",
)


class MatchRequest(BaseModel):
    home_team: str = Field(..., examples=["Flamengo"])
    away_team: str = Field(..., examples=["Palmeiras"])
    round_number: int = Field(1, ge=1)
    competition: str = Field("Brasileirão", examples=["Brasileirão"])
    season: int | None = None


class MatchContextResponse(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    context_text: str
    news_count_home: int
    news_count_away: int
    injury_mentions_home: int
    injury_mentions_away: int
    sentiment_home: float | None
    sentiment_away: float | None
    home_position: int | None = None
    away_position: int | None = None
    home_form: str | None = None
    away_form: str | None = None
    prediction: str | None = None
    confidence: float | None = None
    reason: str | None = None
    probabilities: dict[str, float] | None = None
    model_source: str | None = None


class RoundPrediction(BaseModel):
    home_team: str
    away_team: str
    prediction: str
    confidence: float
    reason: str
    news_count: int
    probabilities: dict[str, float] | None = None
    model_source: str | None = None


class RoundResponse(BaseModel):
    round_number: int
    competition: str
    predictions: list[RoundPrediction]


class WcValueRequest(BaseModel):
    schedule_file: str = Field("data/rounds/wc_2026.json", examples=["data/rounds/wc_2026.json"])
    output_odds_file: str = Field(
        "data/rounds/wc_2026_odds.json",
        examples=["data/rounds/wc_2026_odds.json"],
    )
    sport_key: str | None = Field(None, examples=["soccer_fifa_world_cup"])
    bookmaker: str | None = Field(None, examples=["bet365"])
    regions: str | None = Field(None, examples=["eu"])
    min_edge: float = Field(0.03, ge=0.0, le=1.0)
    save_odds_file: bool = True


class WcOutcomeValue(BaseModel):
    outcome: str
    odd: float
    model_prob: float
    implied_prob: float
    expected_value: float
    fair_odd: float
    kelly_quarter: float


class WcMatchValueResponse(BaseModel):
    home_team: str
    away_team: str
    best: WcOutcomeValue | None = None
    outcomes: list[WcOutcomeValue]


class WcValueResponse(BaseModel):
    matched_games: int
    total_schedule_games: int
    source: str
    captured_at: str | None = None
    edges: list[WcMatchValueResponse]


def _apply_prediction(resp: MatchContextResponse, result: BolaoPrediction) -> MatchContextResponse:
    resp.prediction = result.prediction
    resp.confidence = round(result.confidence, 4)
    resp.reason = result.reason
    resp.probabilities = {k: round(v, 4) for k, v in result.probabilities.items()}
    resp.model_source = result.model_source
    return resp


def _context_to_response(context, include_prediction: bool = False) -> MatchContextResponse:
    resp = MatchContextResponse(
        match_id=context.match_id,
        home_team=context.home_team,
        away_team=context.away_team,
        context_text=context.context_text,
        news_count_home=context.features.news_count_home,
        news_count_away=context.features.news_count_away,
        injury_mentions_home=context.features.injury_mentions_home,
        injury_mentions_away=context.features.injury_mentions_away,
        sentiment_home=context.features.sentiment_home,
        sentiment_away=context.features.sentiment_away,
        home_position=context.features.home_position,
        away_position=context.features.away_position,
        home_form=context.features.home_form,
        away_form=context.features.away_form,
    )
    if include_prediction:
        return _apply_prediction(resp, get_predictor().predict(context))
    return resp


def _match_value_to_response(report: MatchValueReport) -> WcMatchValueResponse:
    best = None
    if report.best:
        best = WcOutcomeValue(
            outcome=report.best.outcome,
            odd=report.best.odd,
            model_prob=report.best.model_prob,
            implied_prob=report.best.implied_prob,
            expected_value=report.best.expected_value,
            fair_odd=report.best.fair_odd,
            kelly_quarter=report.best.kelly_quarter,
        )
    outcomes = [
        WcOutcomeValue(
            outcome=item.outcome,
            odd=item.odd,
            model_prob=item.model_prob,
            implied_prob=item.implied_prob,
            expected_value=item.expected_value,
            fair_odd=item.fair_odd,
            kelly_quarter=item.kelly_quarter,
        )
        for item in report.outcomes
    ]
    return WcMatchValueResponse(
        home_team=report.home_team,
        away_team=report.away_team,
        best=best,
        outcomes=outcomes,
    )


@app.get("/health")
def health():
    stats = collection_stats()
    silver_df = load_silver()
    fixtures_df = load_fixtures()
    return {
        "status": "ok",
        "lake_root": str(settings.lake_root),
        "articles_silver": len(silver_df),
        "fixtures": len(fixtures_df),
        "collections": stats,
        "predictor": get_predictor().status(),
    }


@app.get("/")
def root():
    return {
        "name": "api-noticia",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "endpoints": [
            "/context",
            "/predict",
            "/round/predict",
            "/worldcup/value/live",
        ],
    }


def _build_match_context(req: MatchRequest):
    silver_df = load_silver()
    fixtures_df = load_fixtures()
    match_id = f"{req.home_team}_{req.away_team}_{req.round_number}".lower().replace(" ", "_")
    return build_gold_for_match(
        match_id=match_id,
        home_team=req.home_team,
        away_team=req.away_team,
        round_number=req.round_number,
        competition=req.competition,
        match_date=datetime.now(UTC),
        silver_df=silver_df,
        season=req.season,
        fixtures_df=fixtures_df if not fixtures_df.empty else None,
        live_mode=True,
    )


@app.post("/context", response_model=MatchContextResponse)
def get_match_context(req: MatchRequest):
    context = _build_match_context(req)
    return _context_to_response(context)


@app.post("/predict", response_model=MatchContextResponse)
def predict_match(req: MatchRequest):
    context = _build_match_context(req)
    return _context_to_response(context, include_prediction=True)


@app.get("/round/predict", response_model=RoundResponse)
def predict_current_round():
    try:
        schedule = load_round_schedule()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    results = predict_round(save=False)
    return RoundResponse(
        round_number=schedule["round"],
        competition=schedule.get("competition", "Brasileirão"),
        predictions=[
            RoundPrediction(
                home_team=r["home_team"],
                away_team=r["away_team"],
                prediction=r["prediction"],
                confidence=r["confidence"],
                reason=r["reason"],
                news_count=r["news_count"],
                probabilities=r.get("probabilities"),
                model_source=r.get("model_source"),
            )
            for r in results
        ],
    )


@app.post("/worldcup/value/live", response_model=WcValueResponse)
def worldcup_live_value(req: WcValueRequest):
    schedule_path = Path(req.schedule_file)
    if not schedule_path.exists():
        raise HTTPException(status_code=404, detail=f"Schedule não encontrado: {schedule_path}")

    try:
        import json

        schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha ao ler schedule: {exc}") from exc

    try:
        live_odds = fetch_live_h2h_odds(
            sport_key=req.sport_key,
            regions=req.regions,
            preferred_bookmaker=req.bookmaker,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Odds API: {exc}") from exc

    merged, matched = merge_schedule_with_odds(schedule, live_odds)
    if req.save_odds_file:
        save_odds_file(merged, Path(req.output_odds_file))

    predictor = WcPredictor()
    phase_default = merged.get("phase", "group")
    reports: list[WcMatchValueResponse] = []

    for match in merged.get("matches", []):
        phase = match.get("phase", phase_default)
        pred = predictor.predict(match["home_team"], match["away_team"], phase=phase)
        probabilities = {"1": pred.prob_home, "X": pred.prob_draw, "2": pred.prob_away}
        value = evaluate_match(
            home_team=match["home_team"],
            away_team=match["away_team"],
            probabilities=probabilities,
            odds=match["odds"],
            min_edge=req.min_edge,
        )
        reports.append(_match_value_to_response(value))

    return WcValueResponse(
        matched_games=matched,
        total_schedule_games=len(schedule.get("matches", [])),
        source=merged.get("source", "the-odds-api"),
        captured_at=merged.get("captured_at"),
        edges=reports,
    )
