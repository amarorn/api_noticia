import argparse
from pathlib import Path

from models.train import train


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta JSONL gold e treina LM de bolão")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/training/bolao_train.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("models/checkpoints/bolao-unsloth"),
    )
    parser.add_argument("--base-model", default="unsloth/Qwen2.5-0.5B-Instruct")
    parser.add_argument(
        "--unsloth",
        action="store_true",
        help="Executa scripts/unsloth_train.py (requer pip install -e \".[unsloth]\")",
    )
    args = parser.parse_args()
    train(
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        base_model=args.base_model,
        use_unsloth=args.unsloth,
    )


if __name__ == "__main__":
    main()
