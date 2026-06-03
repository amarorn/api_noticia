from datetime import UTC, datetime

from models.bolao_predictor import (
    BolaoPredictor,
    build_match_prompt,
    parse_bolao_label,
)
from schemas.models import BolaoFeature, GoldBolaoContext


def test_parse_bolao_label():
    assert parse_bolao_label("1") == "1"
    assert parse_bolao_label("Resposta: X") == "X"
    assert parse_bolao_label("vitória visitante 2") == "2"
    assert parse_bolao_label("empate") == "X"


def test_predictor_baseline_without_checkpoint(tmp_path):
    predictor = BolaoPredictor(model_path=tmp_path / "missing", use_lm=True)
    features = BolaoFeature(
        match_id="x",
        home_team="Flamengo",
        away_team="Palmeiras",
        round_number=1,
        competition="Brasileirão",
        match_date=datetime.now(UTC),
        home_position=1,
        away_position=10,
    )
    result = predictor.predict_from_features(features)
    assert result.model_source == "baseline"
    assert result.prediction in ("1", "X", "2")
    assert abs(sum(result.probabilities.values()) - 1.0) < 1e-6


def test_predictor_context_uses_baseline_when_no_lm(tmp_path):
    predictor = BolaoPredictor(model_path=tmp_path / "none", use_lm=False)
    context = GoldBolaoContext(
        match_id="x",
        home_team="Flamengo",
        away_team="Palmeiras",
        round_number=1,
        competition="Brasileirão",
        match_date=datetime.now(UTC),
        context_text="Notícias de teste",
        features=BolaoFeature(
            match_id="x",
            home_team="Flamengo",
            away_team="Palmeiras",
            round_number=1,
            competition="Brasileirão",
            match_date=datetime.now(UTC),
        ),
    )
    result = predictor.predict(context)
    assert result.model_source == "baseline"
    assert set(result.probabilities.keys()) == {"1", "X", "2"}


def test_build_match_prompt_contains_teams():
    prompt = build_match_prompt("Flamengo", "Palmeiras", "Brasileirão", 10, "ctx")
    assert "Flamengo" in prompt and "Palmeiras" in prompt
    assert "rodada 10" in prompt
