import re
from datetime import datetime, timezone
from hashlib import sha256

from dateutil import parser as date_parser

from ingest.fixtures.parser import score_to_label
from schemas.models import BolaoLabel, MatchResult
from schemas.national_teams import normalize_national_team

GROUP_RE = re.compile(r"^▪\s+Group\s+([A-H]|[1-9]\d*)\s*(?:\|.*)?$", re.IGNORECASE)
PHASE_RE = re.compile(
    r"^▪\s+(Round of 16|Quarter-finals|Semi-finals|Match for third place|Final)"
    r"(?:\s*\|.*)?\s*$",
    re.IGNORECASE,
)
MATCHDAY_RE = re.compile(r"^▪\s+Matchday", re.IGNORECASE)

# Sun Nov 20 | Fri Jun 9 | June 18
DATE_WITH_DOW_RE = re.compile(
    r"^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Za-z]{3,9}\s+\d{1,2}(?:\s+\d{4})?)\s*$",
    re.IGNORECASE,
)
# 10 June | 31 May
DATE_DAY_FIRST_RE = re.compile(r"^(\d{1,2}\s+[A-Za-z]{3,9}(?:\s+\d{4})?)\s*$", re.IGNORECASE)
# June 18
DATE_MONTH_FIRST_RE = re.compile(r"^([A-Za-z]{3,9}\s+\d{1,2}(?:\s+\d{4})?)\s*$", re.IGNORECASE)

INLINE_DATE_RE = re.compile(
    r"^\s*"
    r"(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+)?"
    r"(?:"
    r"(?P<dmy>\d{1,2}\s+[A-Za-z]{3,9})"
    r"|"
    r"(?P<mdy>[A-Za-z]{3,9}\s+\d{1,2})"
    r")"
    r"(?:\s+\d{4})?"
    r"(?:\s+(?P<rest>.+))?$",
    re.IGNORECASE,
)

MATCH_RE = re.compile(
    r"^\s*(?:\d{2}:\d{2}\s+)?"
    r"(?P<home>.+?)\s+"
    r"(?P<hs>\d+)-(?P<as>\d+)"
    r"(?:\s+a\.e\.t\.?(?:\s*\([^)]+\))?)?"
    r"(?:\s*\([^)]+\))?"
    r"(?:,\s*(?P<ph>\d+)-(?P<pa>\d+)\s+pen\.)?"
    r"\s+(?P<away>.+?)\s*@",
    re.UNICODE,
)

PHASE_MAP = {
    "round of 16": "round_16",
    "quarter-finals": "quarter",
    "semi-finals": "semi",
    "match for third place": "third_place",
    "final": "final",
}


def _parse_wc_date(date_str: str, season: int) -> datetime:
    dt = date_parser.parse(date_str, dayfirst=True)
    # Quando o texto não traz ano explícito (ex: "Nov 24"), dateutil assume
    # o ano corrente. Para Copa, o ano correto é sempre o da edição.
    if not re.search(r"\b\d{4}\b", date_str):
        dt = dt.replace(year=season)
    return dt.replace(tzinfo=timezone.utc)


def _parse_standalone_date(stripped: str, season: int) -> datetime | None:
    for pattern in (DATE_WITH_DOW_RE, DATE_DAY_FIRST_RE, DATE_MONTH_FIRST_RE):
        m = pattern.match(stripped)
        if m:
            return _parse_wc_date(m.group(1), season)
    return None


def _split_inline_date(stripped: str, season: int) -> tuple[datetime | None, str | None]:
    m = INLINE_DATE_RE.match(stripped)
    if not m:
        return None, None

    date_str = m.group("dmy") or m.group("mdy")
    if not date_str:
        return None, None

    match_date = _parse_wc_date(date_str, season)
    rest = m.group("rest")
    if rest and rest.strip():
        return match_date, rest.strip()
    return match_date, None


def _resolve_label(home_score: int, away_score: int, pen_home: int | None, pen_away: int | None) -> BolaoLabel:
    if pen_home is not None and pen_away is not None:
        return "1" if pen_home > pen_away else "2"
    return score_to_label(home_score, away_score)


def _make_match_id(season: int, phase: str, home: str, away: str, match_date: datetime) -> str:
    key = f"wc|{season}|{phase}|{home}|{away}|{match_date.date().isoformat()}"
    return sha256(key.encode()).hexdigest()[:16]


def _parse_match_line(line: str) -> tuple[str, str, int, int, BolaoLabel] | None:
    if not line.strip() or line.strip().startswith("("):
        return None
    if "@" not in line:
        return None

    match = MATCH_RE.match(line)
    if not match:
        return None

    home_raw = " ".join(match.group("home").split())
    away_raw = " ".join(match.group("away").split())
    home_score = int(match.group("hs"))
    away_score = int(match.group("as"))
    pen_home = int(match.group("ph")) if match.group("ph") else None
    pen_away = int(match.group("pa")) if match.group("pa") else None
    label = _resolve_label(home_score, away_score, pen_home, pen_away)
    return home_raw, away_raw, home_score, away_score, label


def _append_match(
    matches: list[MatchResult],
    *,
    season: int,
    current_phase: str,
    current_group: str | None,
    round_counter: int,
    current_date: datetime,
    home_raw: str,
    away_raw: str,
    home_score: int,
    away_score: int,
    label: BolaoLabel,
    imported_at: datetime,
) -> None:
    home_team = normalize_national_team(home_raw)
    away_team = normalize_national_team(away_raw)
    match_id = _make_match_id(season, current_phase, home_team, away_team, current_date)

    matches.append(
        MatchResult(
            match_id=match_id,
            season=season,
            competition="Copa do Mundo",
            round_number=round_counter,
            match_date=current_date,
            home_team=home_team,
            away_team=away_team,
            home_team_raw=home_raw,
            away_team_raw=away_raw,
            home_score=home_score,
            away_score=away_score,
            label=label,
            imported_at=imported_at,
            phase=current_phase,
            group_name=current_group,
            is_neutral=True,
        )
    )


def parse_world_cup_txt(
    content: str,
    season: int,
    default_phase: str = "group",
) -> list[MatchResult]:
    imported_at = datetime.now(timezone.utc)
    matches: list[MatchResult] = []
    current_phase = default_phase
    current_group: str | None = None
    current_date: datetime | None = None
    round_counter = 0

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped or stripped.startswith("=") or stripped.startswith("#"):
            continue
        if stripped.startswith("Group ") and "|" in stripped:
            continue
        if MATCHDAY_RE.match(stripped):
            continue

        group_match = GROUP_RE.match(stripped)
        if group_match:
            current_phase = "group"
            current_group = group_match.group(1).upper()
            continue

        phase_match = PHASE_RE.match(stripped)
        if phase_match:
            phase_name = phase_match.group(1).lower()
            current_phase = PHASE_MAP.get(phase_name, default_phase)
            current_group = None
            round_counter += 1
            continue

        inline_date, rest = _split_inline_date(stripped, season)
        if inline_date and rest:
            current_date = inline_date
            parsed = _parse_match_line(rest)
            if parsed:
                home_raw, away_raw, home_score, away_score, label = parsed
                _append_match(
                    matches,
                    season=season,
                    current_phase=current_phase,
                    current_group=current_group,
                    round_counter=round_counter,
                    current_date=current_date,
                    home_raw=home_raw,
                    away_raw=away_raw,
                    home_score=home_score,
                    away_score=away_score,
                    label=label,
                    imported_at=imported_at,
                )
            continue

        if inline_date and not rest:
            current_date = inline_date
            continue

        standalone = _parse_standalone_date(stripped, season)
        if standalone:
            current_date = standalone
            continue

        parsed = _parse_match_line(line)
        if not parsed or current_date is None:
            continue

        home_raw, away_raw, home_score, away_score, label = parsed
        _append_match(
            matches,
            season=season,
            current_phase=current_phase,
            current_group=current_group,
            round_counter=round_counter,
            current_date=current_date,
            home_raw=home_raw,
            away_raw=away_raw,
            home_score=home_score,
            away_score=away_score,
            label=label,
            imported_at=imported_at,
        )

    return matches
