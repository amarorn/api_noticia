"""
Esqueleto de fine-tuning para previsão de bolão.

Requer dependências ML: pip install -e ".[ml]"

Integração recomendada com Unsloth ou Hugging Face TRL para SFT.
"""
from pathlib import Path

import structlog

from models.dataset import export_jsonl

logger = structlog.get_logger()


def train(
    dataset_path: Path = Path("data/training/bolao_train.jsonl"),
    output_dir: Path = Path("models/checkpoints/bolao-lm"),
    base_model: str = "unsloth/Qwen2.5-0.5B-Instruct",
    use_unsloth: bool = False,
) -> None:
    count = export_jsonl(dataset_path)
    if count == 0:
        logger.error(
            "training_aborted",
            reason="Dataset vazio. Execute import-fixtures e run-pipeline gold/export.",
        )
        return

    if use_unsloth:
        import subprocess
        import sys

        script = Path(__file__).resolve().parents[1] / "scripts" / "unsloth_train.py"
        subprocess.check_call(
            [
                sys.executable,
                str(script),
                "--dataset",
                str(dataset_path),
                "--base-model",
                base_model,
                "--output-dir",
                str(output_dir),
            ]
        )
        return

    logger.info(
        "training_ready",
        dataset=str(dataset_path),
        examples=count,
        base_model=base_model,
        output_dir=str(output_dir),
        hint='Treino Unsloth: train-bolao --unsloth | python scripts/unsloth_train.py',
    )


if __name__ == "__main__":
    train()
