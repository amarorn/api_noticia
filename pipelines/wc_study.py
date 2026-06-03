import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import settings
from ingest.fixtures.world_cup import WC_EDITIONS, load_wc_fixtures
from models.wc_collaborative import CollaborativeWcModel


def _source_manifest() -> list[dict]:
    base = "https://raw.githubusercontent.com/openfootball/worldcup/master"
    sources: list[dict] = []
    for season, folder in WC_EDITIONS.items():
        sources.append(
            {
                "season": season,
                "folder": folder,
                "group_stage_url": f"{base}/{folder}/cup.txt",
                "knockout_url": f"{base}/{folder}/cup_finals.txt",
            }
        )
    return sources


def _season_summary(df: pd.DataFrame) -> list[dict]:
    summary = []
    for season, grp in df.groupby("season"):
        summary.append(
            {
                "season": int(season),
                "matches": int(len(grp)),
                "home_wins": int((grp["label"] == "1").sum()),
                "draws": int((grp["label"] == "X").sum()),
                "away_wins": int((grp["label"] == "2").sum()),
            }
        )
    return sorted(summary, key=lambda x: x["season"])


def run_study(output: Path, validation_season: int = 2022) -> dict:
    fixtures = load_wc_fixtures()
    if fixtures.empty:
        raise ValueError("Sem dados de Copa no lake. Execute: import-world-cup")

    model = CollaborativeWcModel()
    metrics = model.fit(fixtures, validation_season=validation_season)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "estudo probabilístico com dados reais e verificáveis",
        "dataset": {
            "rows": int(len(fixtures)),
            "seasons": sorted(int(s) for s in fixtures["season"].unique().tolist()),
            "season_summary": _season_summary(fixtures),
            "competition": "Copa do Mundo",
            "data_quality": {
                "missing_scores": int(fixtures["home_score"].isna().sum() + fixtures["away_score"].isna().sum()),
                "missing_labels": int(fixtures["label"].isna().sum()),
            },
        },
        "sources": {
            "provider": "openfootball/worldcup",
            "manifest": _source_manifest(),
        },
        "models": {
            "collaborative_ensemble": {
                "description": "combinação calibrada de Dixon-Coles + Regressão Logística",
                "weights": {
                    "dixon_coles": round(metrics.dixon_coles_weight, 3),
                    "logistic": round(metrics.logistic_weight, 3),
                },
                "validation": {
                    "season": validation_season,
                    "samples": metrics.validation_size,
                    "accuracy": round(metrics.accuracy, 4),
                    "brier_score": round(metrics.brier_score, 6),
                    "log_loss": round(metrics.log_loss, 6),
                },
            }
        },
        "usage_note": (
            "Probabilidades são estimativas estatísticas. Use gestão de risco e nunca trate como garantia."
        ),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Estudo de modelo da Copa com dados reais")
    parser.add_argument(
        "--output",
        type=Path,
        default=settings.lake_root / "reports" / "wc_model_study.json",
        help="Arquivo JSON de saída do estudo",
    )
    parser.add_argument(
        "--validation-season",
        type=int,
        default=2022,
        help="Temporada usada para validação fora da amostra",
    )
    args = parser.parse_args()

    report = run_study(args.output, validation_season=args.validation_season)
    m = report["models"]["collaborative_ensemble"]["validation"]
    w = report["models"]["collaborative_ensemble"]["weights"]
    print(f"Relatório salvo em: {args.output}")
    print(
        "Ensemble calibrado | "
        f"Dixon-Coles={w['dixon_coles']:.3f} Logistic={w['logistic']:.3f} | "
        f"acc={m['accuracy']:.3f} brier={m['brier_score']:.4f} logloss={m['log_loss']:.4f}"
    )


if __name__ == "__main__":
    main()
