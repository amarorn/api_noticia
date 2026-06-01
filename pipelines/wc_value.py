import argparse
import json
from pathlib import Path

from models.ev_value import MatchValueReport, evaluate_match
from models.wc_predictor import WcPredictor
from schemas.national_teams import normalize_national_team

DEFAULT_ODDS_FILE = Path("data/rounds/wc_2026_odds.json")


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _label_outcome(outcome: str) -> str:
    labels = {
        "1": "Vitória mandante",
        "X": "Empate",
        "2": "Vitória visitante",
    }
    return labels.get(outcome, outcome)


def _format_value_line(item) -> str:
    return (
        f"{_label_outcome(item.outcome)} | odd={item.odd:.2f} | "
        f"p_model={item.model_prob:.1%} | p_implícita={item.implied_prob:.1%} | "
        f"EV={item.expected_value:.2%} | odd_justa={item.fair_odd:.2f} | "
        f"Kelly(1/4)={item.kelly_quarter:.2%}"
    )


def _print_report(report: MatchValueReport) -> None:
    print(f"\n{'=' * 70}")
    print(f"{report.home_team} x {report.away_team}")
    if report.best is None:
        print("Sem entrada recomendada (EV abaixo do mínimo).")
    else:
        print("Melhor entrada:")
        print(f"- {_format_value_line(report.best)}")
    print("Mercados avaliados:")
    for item in report.outcomes:
        print(f"- {_format_value_line(item)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Análise de valor (EV) para odds da Copa")
    parser.add_argument(
        "--odds-file",
        type=Path,
        default=DEFAULT_ODDS_FILE,
        help="JSON com jogos e odds 1/X/2",
    )
    parser.add_argument(
        "--min-edge",
        type=float,
        default=0.03,
        help="EV mínimo para recomendar entrada (ex: 0.03 = 3%)",
    )
    parser.add_argument("--json", action="store_true", help="Saída JSON")
    args = parser.parse_args()

    odds_data = _load_json(args.odds_file)
    predictor = WcPredictor()
    phase_default = odds_data.get("phase", "group")

    reports: list[MatchValueReport] = []
    for row in odds_data.get("matches", []):
        home = normalize_national_team(row["home_team"])
        away = normalize_national_team(row["away_team"])
        phase = row.get("phase", phase_default)
        prediction = predictor.predict(home, away, phase=phase)
        probabilities = {
            "1": prediction.prob_home,
            "X": prediction.prob_draw,
            "2": prediction.prob_away,
        }
        report = evaluate_match(
            home_team=home,
            away_team=away,
            probabilities=probabilities,
            odds=row["odds"],
            min_edge=args.min_edge,
        )
        reports.append(report)

    if args.json:
        payload = []
        for report in reports:
            payload.append(
                {
                    "home_team": report.home_team,
                    "away_team": report.away_team,
                    "best": (
                        {
                            "outcome": report.best.outcome,
                            "odd": report.best.odd,
                            "model_prob": report.best.model_prob,
                            "implied_prob": report.best.implied_prob,
                            "expected_value": report.best.expected_value,
                            "fair_odd": report.best.fair_odd,
                            "kelly_quarter": report.best.kelly_quarter,
                        }
                        if report.best
                        else None
                    ),
                    "outcomes": [
                        {
                            "outcome": item.outcome,
                            "odd": item.odd,
                            "model_prob": item.model_prob,
                            "implied_prob": item.implied_prob,
                            "expected_value": item.expected_value,
                            "fair_odd": item.fair_odd,
                            "kelly_quarter": item.kelly_quarter,
                        }
                        for item in report.outcomes
                    ],
                }
            )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print("Análise de valor (EV) com base em probabilidades do modelo.")
    print("Atenção: EV positivo não garante acerto individual. Use gestão de risco.")
    for report in reports:
        _print_report(report)


if __name__ == "__main__":
    main()
