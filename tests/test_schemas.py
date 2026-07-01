"""Testes dos schemas Pydantic (contratos bronze/silver/gold)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from schemas.models import BolaoFeature, BolaoLabel, BronzeArticle, GoldBolaoContext, SilverArticle


def _now() -> datetime:
    return datetime(2026, 6, 15, 12, 0, tzinfo=UTC)


def test_bronze_article_roundtrip():
    article = BronzeArticle(
        id="a1",
        source="globo_esporte",
        source_url="https://ge.globo.com/futebol/noticia.ghtml",
        title="Título",
        scraped_at=_now(),
        content_hash="abc123",
    )
    data = article.model_dump(mode="json")
    restored = BronzeArticle.model_validate(data)
    assert restored.id == "a1"
    assert str(restored.source_url).startswith("https://")


def test_silver_article_teams_default_empty():
    article = SilverArticle(
        id="s1",
        source="espn_br",
        source_url="https://www.espn.com.br/futebol",
        title="Jogo",
        body="Corpo",
        scraped_at=_now(),
        content_hash="hash",
    )
    assert article.teams_mentioned == []
    assert article.national_teams_mentioned == []


def test_bolao_feature_label_literal():
    feature = BolaoFeature(
        match_id="m1",
        home_team="Flamengo",
        away_team="Palmeiras",
        round_number=10,
        competition="brasileirao",
        match_date=_now(),
    )
    ctx = GoldBolaoContext(
        match_id="m1",
        home_team="Flamengo",
        away_team="Palmeiras",
        round_number=10,
        competition="brasileirao",
        match_date=_now(),
        context_text="ctx",
        features=feature,
        label="1",
    )
    assert ctx.label == "1"


def test_invalid_bolao_label_rejected():
    feature = BolaoFeature(
        match_id="m1",
        home_team="A",
        away_team="B",
        round_number=1,
        competition="wc",
        match_date=_now(),
    )
    with pytest.raises(ValidationError):
        GoldBolaoContext(
            match_id="m1",
            home_team="A",
            away_team="B",
            round_number=1,
            competition="wc",
            match_date=_now(),
            context_text="x",
            features=feature,
            label="3",  # type: ignore[arg-type]
        )


def test_bolao_label_type_alias():
    label: BolaoLabel = "X"
    assert label in ("1", "X", "2")
