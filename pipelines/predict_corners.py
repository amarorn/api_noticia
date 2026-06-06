import argparse
import json
from pathlib import Path

from models.corners_predictor import CornersPredictor
from schemas.national_teams import normalize_national_team

DEFAULT_ROUND = Path("data/rounds/wc_2026.json")


def _prediction_to_dict(result) -> dict:
    pred = result.prediction
    return {
        "home_team": result.home_team,
        "away_team": result.away_team,
        "data_source": result.data_source,
        "expected_corners": (
            f"{pred.expected_home_corners:.1f}x{pred.expected_away_corners:.1f}"
        ),
        "expected_total_corners": round(pred.expected_total_corners, 2),
        "most_likely_corners": pred.most_likely_score,
        "prob_home_more_corners": round(pred.prob_home_more, 4),
        "prob_draw_corners": round(pred.prob_draw_corners, 4),
        "prob_away_more_corners": round(pred.prob_away_more, 4),
        "line_probs": {k: round(v, 4) for k, v in pred.line_probs.items()},
        "factors": result.factors.as_dict(),
        "training_summary": result.training_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Previsão de escanteios (Poisson + histórico Sofascore)"
    )
    parser.add_argument("--home", type=str, required=True, help="Seleção mandante")
    parser.add_argument("--away", type=str, required=True, help="Seleção visitante")
    parser.add_argument("--phase", type=str, default="group")
    parser.add_argument("--json", action="store_true", help="Saída JSON")
    args = parser.parse_args()

    predictor = CornersPredictor()
    result = predictor.predict(
        normalize_national_team(args.home),
        normalize_national_team(args.away),
        phase=args.phase,
    )
    payload = _prediction_to_dict(result)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    pred = result.prediction
    print(f"{result.home_team} x {result.away_team}")
    print(f"Fonte: {result.data_source}")
    print(
        f"Escanteios esperados: {pred.expected_home_corners:.1f} x "
        f"{pred.expected_away_corners:.1f} (total {pred.expected_total_corners:.1f})"
    )
    print(f"Placar mais provável: {pred.most_likely_score}")
    print(
        f"Mais escanteios: casa {pred.prob_home_more:.1%} | "
        f"empate {pred.prob_draw_corners:.1%} | fora {pred.prob_away_more:.1%}"
    )
    for key in ("over_9.5", "under_9.5", "over_10.5", "under_10.5"):
        if key in pred.line_probs:
            print(f"P({key.replace('_', ' ')}): {pred.line_probs[key]:.1%}")
    print(f"Treino Sofascore: {result.training_summary}")


if __name__ == "__main__":
    main()
