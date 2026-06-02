from __future__ import annotations

import structlog

from schemas.teams import teams_from_text

logger = structlog.get_logger()

_DEFAULT_MODEL = "pierreguillou/ner-bert-base-cased-pt-lenerbr"
_pipeline = None
_pipeline_model: str | None = None


def _get_ner_pipeline(model_name: str):
    global _pipeline, _pipeline_model
    if _pipeline is not None and _pipeline_model == model_name:
        return _pipeline
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise ImportError(
            "NER requer pip install -e \".[ner]\" (transformers + torch)"
        ) from exc

    _pipeline = pipeline(
        "token-classification",
        model=model_name,
        aggregation_strategy="simple",
    )
    _pipeline_model = model_name
    logger.info("ner_model_loaded", model=model_name)
    return _pipeline


def extract_players(text: str, model_name: str | None = None) -> list[str]:
    if not text.strip():
        return []

    from config import settings

    if not settings.ner_enabled:
        return []

    model = model_name or settings.ner_model
    try:
        ner = _get_ner_pipeline(model)
    except ImportError:
        logger.warning("ner_unavailable", hint='pip install -e ".[ner]"')
        return []

    entities = ner(text[:4000])
    players: list[str] = []
    seen: set[str] = set()
    for ent in entities:
        label = (ent.get("entity_group") or ent.get("entity") or "").upper()
        if "PER" not in label:
            continue
        name = (ent.get("word") or "").strip()
        if len(name) < 3:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        players.append(name)
    return players


def extract_teams(text: str) -> list[str]:
    return teams_from_text(text)


def extract_entities(
    text: str,
    model_name: str | None = None,
) -> tuple[list[str], list[str]]:
    teams = extract_teams(text)
    players = extract_players(text, model_name=model_name)
    return teams, players
