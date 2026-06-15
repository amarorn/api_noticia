"""Testes de estatísticas ao vivo Sofascore."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from ingest.sofascore.live_stats import fetch_live_match_stats


class TestLiveStats:
    def test_fetch_xg_from_statistics(self):
        payload = {
            "statistics": [
                {
                    "period": "ALL",
                    "groups": [
                        {
                            "statisticsItems": [
                                {
                                    "key": "expectedGoals",
                                    "homeValue": "1.42",
                                    "awayValue": "0.88",
                                },
                                {
                                    "name": "Ball possession",
                                    "homeValue": "58",
                                    "awayValue": "42",
                                },
                            ]
                        }
                    ],
                }
            ]
        }
        mock_client = MagicMock()
        mock_client.event_statistics.return_value = payload

        with patch("ingest.sofascore.client.SofascoreClient", return_value=mock_client):
            stats = fetch_live_match_stats(12345)

        assert stats["home_xg"] == 1.42
        assert stats["away_xg"] == 0.88
        assert stats["home_possession_pct"] == 58.0

    def test_falha_silenciosa(self):
        with patch("ingest.sofascore.client.SofascoreClient", side_effect=RuntimeError("offline")):
            stats = fetch_live_match_stats(1)
        assert stats == {}
