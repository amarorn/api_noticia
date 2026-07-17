"""Sincroniza o calendário da fase eliminatória (mata-mata) WC 2026 → ``data/rounds/wc_2026.json``.

Fontes (nessa ordem):
1. Janela oficial FIFA (``FifaClient.match_window_matches``)
2. Supplement por IdMatch conhecidos (32 avos → semis) via ``match_details``
3. Fallback Sofascore (``team_upcoming_events`` das seleções ainda no bracket)

A janela FIFA é limitada; IDs fixos e Sofascore cobrem confrontos já definidos
mas fora da janela rolante (ex.: 2ª semifinal).

CLI: ``sync-wc-knockout-schedule``
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from ingest.fifa.client import FifaClient, FifaClientError
from ingest.fifa.match_ingest import load_fifa_window_matches
from pipelines.sync_wc_group_results import load_round_file, save_round_file
from schemas.national_teams import normalize_national_team

logger = structlog.get_logger()

ROUND_FILE = Path("data/rounds/wc_2026.json")

# IDs FIFA WC 2026 mata-mata conhecidos: 32 avos (512–527) até 2ª semi (540).
# A janela rolante nem sempre devolve todos — ex.: Inglaterra×Argentina (540).
_WC_2026_KNOWN_KO_IDS = tuple(range(400021512, 400021542))

# Placeholders Sofascore/FIFA enquanto o confronto não tem seleções reais.
_PLACEHOLDER_TEAM_RE = re.compile(
    r"^(?:[WL]\d+|tbd|winner(?:\s+of)?.*|loser(?:\s+of)?.*|to\s+be\s+defined)$",
    re.IGNORECASE,
)

_SOFA_WC_SLUG_TOKENS = ("world-cup", "world-championship")

# Mapa nome do estágio (PT/EN, FIFA ou Sofascore) → (phase slug, round sequencial).
_STAGE_PHASE_MAP: dict[str, tuple[str, int]] = {
    "Segundas de final": ("round_of_32", 4),
    "Round of 32": ("round_of_32", 4),
    "Oitavas de final": ("round_of_16", 5),
    "Round of 16": ("round_of_16", 5),
    "Quartas de final": ("quarterfinal", 6),
    "Quarter-finals": ("quarterfinal", 6),
    "Quarter-final": ("quarterfinal", 6),
    "Semifinais": ("semifinal", 7),
    "Semifinal": ("semifinal", 7),
    "Semifinals": ("semifinal", 7),
    "Semi-final": ("semifinal", 7),
    "Semi-finals": ("semifinal", 7),
    "Disputa de 3º lugar": ("third_place", 8),
    "Play-off for third place": ("third_place", 8),
    "Match for 3rd place": ("third_place", 8),
    "3rd place": ("third_place", 8),
    "Final": ("final", 9),
}


def _slug_part(name: str) -> str:
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")
    return n[:16] or "team"


def _phase_for_stage(stage_name: str) -> tuple[str, int]:
    if stage_name in _STAGE_PHASE_MAP:
        return _STAGE_PHASE_MAP[stage_name]
    logger.warning("wc_knockout_stage_desconhecido", stage_name=stage_name)
    return (_slug_part(stage_name) or "knockout", 99)


def _is_wc_2026_match(season_names: str) -> bool:
    low = season_names.lower()
    return "2026" in low and ("world cup" in low or "copa do mundo" in low)


def _is_placeholder_team(name: str) -> bool:
    cleaned = (name or "").strip()
    if not cleaned:
        return True
    return bool(_PLACEHOLDER_TEAM_RE.match(cleaned))


def _localized_label(items: list[dict[str, Any]] | None, *, prefer_pt: bool = True) -> str:
    if not items:
        return ""
    if prefer_pt:
        for item in items:
            if str(item.get("Locale", "")).lower().startswith("pt"):
                return str(item.get("Description", ""))
    return str(items[0].get("Description", ""))


def _team_name(side: dict[str, Any]) -> str:
    names = side.get("TeamName") or []
    for n in names:
        if str(n.get("Locale", "")).lower().startswith("pt"):
            return normalize_national_team(n.get("Description", ""))
    if names:
        return normalize_national_team(names[0].get("Description", ""))
    return ""


def _venue_city(m: dict[str, Any]) -> tuple[str | None, str | None]:
    stadium = m.get("Stadium")
    if isinstance(stadium, dict):
        return (
            _localized_label(stadium.get("Name"), prefer_pt=False) or None,
            _localized_label(stadium.get("CityName"), prefer_pt=False) or None,
        )
    if isinstance(stadium, str):
        return stadium, None
    return None, None


def _iter_window_matches(data: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normaliza a resposta da FIFA (dict com blocos por time) ou cache flattened (lista)."""
    if isinstance(data, list):
        return data
    matches = data.get("matches") or {}
    if isinstance(matches, list):
        return matches
    out: list[dict[str, Any]] = []
    for block in matches.values():
        for m in block.get("MatchesList", []):
            out.append(m)
    return out


def _match_id(match: dict[str, Any]) -> str:
    return str(match.get("IdMatch") or "")


def _parse_knockout_match(m: dict[str, Any]) -> dict[str, Any] | None:
    season_names = " ".join(
        s.get("Description", "") for s in (m.get("SeasonName") or [])
    )
    if not _is_wc_2026_match(season_names):
        return None
    stage_name = _localized_label(m.get("StageName"))
    if stage_name in {"Primeira fase", "Group Stage"}:
        return None  # fase de grupos já vem do build_wc_2026_schedule.py
    if stage_name in {"Repescagem", "Play-offs", "Play-Offs"}:
        return None

    home = _team_name(m.get("Home") or m.get("HomeTeam") or {})
    away = _team_name(m.get("Away") or m.get("AwayTeam") or {})
    if not home or not away or _is_placeholder_team(home) or _is_placeholder_team(away):
        return None

    phase, round_no = _phase_for_stage(stage_name)
    id_match = _match_id(m)
    kickoff = m.get("Date")  # já vem em ISO UTC (ex.: 2026-06-29T17:00:00+00:00)
    venue, city = _venue_city(m)

    return {
        "id": f"{phase}-{_slug_part(home)}-{_slug_part(away)}",
        "home_team": home,
        "away_team": away,
        "group": None,
        "round": round_no,
        "phase": phase,
        "kickoff": kickoff,
        "venue": venue,
        "city": city,
        "fifa_stage": stage_name,
        "fifa_id_match": id_match or None,
    }


def _dup_key(match: dict[str, Any]) -> tuple[str, str, str]:
    return (
        normalize_national_team(str(match.get("home_team") or "")),
        normalize_national_team(str(match.get("away_team") or "")),
        str(match.get("kickoff") or ""),
    )


def _pair_only_key(match: dict[str, Any]) -> tuple[str, str]:
    return (
        normalize_national_team(str(match.get("home_team") or "")),
        normalize_national_team(str(match.get("away_team") or "")),
    )


def _append_unique(
    out: list[dict[str, Any]],
    *,
    seen_ids: set[str],
    seen_pairs: set[tuple[str, str]],
    parsed: dict[str, Any],
) -> bool:
    """Adiciona confronto se ainda não estiver em out (por FIFA id ou par de times)."""
    id_match = parsed.get("fifa_id_match")
    if id_match and id_match in seen_ids:
        return False
    pair = _pair_only_key(parsed)
    # Ignora ordem de mandante invertida (mesmo confronto).
    if pair in seen_pairs or (pair[1], pair[0]) in seen_pairs:
        return False
    if _dup_key(parsed) in {_dup_key(o) for o in out}:
        return False
    out.append(parsed)
    if id_match:
        seen_ids.add(str(id_match))
    seen_pairs.add(pair)
    return True


def _supplement_knockout_by_known_ids(
    client: FifaClient,
    *,
    seen_ids: set[str],
    seen_pairs: set[tuple[str, str]],
    out: list[dict[str, Any]],
) -> int:
    """Busca por IdMatch os KO que a janela rolante ainda não devolveu."""
    added = 0
    for match_id in _WC_2026_KNOWN_KO_IDS:
        id_str = str(match_id)
        if id_str in seen_ids:
            continue
        try:
            details = client.match_details(id_str)
        except Exception as exc:
            logger.debug("wc_knockout_id_fetch_skip", match_id=id_str, error=str(exc))
            continue
        if not isinstance(details, dict):
            continue
        parsed = _parse_knockout_match(details)
        if parsed is None:
            continue
        if _append_unique(out, seen_ids=seen_ids, seen_pairs=seen_pairs, parsed=parsed):
            added += 1
    if added:
        logger.info("wc_knockout_supplemented_by_id", added=added)
    return added


def _is_sofascore_wc_knockout(event: dict[str, Any]) -> bool:
    tournament = event.get("tournament") or event.get("uniqueTournament") or {}
    slug = str(tournament.get("slug") or "").lower()
    name = str(tournament.get("name") or "").lower()
    blob = f"{slug} {name}"
    if not any(token in blob for token in _SOFA_WC_SLUG_TOKENS):
        return False
    if "qual" in slug or "qualification" in name:
        return False
    return True


def _sofascore_stage_name(event: dict[str, Any]) -> str:
    round_info = event.get("roundInfo") or {}
    for key in ("name", "round"):
        raw = round_info.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        if isinstance(raw, (int, float)):
            continue
    tournament = event.get("tournament") or {}
    return str(tournament.get("name") or "Knockout").strip()


def _parse_sofascore_knockout_event(
    event: dict[str, Any],
    *,
    team_map: dict[str, dict],
) -> dict[str, Any] | None:
    """Converte evento Sofascore da fase KO em linha do calendário WC."""
    from ingest.sofascore.event_helpers import (
        canonical_from_event_team,
        match_date_from_event,
    )

    if not _is_sofascore_wc_knockout(event):
        return None

    home_raw = event.get("homeTeam") or {}
    away_raw = event.get("awayTeam") or {}
    home_name = str(home_raw.get("name") or "")
    away_name = str(away_raw.get("name") or "")
    if _is_placeholder_team(home_name) or _is_placeholder_team(away_name):
        return None

    home = canonical_from_event_team(home_raw, team_map)
    away = canonical_from_event_team(away_raw, team_map)
    if not home or not away or _is_placeholder_team(home) or _is_placeholder_team(away):
        return None

    stage_name = _sofascore_stage_name(event)
    phase, round_no = _phase_for_stage(stage_name)
    kickoff = match_date_from_event(event)
    event_id = event.get("id")

    return {
        "id": f"{phase}-{_slug_part(home)}-{_slug_part(away)}",
        "home_team": home,
        "away_team": away,
        "group": None,
        "round": round_no,
        "phase": phase,
        "kickoff": kickoff,
        "venue": None,
        "city": None,
        "fifa_stage": stage_name,
        "fifa_id_match": None,
        "sofascore_event_id": int(event_id) if event_id is not None else None,
        "schedule_source": "sofascore",
    }


def _candidate_teams_for_sofascore(out: list[dict[str, Any]]) -> list[str]:
    """Seleções a consultar: quartas/semis/final já no payload FIFA."""
    teams: set[str] = set()
    late_phases = {"quarterfinal", "semifinal", "third_place", "final"}
    for match in out:
        if str(match.get("phase") or "") not in late_phases:
            continue
        for key in ("home_team", "away_team"):
            name = normalize_national_team(str(match.get(key) or ""))
            if name and not _is_placeholder_team(name):
                teams.add(name)
    return sorted(teams)


def _supplement_from_sofascore(
    *,
    seen_ids: set[str],
    seen_pairs: set[tuple[str, str]],
    out: list[dict[str, Any]],
) -> int:
    """Completa confrontos KO via Sofascore (próximos jogos das seleções no bracket)."""
    try:
        from ingest.sofascore.client import SofascoreClient
        from ingest.sofascore.teams import load_team_map, resolve_team_id
    except Exception as exc:
        logger.warning("wc_knockout_sofascore_import_skip", error=str(exc))
        return 0

    teams = _candidate_teams_for_sofascore(out)
    if not teams:
        # Seed mínimo: se a FIFA só trouxe 1 semi, ainda assim tentar finalistas de QF.
        for match in out:
            if match.get("phase") == "quarterfinal":
                for key in ("home_team", "away_team"):
                    name = normalize_national_team(str(match.get(key) or ""))
                    if name:
                        teams.append(name)
        teams = sorted(set(teams))

    if not teams:
        return 0

    client = SofascoreClient()
    team_map = load_team_map()
    added = 0
    seen_event_ids: set[int] = set()

    for team in teams:
        try:
            team_id, _ = resolve_team_id(team, team_map=team_map, client=client)
        except Exception as exc:
            logger.debug("wc_knockout_sofa_team_skip", team=team, error=str(exc))
            continue
        try:
            events = client.team_upcoming_events(team_id)
        except Exception as exc:
            logger.warning("wc_knockout_sofa_upcoming_fail", team=team, error=str(exc))
            continue

        for event in events:
            event_id = event.get("id")
            if event_id is not None:
                eid = int(event_id)
                if eid in seen_event_ids:
                    continue
                seen_event_ids.add(eid)
            parsed = _parse_sofascore_knockout_event(event, team_map=team_map)
            if parsed is None:
                continue
            if _append_unique(out, seen_ids=seen_ids, seen_pairs=seen_pairs, parsed=parsed):
                added += 1

    if added:
        logger.info("wc_knockout_supplemented_sofascore", added=added, teams=len(teams))
    return added


def fetch_knockout_matches(
    client: FifaClient | None = None,
    *,
    use_sofascore: bool = True,
) -> list[dict[str, Any]]:
    """Busca jogos do mata-mata da Copa 2026 (FIFA + IDs + Sofascore opcional).

    Se a API FIFA falhar (offline/DNS), usa o cache local ``window_matches.json``.
    """
    fifa_client = client or FifaClient()
    raw_matches: list[dict[str, Any]] = []
    source = "api"
    try:
        data = fifa_client.match_window_matches(locale="pt")
        raw_matches = _iter_window_matches(data)
    except (FifaClientError, Exception) as exc:
        logger.warning(
            "wc_knockout_api_failed_using_cache_fallback",
            error=str(exc),
        )
        cached = load_fifa_window_matches(force_refresh=False)
        raw_matches = cached
        source = "cache"

    seen_ids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for m in raw_matches:
        parsed = _parse_knockout_match(m)
        if parsed is None:
            continue
        _append_unique(out, seen_ids=seen_ids, seen_pairs=seen_pairs, parsed=parsed)

    _supplement_knockout_by_known_ids(
        fifa_client, seen_ids=seen_ids, seen_pairs=seen_pairs, out=out
    )

    if use_sofascore:
        _supplement_from_sofascore(seen_ids=seen_ids, seen_pairs=seen_pairs, out=out)

    logger.info("wc_knockout_matches_fetched", source=source, count=len(out))
    return out


def _pair_key(match: dict[str, Any]) -> tuple[str, str, str]:
    return _dup_key(match)


def merge_knockout_matches(
    round_data: dict[str, Any],
    knockout_matches: list[dict[str, Any]],
) -> tuple[dict[str, Any], int, int]:
    """Mescla jogos do mata-mata no round_data (por id ou par normalizado + horário)."""
    matches: list[dict[str, Any]] = round_data.setdefault("matches", [])
    by_id = {m.get("id"): idx for idx, m in enumerate(matches)}
    by_pair = {_pair_key(m): idx for idx, m in enumerate(matches)}
    by_pair_only = {_pair_only_key(m): idx for idx, m in enumerate(matches)}

    added = 0
    updated = 0
    for km in knockout_matches:
        idx = by_id.get(km["id"])
        if idx is None:
            idx = by_pair.get(_pair_key(km))
        if idx is None:
            # Mesmo confronto com kickoff levemente diferente (FIFA vs Sofascore).
            idx = by_pair_only.get(_pair_only_key(km))
            if idx is None:
                rev = (_pair_only_key(km)[1], _pair_only_key(km)[0])
                idx = by_pair_only.get(rev)
        if idx is None:
            matches.append(km)
            by_id[km["id"]] = len(matches) - 1
            by_pair[_pair_key(km)] = len(matches) - 1
            by_pair_only[_pair_only_key(km)] = len(matches) - 1
            added += 1
        else:
            existing = matches[idx]
            km_merged = {**existing, **km}
            for score_key in ("home_score", "away_score", "result_source", "result_synced_at"):
                if score_key in existing:
                    km_merged[score_key] = existing[score_key]
            # Prefere fifa_id_match já existente se a fonte nova for Sofascore.
            if existing.get("fifa_id_match") and not km.get("fifa_id_match"):
                km_merged["fifa_id_match"] = existing["fifa_id_match"]
            matches[idx] = km_merged
            by_id[km_merged["id"]] = idx
            by_pair[_pair_key(km_merged)] = idx
            by_pair_only[_pair_only_key(km_merged)] = idx
            updated += 1

    round_data["matches"] = matches
    return round_data, added, updated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sincroniza calendário do mata-mata WC 2026 (FIFA + Sofascore)"
    )
    parser.add_argument(
        "--round-file", default=str(ROUND_FILE), help=f"Padrão: {ROUND_FILE}"
    )
    parser.add_argument("--no-backup", action="store_true", help="Não cria .bak antes de gravar")
    parser.add_argument("--dry-run", action="store_true", help="Só mostra o que seria feito")
    parser.add_argument(
        "--skip-sofascore",
        action="store_true",
        help="Não consulta Sofascore (somente FIFA + IDs)",
    )
    args = parser.parse_args()

    round_path = Path(args.round_file)
    try:
        round_data = load_round_file(round_path)
    except FileNotFoundError as exc:
        print(f"Erro: {exc}")
        return 1

    try:
        knockout_matches = fetch_knockout_matches(use_sofascore=not args.skip_sofascore)
    except FifaClientError as exc:
        print(f"Erro ao consultar API FIFA: {exc}")
        return 1

    if not knockout_matches:
        print("Nenhum jogo do mata-mata encontrado na janela atual da FIFA.")
        return 0

    by_phase: dict[str, int] = {}
    for m in knockout_matches:
        by_phase[m["phase"]] = by_phase.get(m["phase"], 0) + 1
    print(f"Encontrados {len(knockout_matches)} jogo(s) do mata-mata:")
    for phase, count in sorted(by_phase.items(), key=lambda kv: kv[0]):
        print(f"  {phase}: {count}")

    if args.dry_run:
        for m in knockout_matches:
            src = m.get("schedule_source") or ("fifa" if m.get("fifa_id_match") else "?")
            print(
                f"  [{m['phase']}] {m['home_team']} x {m['away_team']} — {m['kickoff']} ({src})"
            )
        return 0

    round_data, added, updated = merge_knockout_matches(round_data, knockout_matches)
    round_data["results_synced_at"] = datetime.now(UTC).isoformat()
    save_round_file(round_path, round_data, backup=not args.no_backup)

    print(f"Atualizado {round_path} — {added} novo(s), {updated} atualizado(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
