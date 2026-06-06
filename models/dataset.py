from pathlib import Path

import pandas as pd
import structlog

logger = structlog.get_logger()


def load_gold_dataset(gold_path: Path | None = None) -> pd.DataFrame:
    from config import settings
    from ingest.gcp.lake_store import cloud_lake_enabled, read_layer_snapshot
    from ingest.gcp.lake_frames import normalize_gold_df

    if gold_path is None and cloud_lake_enabled():
        return normalize_gold_df(read_layer_snapshot("gold"))

    root = gold_path or settings.gold_path
    if not root.exists():
        return pd.DataFrame()
    files = list(root.glob("**/*.parquet"))
    if not files:
        return pd.DataFrame()
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    if "match_id" in df.columns:
        return df.drop_duplicates(subset=["match_id"], keep="last")
    return df


def prepare_training_examples(df: pd.DataFrame) -> list[dict]:
    examples = []
    df = df.drop_duplicates(subset=["match_id"], keep="last")
    for _, row in df.iterrows():
        if not row.get("label"):
            continue
        prompt = (
            f"Você é um analista esportivo. Com base nas estatísticas e notícias abaixo, "
            f"preveja o resultado do jogo {row['home_team']} x {row['away_team']} "
            f"({row['competition']}, rodada {row['round_number']}).\n\n"
            f"{row['context_text']}\n\n"
            f"Resposta (formato bolão - use 1=mandante, X=empate, 2=visitante):"
        )
        examples.append({
            "prompt": prompt,
            "completion": row["label"],
            "match_id": row["match_id"],
        })
    return examples


def export_jsonl(output_path: Path) -> int:
    df = load_gold_dataset()
    examples = prepare_training_examples(df)
    if not examples:
        logger.warning("no_labeled_examples")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(examples).to_json(output_path, orient="records", lines=True, force_ascii=False)
    logger.info("training_export", path=str(output_path), count=len(examples))
    return len(examples)
