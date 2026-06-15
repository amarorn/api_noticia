"""Sincroniza placares reais da fase de grupos WC → ``data/rounds/wc_2026.json``.

Fontes:
  - **fifa**: janela ``inside.fifa.com`` (jogos finalizados que batem o calendário)
  - **csv**: arquivo com mandante, visitante e placar (export manual ou planilha)

Formato CSV esperado (header, separador `,` ou `;`):

    mandante,visitante,gols_casa,gols_fora
    México,África do Sul,2,1

Aliases aceitos: ``home_team``, ``away_team``, ``home_score``, ``away_score``,
``time_casa``, ``time_fora``, ``placar`` (ex.: ``2-1`` ou ``2:1`` — exige colunas de times).

CLI: ``sync-wc-group-results``
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from schemas.national_teams import normalize_national_team

DEFAULT_ROUND_FILE = Path("data/rounds/wc_2026.json")

SCORE_IN_TEXT = re.compile(
    r"(?P<home>\d+)\s*[-xX:×]\s*(?P<away>\d+)",
)

CSV_HOME_ALIASES = frozenset(
    {"mandante", "home_team", "home", "time_casa", "casa", "team_home", "selecao_mandante"}
)
CSV_AWAY_ALIASES = frozenset(
    {"visitante", "away_team", "away", "time_fora", "fora", "team_away", "selecao_visitante"}
)
CSV_HS_ALIASES = frozenset({"gols_casa", "home_score", "placar_casa", "gols_mandante", "score_home"})
CSV_AS_ALIASES = frozenset({"gols_fora", "away_score", "placar_fora", "gols_visitante", "score_away"})
CSV_SCORE_ALIASES = frozenset({"placar", "score", "resultado", "result"})


@dataclass
class ResultUpdate:
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    source: Literal["fifa", "csv"]
    match_id: str | None = None
    group: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SyncReport:
    round_file: str
    source: str
    updated: list[ResultUpdate]
    skipped: list[str]
    unchanged: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_file": self.round_file,
            "source": self.source,
            "n_updated": len(self.updated),
            "n_unchanged": self.unchanged,
            "n_skipped": len(self.skipped),
            "updated": [u.to_dict() for u in self.updated],
            "skipped": self.skipped,
        }


def load_round_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Calendário não encontrado: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_round_file(path: Path, data: dict[str, Any], *, backup: bool = True) -> None:
    if backup and path.exists():
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        bak = path.with_suffix(path.suffix + f".bak.{ts}")
        shutil.copy2(path, bak)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _schedule_index(round_data: dict[str, Any]) -> dict[tuple[str, str], dict]:
    """Mapa (mandante, visitante) normalizado → objeto match do JSON."""
    index: dict[tuple[str, str], dict] = {}
    for match in round_data.get("matches", []):
        if match.get("phase", round_data.get("phase", "group")) != "group":
            continue
        home = normalize_national_team(match["home_team"])
        away = normalize_national_team(match["away_team"])
        index[(home, away)] = match
    return index


def _resolve_team(raw: str, known: set[str]) -> str | None:
    if not raw or not str(raw).strip():
        return None
    norm = normalize_national_team(str(raw).strip())
    if norm in known:
        return norm
    raw_cf = str(raw).strip().casefold()
    for team in known:
        if team.casefold() == raw_cf:
            return team
    return norm if norm else None


def _parse_score_pair(raw: str) -> tuple[int, int] | None:
    text = str(raw or "").strip()
    m = SCORE_IN_TEXT.search(text)
    if not m:
        return None
    return int(m.group("home")), int(m.group("away"))


def _normalize_csv_key(key: str) -> str:
    return (
        key.strip()
        .lower()
        .replace(" ", "_")
        .replace("ã", "a")
        .replace("õ", "o")
        .replace("ç", "c")
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )


def _pick_column(row: dict[str, str], aliases: frozenset[str]) -> str | None:
    for key, val in row.items():
        if _normalize_csv_key(key) in aliases:
            v = (val or "").strip()
            if v:
                return v
    return None


def parse_results_csv(
    content: str | bytes,
    *,
    schedule_index: dict[tuple[str, str], dict],
) -> tuple[list[ResultUpdate], list[str]]:
    """Lê CSV e devolve updates + linhas ignoradas."""
    if isinstance(content, bytes):
        text = content.decode("utf-8-sig")
    else:
        text = content

    delimiter = ";" if text.count(";") > text.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        return [], ["csv_sem_header"]

    known = {team for pair in schedule_index for team in pair}
    updates: list[ResultUpdate] = []
    skipped: list[str] = []

    for i, row in enumerate(reader, start=2):
        home_raw = _pick_column(row, CSV_HOME_ALIASES)
        away_raw = _pick_column(row, CSV_AWAY_ALIASES)
        if not home_raw or not away_raw:
            skipped.append(f"linha {i}: mandante/visitante ausente")
            continue

        home = _resolve_team(home_raw, known)
        away = _resolve_team(away_raw, known)
        if not home or not away:
            skipped.append(f"linha {i}: times não reconhecidos ({home_raw} x {away_raw})")
            continue

        hs_raw = _pick_column(row, CSV_HS_ALIASES)
        as_raw = _pick_column(row, CSV_AS_ALIASES)
        score_raw = _pick_column(row, CSV_SCORE_ALIASES)

        home_score: int | None = None
        away_score: int | None = None

        if hs_raw is not None and as_raw is not None:
            try:
                home_score = int(float(hs_raw.replace(",", ".")))
                away_score = int(float(as_raw.replace(",", ".")))
            except ValueError:
                skipped.append(f"linha {i}: placar numérico inválido")
                continue
        elif score_raw:
            parsed = _parse_score_pair(score_raw)
            if not parsed:
                skipped.append(f"linha {i}: placar '{score_raw}' inválido")
                continue
            home_score, away_score = parsed
        else:
            skipped.append(f"linha {i}: sem colunas de placar")
            continue

        match, swapped = _locate_match(schedule_index, home, away)
        if match is None:
            skipped.append(f"linha {i}: jogo fora do calendário ({home} x {away})")
            continue
        if swapped:
            home_score, away_score = away_score, home_score
            home, away = normalize_national_team(match["home_team"]), normalize_national_team(
                match["away_team"]
            )

        updates.append(
            ResultUpdate(
                home_team=home,
                away_team=away,
                home_score=home_score,
                away_score=away_score,
                source="csv",
                match_id=match.get("id"),
                group=match.get("group"),
            )
        )

    return updates, skipped


def _locate_match(
    schedule_index: dict[tuple[str, str], dict],
    home: str,
    away: str,
) -> tuple[dict | None, bool]:
    key = (home, away)
    if key in schedule_index:
        return schedule_index[key], False
    rev = (away, home)
    if rev in schedule_index:
        return schedule_index[rev], True
    return None, False


def _fifa_team_name(raw: dict[str, Any]) -> str:
    from ingest.fifa.fixtures_importer import _extract_name

    return _extract_name(raw.get("TeamName", []))


def extract_fifa_results(
    round_data: dict[str, Any],
    fifa_matches: list[dict[str, Any]],
) -> tuple[list[ResultUpdate], list[str]]:
    """Extrai placares FIFA finalizados que existem no calendário WC."""
    schedule_index = _schedule_index(round_data)
    updates: list[ResultUpdate] = []
    skipped: list[str] = []
    seen: set[tuple[str, str]] = set()

    for raw in fifa_matches:
        period = raw.get("Period", 0)
        status = raw.get("MatchStatus", 0)
        if period != 10 and status != 10:
            continue

        home_raw = raw.get("HomeTeam") or raw.get("Home") or {}
        away_raw = raw.get("AwayTeam") or raw.get("Away") or {}
        home_name = _fifa_team_name(home_raw)
        away_name = _fifa_team_name(away_raw)
        if not home_name or not away_name:
            continue

        home = normalize_national_team(home_name)
        away = normalize_national_team(away_name)
        match, swapped = _locate_match(schedule_index, home, away)
        if match is None:
            continue

        key = (
            normalize_national_team(match["home_team"]),
            normalize_national_team(match["away_team"]),
        )
        if key in seen:
            continue
        seen.add(key)

        hs = int(raw.get("HomeTeamScore", 0) or 0)
        as_ = int(raw.get("AwayTeamScore", 0) or 0)
        if swapped:
            hs, as_ = as_, hs

        updates.append(
            ResultUpdate(
                home_team=key[0],
                away_team=key[1],
                home_score=hs,
                away_score=as_,
                source="fifa",
                match_id=match.get("id"),
                group=match.get("group"),
            )
        )

    if not updates and fifa_matches:
        skipped.append("nenhum jogo FIFA finalizado bate o calendário wc_2026.json")
    return updates, skipped


def apply_updates(
    round_data: dict[str, Any],
    updates: list[ResultUpdate],
) -> tuple[dict[str, Any], int]:
    """Grava home_score/away_score nos matches; retorna qtd inalterada."""
    schedule_index = _schedule_index(round_data)
    unchanged = 0
    synced_at = datetime.now(UTC).isoformat()

    for upd in updates:
        match = schedule_index.get((upd.home_team, upd.away_team))
        if match is None:
            continue
        if match.get("home_score") == upd.home_score and match.get("away_score") == upd.away_score:
            unchanged += 1
        match["home_score"] = upd.home_score
        match["away_score"] = upd.away_score
        match["result_source"] = upd.source
        match["result_synced_at"] = synced_at

    round_data["results_synced_at"] = synced_at
    return round_data, unchanged


def sync_wc_group_results(
    *,
    round_file: Path = DEFAULT_ROUND_FILE,
    source: Literal["fifa", "csv", "auto"] = "auto",
    csv_path: Path | None = None,
    force_fifa_refresh: bool = False,
    dry_run: bool = False,
    backup: bool = True,
) -> SyncReport:
    round_data = load_round_file(round_file)
    all_updates: list[ResultUpdate] = []
    all_skipped: list[str] = []
    used_source = source

    if source in ("fifa", "auto"):
        from ingest.fifa.match_ingest import load_fifa_window_matches

        fifa_matches = load_fifa_window_matches(force_refresh=force_fifa_refresh)
        fifa_updates, fifa_skipped = extract_fifa_results(round_data, fifa_matches)
        all_updates.extend(fifa_updates)
        all_skipped.extend(fifa_skipped)

    if source in ("csv", "auto"):
        if csv_path is None:
            if source == "csv":
                raise ValueError("Fonte csv exige --csv PATH")
        else:
            if not csv_path.exists():
                raise FileNotFoundError(f"CSV não encontrado: {csv_path}")
            schedule_index = _schedule_index(round_data)
            csv_updates, csv_skipped = parse_results_csv(
                csv_path.read_bytes(),
                schedule_index=schedule_index,
            )
            # CSV sobrescreve FIFA no mesmo confronto
            by_pair = {(u.home_team, u.away_team): u for u in all_updates}
            for u in csv_updates:
                by_pair[(u.home_team, u.away_team)] = u
            all_updates = list(by_pair.values())
            all_skipped.extend(csv_skipped)
            if csv_updates:
                used_source = "csv" if source == "csv" else "auto"

    if not all_updates:
        return SyncReport(
            round_file=str(round_file),
            source=used_source,
            updated=[],
            skipped=all_skipped,
            unchanged=0,
        )

    round_data, unchanged = apply_updates(round_data, all_updates)

    if not dry_run:
        save_round_file(round_file, round_data, backup=backup)

    return SyncReport(
        round_file=str(round_file),
        source=used_source,
        updated=all_updates,
        skipped=all_skipped,
        unchanged=unchanged,
    )


def sync_single_wc_result(
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    *,
    round_file: Path = DEFAULT_ROUND_FILE,
) -> dict[str, Any]:
    """Atualiza placar de um jogo da fase de grupos em ``wc_2026.json``."""
    if not round_file.exists():
        return {"updated": False, "reason": "round_file_missing"}

    home = normalize_national_team(home_team)
    away = normalize_national_team(away_team)
    round_data = load_round_file(round_file)
    schedule = _schedule_index(round_data)
    if (home, away) not in schedule:
        return {"updated": False, "reason": "not_in_schedule", "home_team": home, "away_team": away}

    upd = ResultUpdate(
        home_team=home,
        away_team=away,
        home_score=home_score,
        away_score=away_score,
        source="superbet",
    )
    round_data, unchanged = apply_updates(round_data, [upd])
    if unchanged >= 1:
        return {
            "updated": False,
            "reason": "unchanged",
            "home_team": home,
            "away_team": away,
        }

    save_round_file(round_file, round_data, backup=True)
    return {
        "updated": True,
        "home_team": home,
        "away_team": away,
        "score": f"{home_score}x{away_score}",
        "round_file": str(round_file),
    }


def write_example_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "mandante,visitante,gols_casa,gols_fora\n"
        "México,África do Sul,2,1\n"
        "Canadá,Bósnia,1,1\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sincroniza placares reais da Copa 2026 → wc_2026.json (FIFA e/ou CSV)."
    )
    parser.add_argument(
        "--round-file",
        type=Path,
        default=DEFAULT_ROUND_FILE,
        help="Calendário WC (padrão: data/rounds/wc_2026.json)",
    )
    parser.add_argument(
        "--source",
        choices=("fifa", "csv", "auto"),
        default="auto",
        help="fifa: só API FIFA; csv: só arquivo; auto: FIFA + CSV (--csv opcional)",
    )
    parser.add_argument("--csv", type=Path, help="CSV com mandante, visitante e placar")
    parser.add_argument(
        "--force-fifa-refresh",
        action="store_true",
        help="Ignora cache FIFA e busca janela online",
    )
    parser.add_argument("--dry-run", action="store_true", help="Não grava o JSON")
    parser.add_argument("--no-backup", action="store_true", help="Não cria .bak antes de gravar")
    parser.add_argument("--json", action="store_true", help="Saída JSON")
    parser.add_argument(
        "--write-example-csv",
        type=Path,
        metavar="PATH",
        help="Grava CSV de exemplo e encerra",
    )
    args = parser.parse_args()

    if args.write_example_csv:
        write_example_csv(args.write_example_csv)
        print(f"Exemplo gravado: {args.write_example_csv}")
        return 0

    try:
        report = sync_wc_group_results(
            round_file=args.round_file,
            source=args.source,
            csv_path=args.csv,
            force_fifa_refresh=args.force_fifa_refresh,
            dry_run=args.dry_run,
            backup=not args.no_backup,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Arquivo: {report.round_file} | fonte: {report.source}")
        if args.dry_run:
            print("(dry-run — JSON não alterado)")
        for u in report.updated:
            print(f"  ✓ {u.home_team} {u.home_score}x{u.away_score} {u.away_team} [{u.source}]")
        if report.unchanged:
            print(f"  = {report.unchanged} jogo(s) já estavam com o mesmo placar")
        for msg in report.skipped:
            print(f"  ⚠ {msg}")
        if not report.updated:
            print("Nenhum placar aplicado.")
            return 1
    return 0 if report.updated else 1


if __name__ == "__main__":
    sys.exit(main())
