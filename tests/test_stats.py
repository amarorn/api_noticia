from datetime import datetime, timezone

import pandas as pd

from pipelines.stats import compute_h2h, compute_standings, format_stats_context


def _make_fixtures() -> pd.DataFrame:
    rows = [
        ("2024-04-01", "Flamengo", "Palmeiras", 2, 0, 1),
        ("2024-04-08", "Palmeiras", "Flamengo", 1, 1, 1),
        ("2024-04-15", "Flamengo", "Corinthians", 3, 1, 2),
        ("2024-04-22", "Corinthians", "Flamengo", 0, 2, 2),
        ("2024-04-29", "Palmeiras", "Corinthians", 2, 0, 3),
    ]
    records = []
    for date, home, away, hs, aws, rnd in rows:
        records.append({
            "match_date": date,
            "home_team": home,
            "away_team": away,
            "home_score": hs,
            "away_score": aws,
            "round_number": rnd,
            "season": 2024,
        })
    return pd.DataFrame(records)


def test_standings():
    fixtures = _make_fixtures()
    before = datetime(2024, 5, 1, tzinfo=timezone.utc)
    table = compute_standings(fixtures, before, season=2024)
    assert table["Flamengo"].points == 10
    assert table["Flamengo"].position == 1


def test_h2h():
    fixtures = _make_fixtures()
    before = datetime(2024, 5, 1, tzinfo=timezone.utc)
    stats = compute_h2h(fixtures, "Flamengo", "Palmeiras", before, season=2024)
    assert stats is not None
    assert stats.h2h_home_wins + stats.h2h_draws + stats.h2h_away_wins == 2
    text = format_stats_context("Flamengo", "Palmeiras", stats)
    assert "Estatísticas pré-jogo" in text
    assert "Flamengo" in text
