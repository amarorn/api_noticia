import argparse
import json
from pathlib import Path

from models.wc_artifact import load_or_train_wc_predictor
from schemas.national_teams import normalize_national_team
from pipelines.wc_predict_utils import before_date_for_match, match_is_played
from schemas.wc_kxl_dynamic import WcKxlMatchInput

DEFAULT_ROUND = Path("data/rounds/wc_2026.json")


def _load_round(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de rodada não encontrado: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _print_prediction(pred, verbose: bool = True) -> None:
    label_map = {"1": "vitória mandante", "X": "empate", "2": "vitória visitante"}
    print(f"\n{'=' * 60}")
    print(f"{pred.home_team} x {pred.away_team}")
    print(f"Palpite: {pred.prediction} ({label_map[pred.prediction]})")
    print(f"Confiança: {pred.confidence:.1%}")
    print(
        f"Probabilidades: 1={pred.prob_home:.1%} | X={pred.prob_draw:.1%} | 2={pred.prob_away:.1%}"
    )
    print(f"Placar provável (Dixon-Coles): {pred.poisson_score} (gols esp. {pred.expected_goals})")
    print(f"H2H: {pred.h2h_summary}")
    if verbose:
        print(f"\n{pred.context}")
        print(f"\nModelos: {json.dumps(pred.model_breakdown, ensure_ascii=False)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Palpites Copa do Mundo (Dixon-Coles + Logística)")
    parser.add_argument("--round-file", type=Path, default=DEFAULT_ROUND, help="JSON com jogos")
    parser.add_argument("--home", type=str, help="Seleção mandante (palpite avulso)")
    parser.add_argument("--away", type=str, help="Seleção visitante (palpite avulso)")
    parser.add_argument("--phase", type=str, default="group", help="Fase: group, round_16, quarter...")
    parser.add_argument("--json", action="store_true", help="Saída JSON")
    parser.add_argument("--output", type=Path, help="Grava JSON em arquivo (usa com --json)")
    parser.add_argument("--quiet", action="store_true", help="Menos detalhes")
    parser.add_argument(
        "--kxl-json",
        type=Path,
        help="JSON com campo kxl_match (mesmo formato da API)",
    )
    parser.add_argument(
        "--no-train",
        action="store_true",
        help="Falha se o artifact WC estiver ausente/desatualizado",
    )
    args = parser.parse_args()

    kxl_match: WcKxlMatchInput | None = None
    if args.kxl_json:
        payload = json.loads(args.kxl_json.read_text(encoding="utf-8"))
        if "kxl_match" in payload:
            kxl_match = WcKxlMatchInput.model_validate(payload["kxl_match"])

    predictor, _manifest = load_or_train_wc_predictor(allow_train=not args.no_train)
    results = []

    if args.home and args.away:
        home = normalize_national_team(args.home)
        away = normalize_national_team(args.away)
        pred = predictor.predict(home, away, phase=args.phase, kxl_match=kxl_match)
        results.append(pred)
    else:
        round_data = _load_round(args.round_file)
        phase = round_data.get("phase", "group")
        round_matches = round_data.get("matches", [])
        for match in round_matches:
            home = normalize_national_team(match["home_team"])
            away = normalize_national_team(match["away_team"])
            match_phase = match.get("phase", phase)
            if match_is_played(match):
                continue
            pred = predictor.predict(
                home,
                away,
                phase=match_phase,
                kxl_match=kxl_match,
                before_date=before_date_for_match(match),
                season=round_data.get("season"),
                group_name=match.get("group"),
            )
            results.append((pred, match))

    if args.json:
        output = []
        for item in results:
            if isinstance(item, tuple):
                p, meta = item
                row = {
                    "group": meta.get("group"),
                    "matchday": meta.get("matchday"),
                    "phase": meta.get("phase"),
                }
            else:
                p, row = item, {}
            output.append({
                **row,
                "home_team": p.home_team,
                "away_team": p.away_team,
                "prediction": p.prediction,
                "confidence": round(p.confidence, 4),
                "probabilities": {"1": p.prob_home, "X": p.prob_draw, "2": p.prob_away},
                "likely_score": p.poisson_score,
                "expected_goals": p.expected_goals,
                "h2h": p.h2h_summary,
                "models": p.model_breakdown,
            })
        payload = json.dumps(output, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
            print(f"Palpites salvos: {args.output} ({len(output)} jogos)")
        else:
            print(payload)
    else:
        metrics = predictor.training_metrics
        print(f"Modelo treinado com {metrics.get('train_size', '?')} jogos históricos")
        if "holdout_accuracy" in metrics:
            print(f"Acurácia holdout Copa {metrics.get('holdout_season')}: {metrics['holdout_accuracy']:.1%}")
        for item in results:
            pred = item[0] if isinstance(item, tuple) else item
            _print_prediction(pred, verbose=not args.quiet)


if __name__ == "__main__":
    main()
