import json
from unittest.mock import patch

import pandas as pd
import pytest

from models.wc_artifact import (
    ARTIFACT_VERSION,
    artifact_is_valid,
    read_manifest,
    save_artifact,
)
from models.wc_predictor import train_wc_predictor


@pytest.fixture
def tiny_fixtures() -> pd.DataFrame:
    rows = []
    labels = ("1", "X", "2")
    for season in (2010, 2014, 2018, 2022):
        for i in range(20):
            day = (i % 20) + 1
            label = labels[i % 3]
            hs, aws = (2, 1) if label == "1" else ((1, 1) if label == "X" else (0, 2))
            rows.append(
                {
                    "season": season,
                    "match_date": f"{season}-06-{day:02d}",
                    "home_team": "Brasil",
                    "away_team": "Alemanha",
                    "home_score": hs,
                    "away_score": aws,
                    "label": label,
                    "phase": "group",
                    "is_neutral": True,
                }
            )
    return pd.DataFrame(rows)


def test_save_and_load_artifact_roundtrip(tmp_path, tiny_fixtures):
    with (
        patch("models.wc_artifact.settings") as mock_settings,
        patch("models.wc_artifact.fixtures_fingerprint", return_value="fp-test"),
        patch("models.wc_artifact.squads_fingerprint", return_value="sq-test"),
        patch("ingest.fixtures.world_cup.load_wc_fixtures", return_value=tiny_fixtures),
    ):
        mock_settings.wc_artifact_dir = tmp_path / "artifacts"
        mock_settings.fixtures_path = tmp_path / "fixtures"
        mock_settings.wc_squads_path = tmp_path / "squads.json"

        predictor = train_wc_predictor(tiny_fixtures, validation_season=2022)
        manifest = save_artifact(predictor)

        assert manifest["artifact_version"] == ARTIFACT_VERSION
        loaded_manifest = read_manifest()
        assert artifact_is_valid(loaded_manifest)

        from models.wc_artifact import load_artifact

        loaded = load_artifact()
        assert loaded is not None
        assert loaded.logistic._fitted
        assert loaded.collaborative.metrics is not None


def test_artifact_invalid_when_fingerprint_changes(tmp_path, tiny_fixtures):
    with (
        patch("models.wc_artifact.settings") as mock_settings,
        patch("models.wc_artifact.fixtures_fingerprint", return_value="fp-test"),
        patch("models.wc_artifact.squads_fingerprint", return_value="sq-test"),
    ):
        mock_settings.wc_artifact_dir = tmp_path / "artifacts"

        predictor = train_wc_predictor(tiny_fixtures, validation_season=2022)
        save_artifact(predictor)

        manifest_path = tmp_path / "artifacts" / "manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        data["fixtures_fingerprint"] = "stale"
        manifest_path.write_text(json.dumps(data), encoding="utf-8")

        assert artifact_is_valid() is False
