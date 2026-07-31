import re
from datetime import datetime, timezone
from hashlib import sha256

from dateutil import parser as date_parser

from schemas.models import BolaoLabel, MatchResult
from schemas.teams import normalize_team

ROUND_RE = re.compile(r"^▪ (?:Matchday|Round)\s+(\d+)", re.IGNORECASE)
ROUND_GENERIC_RE = re.compile(r"^▪ .+?(?:Round|Rodada|Matchday)\s+(\d+)", re.IGNORECASE)
DATE_RE = re.compile(
    r"^\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Za-z]{3}\s+\d{1,2}\s+\d{4})"
)
DATE_NO_YEAR_RE = re.compile(
    r"^\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Za-z]{3}\s+\d{1,2})\s*$"
)
MATCH_RE = re.compile(
    r"^\s+(?:\d{2}:\d{2}\s+)?(.+?)\s+v\s+(.+?)\s+(\d+)-(\d+)(?:\s+pen\.|\s+a\.e\.t\.)?\s+\("
)


def _parse_match_date(date_str: str, season: int) -> datetime:
    dt = date_parser.parse(date_str)
    if dt.year == 1900 or len(date_str.split()) == 2:
        month = dt.month
        year = season + 1 if month <= 3 else season
        dt = dt.replace(year=year)
    return dt.replace(tzinfo=timezone.utc)


def score_to_label(home_score: int, away_score: int) -> BolaoLabel:
    if home_score > away_score:
        return "1"
    if home_score == away_score:
        return "X"
    return "2"


def _make_match_id(season: int, round_number: int, home: str, away: str, match_date: datetime) -> str:
    key = f"{season}|{round_number}|{home}|{away}|{match_date.date().isoformat()}"
    return sha256(key.encode()).hexdigest()[:16]


def parse_football_txt(
    content: str,
    season: int,
    competition: str = "Brasileirão",
    *,
    is_neutral: bool | None = None,
) -> list[MatchResult]:
    imported_at = datetime.now(timezone.utc)
    matches: list[MatchResult] = []
    current_round = 0
    current_date: datetime | None = None

    for line in content.splitlines():
        round_match = ROUND_RE.match(line) or ROUND_GENERIC_RE.match(line)
        if round_match:
            current_round = int(round_match.group(1))
            continue

        date_match = DATE_RE.match(line)
        if date_match:
            current_date = _parse_match_date(date_match.group(1), season)
            continue

        date_no_year = DATE_NO_YEAR_RE.match(line)
        if date_no_year:
            current_date = _parse_match_date(date_no_year.group(1), season)
            continue

        game = MATCH_RE.match(line)
        if not game or current_round == 0 or current_date is None:
            continue

        home_raw = " ".join(game.group(1).split())
        away_raw = " ".join(game.group(2).split())
        home_score = int(game.group(3))
        away_score = int(game.group(4))

        home_team = normalize_team(home_raw)
        away_team = normalize_team(away_raw)

        match_date = current_date
        match_id = _make_match_id(season, current_round, home_team, away_team, match_date)

        if is_neutral is None:
            neutral = competition.lower() not in (
                "brasileirão",
                "brasileirao",
                "brasileirão série b",
                "copa do brasil",
                "copa libertadores",
            )
        else:
            neutral = is_neutral

        matches.append(
            MatchResult(
                match_id=match_id,
                season=season,
                competition=competition,
                round_number=current_round,
                match_date=match_date,
                home_team=home_team,
                away_team=away_team,
                home_team_raw=home_raw,
                away_team_raw=away_raw,
                home_score=home_score,
                away_score=away_score,
                label=score_to_label(home_score, away_score),
                imported_at=imported_at,
                is_neutral=neutral,
            )
        )

    return matches
