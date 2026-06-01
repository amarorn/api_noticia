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
    base_model: str = "meta-llama/Llama-3.2-1B-Instruct",
) -> None:
    count = export_jsonl(dataset_path)
    if count == 0:
        logger.error(
            "training_aborted",
            reason="Dataset vazio. Adicione labels (1/2/X) nos jogos gold antes de treinar.",
        )
        return

    logger.info(
        "training_ready",
        dataset=str(dataset_path),
        examples=count,
        base_model=base_model,
        output_dir=str(output_dir),
        hint="Use Unsloth SFT com o JSONL exportado. Veja README.md.",
    )


if __name__ == "__main__":
    train()
