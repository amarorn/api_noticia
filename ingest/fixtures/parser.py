import re
import zoneinfo
from datetime import datetime, timezone
from hashlib import sha256

from dateutil import parser as date_parser

from schemas.models import BolaoLabel, MatchResult
from schemas.teams import normalize_team

BR_TZ = zoneinfo.ZoneInfo("America/Sao_Paulo")

ROUND_RE = re.compile(r"^▪ (?:Matchday|Round)\s+(\d+)", re.IGNORECASE)
ROUND_GENERIC_RE = re.compile(r"^▪ .+?(?:Round|Rodada|Matchday)\s+(\d+)", re.IGNORECASE)
DATE_RE = re.compile(
    r"^\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Za-z]{3}\s+\d{1,2}\s+\d{4})"
)
DATE_NO_YEAR_RE = re.compile(
    r"^\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Za-z]{3}\s+\d{1,2})\s*$"
)
# Linha com horário opcional; placar opcional (jogos futuros no openfootball).
MATCH_LINE_RE = re.compile(
    r"^\s+(?:(\d{2}:\d{2})\s+)?(.+?)\s+v\s+(.+?)"
    r"(?:\s+(\d+)-(\d+)(?:\s+pen\.|\s+a\.e\.t\.)?(?:\s+\([^)]+\))?)?\s*$"
)
CONT_LINE_RE = re.compile(
    r"^\s{11,}(.+?)\s+v\s+(.+?)"
    r"(?:\s+(\d+)-(\d+)(?:\s+pen\.|\s+a\.e\.t\.)?(?:\s+\([^)]+\))?)?\s*$"
)


def _parse_match_date(date_str: str, season: int) -> datetime:
    dt = date_parser.parse(date_str)
    if dt.year == 1900 or len(date_str.split()) == 2:
        month = dt.month
        year = season + 1 if month <= 3 else season
        dt = dt.replace(year=year)
    return dt.replace(tzinfo=timezone.utc)


def _kickoff_utc(date_str: str, season: int, time_str: str | None) -> datetime:
    """Combina data openfootball + hora local (Brasília) → UTC."""
    dt = date_parser.parse(date_str)
    if dt.year == 1900 or len(date_str.split()) == 2:
        month = dt.month
        year = season + 1 if month <= 3 else season
        dt = dt.replace(year=year)
    if time_str:
        hour, minute = map(int, time_str.split(":"))
        local = datetime(dt.year, dt.month, dt.day, hour, minute, tzinfo=BR_TZ)
        return local.astimezone(timezone.utc)
    local = datetime(dt.year, dt.month, dt.day, tzinfo=BR_TZ)
    return local.astimezone(timezone.utc)


def score_to_label(home_score: int, away_score: int) -> BolaoLabel:
    if home_score > away_score:
        return "1"
    if home_score == away_score:
        return "X"
    return "2"


def _make_match_id(
    season: int,
    round_number: int,
    home: str,
    away: str,
    match_date: datetime,
) -> str:
    key = f"{season}|{round_number}|{home}|{away}|{match_date.isoformat()}"
    return sha256(key.encode()).hexdigest()[:16]


def _parse_match_line(
    line: str,
    *,
    last_time: str | None,
) -> tuple[str | None, str, str, int | None, int | None] | None:
    """Retorna (time, home_raw, away_raw, home_score, away_score) ou None."""
    game = MATCH_LINE_RE.match(line)
    if game:
        time_str = game.group(1) or last_time
        home_raw = " ".join(game.group(2).split())
        away_raw = " ".join(game.group(3).split())
        hs = int(game.group(4)) if game.group(4) is not None else None
        aws = int(game.group(5)) if game.group(5) is not None else None
        return time_str, home_raw, away_raw, hs, aws

    cont = CONT_LINE_RE.match(line)
    if cont and last_time:
        home_raw = " ".join(cont.group(1).split())
        away_raw = " ".join(cont.group(2).split())
        hs = int(cont.group(3)) if cont.group(3) is not None else None
        aws = int(cont.group(4)) if cont.group(4) is not None else None
        return last_time, home_raw, away_raw, hs, aws
    return None


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
    current_date_str: str | None = None
    last_time: str | None = None

    for line in content.splitlines():
        round_match = ROUND_RE.match(line) or ROUND_GENERIC_RE.match(line)
        if round_match:
            current_round = int(round_match.group(1))
            last_time = None
            continue

        date_match = DATE_RE.match(line)
        if date_match:
            current_date_str = date_match.group(1)
            last_time = None
            continue

        date_no_year = DATE_NO_YEAR_RE.match(line)
        if date_no_year:
            current_date_str = date_no_year.group(1)
            last_time = None
            continue

        if current_round == 0 or current_date_str is None:
            continue

        parsed = _parse_match_line(line, last_time=last_time)
        if not parsed:
            continue

        time_str, home_raw, away_raw, home_score, away_score = parsed
        line_match = MATCH_LINE_RE.match(line)
        if line_match and line_match.group(1):
            last_time = line_match.group(1)

        home_team = normalize_team(home_raw)
        away_team = normalize_team(away_raw)
        match_date = _kickoff_utc(current_date_str, season, time_str)
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

        label: BolaoLabel | None = None
        if home_score is not None and away_score is not None:
            label = score_to_label(home_score, away_score)

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
                label=label,
                imported_at=imported_at,
                is_neutral=neutral,
            )
        )

    return matches
