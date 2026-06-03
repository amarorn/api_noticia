from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import structlog

from config import settings
from ingest.fixtures.store import load_fixtures
from pipelines.silver import load_silver
from pipelines.stats import compute_h2h, format_stats_context
from schemas.models import BolaoFeature, GoldBolaoContext
from schemas.teams import article_mentions_team

logger = structlog.get_logger()

INJURY_KEYWORDS = [
    "lesão", "lesionado", "contundido", "machucado", "desfalque", "fora",
    "cirurgia", "recuperação", "dm", "departamento médico", "indisponível",
]

NEWS_WINDOW_DAYS = 7


def _count_injury_mentions(texts: list[str]) -> int:
    count = 0
    for text in texts:
        text_lower = text.lower()
        count += sum(1 for kw in INJURY_KEYWORDS if kw in text_lower)
    return count


def _parse_datetime(value) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return pd.to_datetime(value, utc=True).to_pydatetime()


def filter_news_for_match(
    silver_df: pd.DataFrame,
    match_date: datetime,
    window_days: int = NEWS_WINDOW_DAYS,
    live_mode: bool = False,
) -> pd.DataFrame:
    if silver_df.empty or "published_at" not in silver_df.columns:
        return silver_df

    now = datetime.now(timezone.utc)
    match_dt = _parse_datetime(match_date) or now

    if live_mode or match_dt > now:
        window_start = now - timedelta(days=window_days)
        window_end = now + timedelta(days=1)
    else:
        window_start = match_dt - timedelta(days=window_days)
        window_end = match_dt

    filtered = silver_df.copy()
    filtered["_published"] = pd.to_datetime(filtered["published_at"], utc=True, errors="coerce")
    return filtered[
        (filtered["_published"] >= window_start) & (filtered["_published"] < window_end)
    ].drop(columns=["_published"])


def _collect_players(news_df: pd.DataFrame) -> list[str]:
    players: list[str] = []
    seen: set[str] = set()
    if news_df.empty or "players_mentioned" not in news_df.columns:
        return players
    for val in news_df["players_mentioned"]:
        items = val.tolist() if hasattr(val, "tolist") else (val or [])
        for name in items:
            key = str(name).strip().lower()
            if key and key not in seen:
                seen.add(key)
                players.append(str(name).strip())
    return players[:20]


def _build_players_section(home: str, away: str, home_news: pd.DataFrame, away_news: pd.DataFrame) -> list[str]:
    home_players = _collect_players(home_news)
    away_players = _collect_players(away_news)
    if not home_players and not away_players:
        return []

    lines = ["## Jogadores citados na imprensa", ""]
    if home_players:
        lines.append(f"### {home}")
        lines.extend(f"- {p}" for p in home_players)
        lines.append("")
    if away_players:
        lines.append(f"### {away}")
        lines.extend(f"- {p}" for p in away_players)
    return lines


def _build_news_section(news_df: pd.DataFrame) -> list[str]:
    lines = ["## Notícias recentes", ""]
    if news_df.empty:
        lines.append("(Sem notícias no período analisado)")
        return lines

    for _, row in news_df.head(15).iterrows():
        lines.append(f"- [{row['source']}] {row['title']}")
        if row.get("summary"):
            lines.append(f"  {str(row['summary'])[:200]}")
    return lines


def _build_context_text(
    home: str,
    away: str,
    news_df: pd.DataFrame,
    stats_text: str = "",
    home_news: pd.DataFrame | None = None,
    away_news: pd.DataFrame | None = None,
) -> str:
    lines = [f"# {home} x {away}", ""]
    if stats_text:
        lines.append(stats_text)
        lines.append("")
    if home_news is not None and away_news is not None:
        player_lines = _build_players_section(home, away, home_news, away_news)
        if player_lines:
            lines.extend(player_lines)
            lines.append("")
    lines.extend(_build_news_section(news_df))
    return "\n".join(lines)


def _apply_stats_to_features(features: BolaoFeature, stats) -> BolaoFeature:
    if stats is None:
        return features
    return features.model_copy(update={
        "home_position": stats.home.position,
        "away_position": stats.away.position,
        "home_points": stats.home.points,
        "away_points": stats.away.points,
        "home_form": stats.home.form,
        "away_form": stats.away.form,
        "home_goals_for": stats.home.goals_for,
        "home_goals_against": stats.home.goals_against,
        "away_goals_for": stats.away.goals_for,
        "away_goals_against": stats.away.goals_against,
        "h2h_home_wins": stats.h2h_home_wins,
        "h2h_draws": stats.h2h_draws,
        "h2h_away_wins": stats.h2h_away_wins,
    })


def build_gold_for_match(
    match_id: str,
    home_team: str,
    away_team: str,
    round_number: int,
    competition: str,
    match_date: datetime,
    silver_df: pd.DataFrame,
    label: str | None = None,
    home_score: int | None = None,
    away_score: int | None = None,
    season: int | None = None,
    news_window_days: int = NEWS_WINDOW_DAYS,
    fixtures_df: pd.DataFrame | None = None,
    live_mode: bool = False,
) -> GoldBolaoContext:
    news_df = filter_news_for_match(
        silver_df, match_date, window_days=news_window_days, live_mode=live_mode
    )

    home_news = news_df[news_df["teams_mentioned"].apply(lambda t: article_mentions_team(t, home_team))]
    away_news = news_df[news_df["teams_mentioned"].apply(lambda t: article_mentions_team(t, away_team))]

    home_texts = home_news["body"].tolist() if not home_news.empty else []
    away_texts = away_news["body"].tolist() if not away_news.empty else []

    relevant = pd.concat([home_news, away_news]).drop_duplicates(subset=["id"]) if not news_df.empty else news_df

    match_stats = None
    stats_text = ""
    if fixtures_df is not None and not fixtures_df.empty:
        match_stats = compute_h2h(
            fixtures_df, home_team, away_team, match_date, season=season
        )
        if match_stats:
            stats_text = format_stats_context(home_team, away_team, match_stats)

    features = BolaoFeature(
        match_id=match_id,
        home_team=home_team,
        away_team=away_team,
        round_number=round_number,
        competition=competition,
        match_date=match_date,
        news_count_home=len(home_news),
        news_count_away=len(away_news),
        injury_mentions_home=_count_injury_mentions(home_texts),
        injury_mentions_away=_count_injury_mentions(away_texts),
        sentiment_home=float(home_news["sentiment_score"].mean()) if not home_news.empty else None,
        sentiment_away=float(away_news["sentiment_score"].mean()) if not away_news.empty else None,
        headline_keywords=relevant["title"].tolist()[:10] if not relevant.empty else [],
    )
    features = _apply_stats_to_features(features, match_stats)

    return GoldBolaoContext(
        match_id=match_id,
        home_team=home_team,
        away_team=away_team,
        round_number=round_number,
        competition=competition,
        match_date=match_date,
        context_text=_build_context_text(
            home_team, away_team, relevant, stats_text,
            home_news=home_news, away_news=away_news,
        ),
        features=features,
        label=label,
        home_score=home_score,
        away_score=away_score,
        season=season,
    )


def save_gold(contexts: list[GoldBolaoContext], suffix: str = "bolao_context") -> Path | None:
    if not contexts:
        return None

    settings.gold_path.mkdir(parents=True, exist_ok=True)
    records = [c.model_dump(mode="json") for c in contexts]
    df = pd.DataFrame(records)

    dt = datetime.now(timezone.utc)
    out_path = (
        settings.gold_path
        / f"year={dt.year}"
        / f"month={dt.month:02d}"
        / f"{suffix}_{dt.strftime('%H%M%S')}.parquet"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    logger.info("gold_saved", path=str(out_path), rows=len(df))
    return out_path


def fixtures_to_match_dicts(
    fixtures_df: pd.DataFrame,
    round_number: int | None = None,
    season: int | None = None,
) -> list[dict]:
    df = fixtures_df.copy()
    if season is not None:
        df = df[df["season"] == season]
    if round_number is not None:
        df = df[df["round_number"] == round_number]

    matches = []
    for _, row in df.iterrows():
        matches.append({
            "match_id": row["match_id"],
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "round_number": int(row["round_number"]),
            "competition": row["competition"],
            "match_date": _parse_datetime(row["match_date"]),
            "label": row["label"],
            "home_score": int(row["home_score"]),
            "away_score": int(row["away_score"]),
            "season": int(row["season"]),
        })
    return matches


def run_gold_pipeline(
    matches: list[dict] | None = None,
    season: int | None = None,
    round_number: int | None = None,
    use_fixtures: bool = True,
) -> Path | None:
    silver_df = load_silver()
    all_fixtures = load_fixtures()

    if matches is None and use_fixtures:
        if all_fixtures.empty:
            logger.warning("no_fixtures_data", hint="Execute: import-brasileirao")
            return None
        matches = fixtures_to_match_dicts(all_fixtures, round_number=round_number, season=season)
    elif matches is None:
        matches = [{
            "match_id": "demo_001",
            "home_team": "Flamengo",
            "away_team": "Palmeiras",
            "round_number": 1,
            "competition": "Brasileirão",
            "match_date": datetime.now(timezone.utc),
        }]

    contexts = [
        build_gold_for_match(
            match_id=m["match_id"],
            home_team=m["home_team"],
            away_team=m["away_team"],
            round_number=m["round_number"],
            competition=m["competition"],
            match_date=m["match_date"],
            silver_df=silver_df,
            label=m.get("label"),
            home_score=m.get("home_score"),
            away_score=m.get("away_score"),
            season=m.get("season"),
            fixtures_df=all_fixtures if not all_fixtures.empty else None,
        )
        for m in matches
    ]
    suffix = f"brasileirao_{season}" if season else "bolao_context"
    return save_gold(contexts, suffix=suffix)
