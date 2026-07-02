"""Sincroniza o calendário da fase eliminatória (mata-mata) WC 2026 → ``data/rounds/wc_2026.json``.

Fonte: API oficial da FIFA (``ingest.fifa.client.FifaClient.match_window_matches``),
que retorna uma janela rolante de jogos ao redor da data atual — inclui a Copa do
Mundo da FIFA 2026™ assim que os confrontos do mata-mata são definidos pela FIFA.

A janela é limitada (~dias antes/depois de "agora"), então é preciso rodar este
script periodicamente conforme o torneio avança para capturar cada fase (oitavas,
quartas, semis, final) à medida que a FIFA libera os confrontos.

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
COMPETITION_MARKER = "Copa do Mundo da FIFA 2026"

# Mapa nome do estágio (PT, retornado pela FIFA) → (phase slug, round sequencial).
# Estágios futuros ainda não vistos caem no fallback genérico em _phase_for_stage.
_STAGE_PHASE_MAP: dict[str, tuple[str, int]] = {
    "Segundas de final": ("round_of_32", 4),
    "Oitavas de final": ("round_of_16", 5),
    "Quartas de final": ("quarterfinal", 6),
    "Semifinais": ("semifinal", 7),
    "Disputa de 3º lugar": ("third_place", 8),
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


def _team_name(side: dict[str, Any]) -> str:
    names = side.get("TeamName") or []
    for n in names:
        if str(n.get("Locale", "")).lower().startswith("pt"):
            return normalize_national_team(n.get("Description", ""))
    if names:
        return normalize_national_team(names[0].get("Description", ""))
    return ""


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
    if COMPETITION_MARKER not in season_names:
        return None
    stage_name = (m.get("StageName") or [{}])[0].get("Description", "")
    if stage_name == "Primeira fase":
        return None  # fase de grupos já vem do build_wc_2026_schedule.py

    home = _team_name(m.get("Home") or {})
    away = _team_name(m.get("Away") or {})
    if not home or not away:
        return None

    phase, round_no = _phase_for_stage(stage_name)
    id_match = _match_id(m)
    kickoff = m.get("Date")  # já vem em ISO UTC (ex.: 2026-06-29T17:00:00+00:00)

    return {
        "id": f"{phase}-{_slug_part(home)}-{_slug_part(away)}",
        "home_team": home,
        "away_team": away,
        "group": None,
        "round": round_no,
        "phase": phase,
        "kickoff": kickoff,
        "venue": m.get("Stadium"),
        "city": None,
        "fifa_stage": stage_name,
        "fifa_id_match": id_match or None,
    }


def fetch_knockout_matches(client: FifaClient | None = None) -> list[dict[str, Any]]:
    """Busca jogos do mata-mata da Copa 2026 na janela atual da API FIFA.

    Se a API direta falhar (offline/DNS), usa o cache local ``window_matches.json``
    como fallback, garantindo que o calendário não fique mais desatualizado do que
    o cache já permite.
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
    out: list[dict[str, Any]] = []
    for m in raw_matches:
        parsed = _parse_knockout_match(m)
        if parsed is None:
            continue
        id_match = parsed.get("fifa_id_match")
        if id_match and id_match in seen_ids:
            continue
        if id_match:
            seen_ids.add(id_match)
        # Fallback de deduplicação por confronto + horário caso IdMatch esteja ausente.
        dup_key = (parsed["home_team"], parsed["away_team"], parsed["kickoff"])
        if dup_key in {(o["home_team"], o["away_team"], o["kickoff"]) for o in out}:
            continue
        out.append(parsed)

    logger.info("wc_knockout_matches_fetched", source=source, count=len(out))
    return out


def merge_knockout_matches(
    round_data: dict[str, Any],
    knockout_matches: list[dict[str, Any]],
) -> tuple[dict[str, Any], int, int]:
    """Mescla jogos do mata-mata no round_data existente (por id, substitui se já existir)."""
    matches: list[dict[str, Any]] = round_data.setdefault("matches", [])
    by_id = {m.get("id"): idx for idx, m in enumerate(matches)}

    added = 0
    updated = 0
    for km in knockout_matches:
        idx = by_id.get(km["id"])
        if idx is None:
            matches.append(km)
            by_id[km["id"]] = len(matches) - 1
            added += 1
        else:
            existing = matches[idx]
            km_merged = {**existing, **km}
            # Preserva placar/resultado já sincronizado, se houver.
            for score_key in ("home_score", "away_score", "result_source", "result_synced_at"):
                if score_key in existing:
                    km_merged[score_key] = existing[score_key]
            matches[idx] = km_merged
            updated += 1

    round_data["matches"] = matches
    return round_data, added, updated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sincroniza calendário do mata-mata WC 2026 a partir da API FIFA"
    )
    parser.add_argument(
        "--round-file", default=str(ROUND_FILE), help=f"Padrão: {ROUND_FILE}"
    )
    parser.add_argument("--no-backup", action="store_true", help="Não cria .bak antes de gravar")
    parser.add_argument("--dry-run", action="store_true", help="Só mostra o que seria feito")
    args = parser.parse_args()

    round_path = Path(args.round_file)
    try:
        round_data = load_round_file(round_path)
    except FileNotFoundError as exc:
        print(f"Erro: {exc}")
        return 1

    try:
        knockout_matches = fetch_knockout_matches()
    except FifaClientError as exc:
        print(f"Erro ao consultar API FIFA: {exc}")
        return 1

    if not knockout_matches:
        print("Nenhum jogo do mata-mata encontrado na janela atual da FIFA.")
        return 0

    by_phase: dict[str, int] = {}
    for m in knockout_matches:
        by_phase[m["phase"]] = by_phase.get(m["phase"], 0) + 1
    print(f"Encontrados {len(knockout_matches)} jogo(s) do mata-mata na janela atual:")
    for phase, count in sorted(by_phase.items(), key=lambda kv: kv[0]):
        print(f"  {phase}: {count}")

    if args.dry_run:
        for m in knockout_matches:
            print(f"  [{m['phase']}] {m['home_team']} x {m['away_team']} — {m['kickoff']}")
        return 0

    round_data, added, updated = merge_knockout_matches(round_data, knockout_matches)
    round_data["results_synced_at"] = datetime.now(UTC).isoformat()
    save_round_file(round_path, round_data, backup=not args.no_backup)

    print(f"Atualizado {round_path} — {added} novo(s), {updated} atualizado(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
