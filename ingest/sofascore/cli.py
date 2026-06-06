from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

import structlog

from config import settings
from ingest.sofascore.compact_stats import compact_match_stats_json
from ingest.sofascore.fept_ingest import build_team_map_from_squads, ingest_fept
from ingest.sofascore.history_ingest import (
    ingest_all_teams_history,
    ingest_fixtures_history,
    ingest_team_history,
)
from ingest.sofascore.stats_ingest import ingest_fept_and_stats, ingest_match_stats
from schemas.national_teams import normalize_national_team

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _load_round_match(round_file: Path, match_id: str | None, index: int | None) -> dict:
    data = json.loads(round_file.read_text(encoding="utf-8"))
    matches = data.get("matches") or []
    if not matches:
        raise ValueError(f"Nenhum jogo em {round_file}")
    if match_id:
        for match in matches:
            if match.get("id") == match_id:
                return match
        raise ValueError(f"Match id não encontrado: {match_id}")
    if index is not None:
        if index < 0 or index >= len(matches):
            raise IndexError(f"Índice fora do intervalo: {index}")
        return matches[index]
    raise ValueError("Use --match-id ou --match-index com --round-file")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingere escalações Sofascore e gera bloco FEPT para KXL"
    )
    parser.add_argument("--home", type=str, help="Seleção mandante")
    parser.add_argument("--away", type=str, help="Seleção visitante")
    parser.add_argument("--date", type=str, help="Data do jogo (YYYY-MM-DD)")
    parser.add_argument("--event-id", type=int, help="ID do evento Sofascore")
    parser.add_argument(
        "--round-file",
        type=Path,
        default=Path("data/rounds/wc_2026.json"),
        help="Calendário Copa (usa kickoff como data)",
    )
    parser.add_argument("--match-id", type=str, help="ID do confronto no round-file")
    parser.add_argument("--match-index", type=int, help="Índice do jogo no round-file")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=f"Diretório de saída (padrão: {settings.sofascore_fept_dir})",
    )
    parser.add_argument("--no-save", action="store_true", help="Não grava JSON em disco")
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Ingere só estatísticas (escanteios, chutes, posse) — sem FEPT",
    )
    parser.add_argument(
        "--with-stats",
        action="store_true",
        help="Ingere FEPT e estatísticas do jogo no mesmo event_id",
    )
    parser.add_argument("--json", action="store_true", help="Imprime payload JSON no stdout")
    parser.add_argument(
        "--build-team-map",
        action="store_true",
        help="Reconstrói data/wc/sofascore_teams.json a partir das convocações",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ingere tudo: fixtures WC (openfootball) + últimos jogos de cada seleção",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Ingere histórico de estatísticas em massa para match_stats.parquet",
    )
    parser.add_argument(
        "--all-teams",
        action="store_true",
        help="Com --history: processa todas as seleções em sofascore_teams.json",
    )
    parser.add_argument(
        "--max-per-team",
        type=int,
        default=25,
        help="Com --history: máximo de jogos recentes por seleção",
    )
    parser.add_argument(
        "--from-fixtures",
        action="store_true",
        help="Com --history: tenta resolver fixtures WC por data e ingerir stats",
    )
    parser.add_argument(
        "--since-year",
        type=int,
        default=2018,
        help="Com --from-fixtures: temporada mínima dos fixtures WC",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Com --from-fixtures: limita quantidade de fixtures processados",
    )
    parser.add_argument(
        "--compact-parquet",
        action="store_true",
        help="Consolida *_stats.json em match_stats.parquet (sem chamar API)",
    )
    args = parser.parse_args()

    if args.compact_parquet:
        report = compact_match_stats_json()
        if args.json:
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(
                f"Compactado: {report.json_files} JSON → "
                f"{report.rows_written} jogos em {report.parquet_path}"
            )
        return

    if args.all:
        fx_report = ingest_fixtures_history(
            since_year=1930,
            limit=None,
            save=not args.no_save,
        )
        teams_report = ingest_all_teams_history(
            max_per_team=args.max_per_team,
            save=not args.no_save,
        )
        combined = {
            "fixtures": fx_report.to_dict(),
            "all_teams": teams_report.to_dict(),
            "parquet_matches": teams_report.parquet_matches,
        }
        if args.json:
            print(json.dumps(combined, ensure_ascii=False, indent=2))
        else:
            print(
                "Sofascore ALL — fixtures WC: "
                f"{fx_report.events_ingested} novos, "
                f"{fx_report.events_skipped} ignorados, "
                f"{fx_report.events_failed} falhas "
                f"({fx_report.events_attempted} tentados)"
            )
            print(
                "Sofascore ALL — seleções: "
                f"{teams_report.teams_processed} times, "
                f"{teams_report.events_ingested} novos, "
                f"{teams_report.events_skipped} ignorados, "
                f"{teams_report.events_failed} falhas"
            )
            print(f"Total no parquet: {teams_report.parquet_matches} jogos")
        return

    if args.history:
        if args.from_fixtures:
            report = ingest_fixtures_history(
                since_year=args.since_year,
                limit=args.limit,
                save=not args.no_save,
            )
        elif args.all_teams:
            report = ingest_all_teams_history(
                max_per_team=args.max_per_team,
                save=not args.no_save,
            )
        elif args.home:
            ok, skip, fail = ingest_team_history(
                args.home,
                max_events=args.max_per_team,
                save=not args.no_save,
            )
            report_dict = {
                "teams_processed": 1,
                "events_ingested": ok,
                "events_skipped": skip,
                "events_failed": fail,
            }
            if args.json:
                print(json.dumps(report_dict, ensure_ascii=False, indent=2))
            else:
                print(
                    f"Histórico {args.home}: {ok} ingeridos, "
                    f"{skip} ignorados, {fail} falhas"
                )
            return
        else:
            parser.error(
                "Com --history use --all-teams, --from-fixtures ou --home SELEÇÃO"
            )
        if args.json:
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(
                f"Histórico Sofascore: {report.events_ingested} ingeridos, "
                f"{report.events_skipped} ignorados, {report.events_failed} falhas "
                f"({report.parquet_matches} jogos no parquet)"
            )
        return

    if args.build_team_map:
        teams = build_team_map_from_squads()
        out = {
            "version": 1,
            "source": "sofascore_search",
            "teams": teams,
        }
        path = Path("data/wc/sofascore_teams.json")
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Mapeamento salvo: {path} ({len(teams)} seleções)")
        return

    home = args.home
    away = args.away
    match_date = _parse_date(args.date) if args.date else None

    if args.match_id or args.match_index is not None:
        match = _load_round_match(args.round_file, args.match_id, args.match_index)
        home = home or match["home_team"]
        away = away or match["away_team"]
        if not match_date:
            kickoff = match.get("kickoff")
            if kickoff:
                match_date = datetime.fromisoformat(kickoff).date()

    if not args.event_id and (not home or not away):
        parser.error("Informe --event-id ou --home/--away (ou --match-id/--match-index)")

    if home:
        home = normalize_national_team(home)
    if away:
        away = normalize_national_team(away)

    save = not args.no_save

    if args.stats_only:
        stats_result = ingest_match_stats(
            home_team=home,
            away_team=away,
            event_id=args.event_id,
            match_date=match_date,
            save=save,
            output_dir=args.output_dir or settings.sofascore_stats_dir,
        )
        payload = stats_result.to_payload()
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"Evento Sofascore: {stats_result.event_id}")
            print(f"Confronto: {stats_result.home_team} x {stats_result.away_team}")
            corners_h = stats_result.stats.get("home_corners")
            corners_a = stats_result.stats.get("away_corners")
            poss_h = stats_result.stats.get("home_possession_pct")
            poss_a = stats_result.stats.get("away_possession_pct")
            print(f"Escanteios: {corners_h} x {corners_a} | Posse: {poss_h}% x {poss_a}%")
            if stats_result.json_path:
                print(f"JSON: {stats_result.json_path}")
            if stats_result.parquet_path:
                print(f"Parquet: {stats_result.parquet_path}")
        return

    if args.with_stats:
        fept_result, fept_path, stats_result = ingest_fept_and_stats(
            home_team=home,
            away_team=away,
            event_id=args.event_id,
            match_date=match_date,
            save=save,
            fept_dir=args.output_dir,
            stats_dir=settings.sofascore_stats_dir,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "fept": fept_result.to_payload(),
                        "stats": stats_result.to_payload(),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            fept = fept_result.fept
            print(f"Evento Sofascore: {fept_result.event_id}")
            print(f"Confronto: {fept_result.home_team} x {fept_result.away_team}")
            print(
                f"Esquemas: {fept.esquema_mandante or '?'} x {fept.esquema_visitante or '?'}"
            )
            print(
                f"Notas: {fept_result.ratings_found} ok, {fept_result.ratings_missing} ausentes"
            )
            print(
                f"Escanteios: {stats_result.stats.get('home_corners')} x "
                f"{stats_result.stats.get('away_corners')}"
            )
            if fept_path:
                print(f"FEPT: {fept_path}")
            if stats_result.parquet_path:
                print(f"Stats: {stats_result.parquet_path}")
        return

    result, path = ingest_fept(
        home_team=home,
        away_team=away,
        event_id=args.event_id,
        match_date=match_date,
        save=save,
        output_dir=args.output_dir,
    )
    payload = result.to_payload()

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        fept = result.fept
        print(f"Evento Sofascore: {result.event_id}")
        print(f"Confronto: {result.home_team} x {result.away_team}")
        print(
            f"Esquemas: {fept.esquema_mandante or '?'} x {fept.esquema_visitante or '?'}"
        )
        print(
            f"Notas: {result.ratings_found} preenchidas, "
            f"{result.ratings_missing} ausentes"
        )
        if path:
            payload = json.loads(path.read_text(encoding="utf-8"))
            meta = payload.get("meta") or {}
            if meta.get("absences_home") or meta.get("absences_away"):
                print(
                    f"Desfalques: {meta.get('absences_home', 0)} mandante, "
                    f"{meta.get('absences_away', 0)} visitante"
                )
            if meta.get("referee"):
                print(
                    f"Árbitro: {meta['referee']} "
                    f"({meta.get('referee_profile', 'equilibrado')})"
                )
            print(f"Salvo em: {path}")
        print("Use --with-stats para escanteios/chutes/posse ou --stats-only")


if __name__ == "__main__":
    main()
