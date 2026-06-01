import argparse
import json
from pathlib import Path

from models.wc_predictor import WcPredictor
from schemas.national_teams import normalize_national_team

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
    print(f"Placar provável (Poisson): {pred.poisson_score} (gols esp. {pred.expected_goals})")
    print(f"H2H: {pred.h2h_summary}")
    if verbose:
        print(f"\n{pred.context}")
        print(f"\nModelos: {json.dumps(pred.model_breakdown, ensure_ascii=False)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Palpites Copa do Mundo (Poisson + Logística)")
    parser.add_argument("--round-file", type=Path, default=DEFAULT_ROUND, help="JSON com jogos")
    parser.add_argument("--home", type=str, help="Seleção mandante (palpite avulso)")
    parser.add_argument("--away", type=str, help="Seleção visitante (palpite avulso)")
    parser.add_argument("--phase", type=str, default="group", help="Fase: group, round_16, quarter...")
    parser.add_argument("--json", action="store_true", help="Saída JSON")
    parser.add_argument("--quiet", action="store_true", help="Menos detalhes")
    args = parser.parse_args()

    predictor = WcPredictor()
    results = []

    if args.home and args.away:
        home = normalize_national_team(args.home)
        away = normalize_national_team(args.away)
        pred = predictor.predict(home, away, phase=args.phase)
        results.append(pred)
    else:
        round_data = _load_round(args.round_file)
        phase = round_data.get("phase", "group")
        for match in round_data.get("matches", []):
            home = normalize_national_team(match["home_team"])
            away = normalize_national_team(match["away_team"])
            match_phase = match.get("phase", phase)
            pred = predictor.predict(home, away, phase=match_phase)
            results.append(pred)

    if args.json:
        output = [
            {
                "home_team": p.home_team,
                "away_team": p.away_team,
                "prediction": p.prediction,
                "confidence": round(p.confidence, 4),
                "probabilities": {"1": p.prob_home, "X": p.prob_draw, "2": p.prob_away},
                "likely_score": p.poisson_score,
                "expected_goals": p.expected_goals,
                "h2h": p.h2h_summary,
                "models": p.model_breakdown,
            }
            for p in results
        ]
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        metrics = predictor.training_metrics
        print(f"Modelo treinado com {metrics.get('train_size', '?')} jogos históricos")
        if "holdout_accuracy" in metrics:
            print(f"Acurácia holdout Copa {metrics.get('holdout_season')}: {metrics['holdout_accuracy']:.1%}")
        for pred in results:
            _print_prediction(pred, verbose=not args.quiet)


if __name__ == "__main__":
    main()
