# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "unsloth",
#   "datasets>=2.18.0",
#   "trl>=0.12.0",
# ]
# ///
"""
Fine-tuning com Unsloth a partir do JSONL exportado pelo pipeline gold.

Uso:
  run-pipeline export
  python scripts/unsloth_train.py --dataset data/training/bolao_train.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from models.dataset import export_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SFT bolão com Unsloth")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/training/bolao_train.jsonl"),
    )
    parser.add_argument("--base-model", type=str, default="unsloth/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--output-dir", type=Path, default=Path("models/checkpoints/bolao-unsloth"))
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--export-first", action="store_true", help="Regenera JSONL do gold antes")
    return parser.parse_args()


def load_examples(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    args = parse_args()
    if args.export_first or not args.dataset.exists():
        count = export_jsonl(args.dataset)
        if count == 0:
            raise SystemExit(
                "Dataset vazio. Execute import-fixtures + run-pipeline gold/export com labels."
            )

    examples = load_examples(args.dataset)
    if len(examples) < 20:
        raise SystemExit(f"Dataset muito pequeno: {len(examples)} exemplos (mínimo 20)")

    from datasets import Dataset
    from unsloth import FastLanguageModel
    from trl import SFTTrainer
    from transformers import TrainingArguments

    texts = [
        f"{ex['prompt']}\nResposta:\n{ex['completion']}".strip() for ex in examples
    ]
    ds = Dataset.from_dict({"text": texts})

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=2048,
        load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=ds,
        dataset_text_field="text",
        args=TrainingArguments(
            output_dir=str(args.output_dir),
            per_device_train_batch_size=2,
            gradient_accumulation_steps=8,
            max_steps=args.max_steps,
            learning_rate=args.learning_rate,
            logging_steps=10,
            save_steps=50,
            bf16=True,
        ),
    )
    trainer.train()
    model.save_pretrained(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))
    print(f"Modelo salvo em {args.output_dir}")


if __name__ == "__main__":
    main()
