# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "datasets>=2.18.0",
#   "transformers>=4.40.0",
#   "trl>=0.12.0",
#   "peft>=0.12.0",
#   "accelerate>=0.30.0",
#   "trackio",
# ]
# ///

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from datasets import load_dataset
from peft import LoraConfig
from trl import SFTConfig, SFTTrainer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SFT do modelo de bolão no Hugging Face Jobs")
    parser.add_argument("--dataset-repo", type=str, required=True, help="Repo dataset no Hub")
    parser.add_argument("--data-file", type=str, default="training/bolao_train.jsonl")
    parser.add_argument("--base-model", type=str, default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--hub-model-id", type=str, required=True)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=8)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    ds = load_dataset(
        args.dataset_repo,
        data_files={"train": args.data_file},
        split="train",
    )
    if len(ds) < 20:
        raise ValueError(f"Dataset muito pequeno para treino: {len(ds)} linhas")

    def _to_text(row: dict) -> dict:
        prompt = row.get("prompt", "")
        completion = row.get("completion", "")
        text = f"{prompt}\nResposta:\n{completion}".strip()
        return {"text": text}

    ds = ds.map(_to_text)
    ds = ds.remove_columns([c for c in ds.column_names if c != "text"])
    split = ds.train_test_split(test_size=0.05, seed=42)

    run_suffix = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_name = f"bolao-sft-{run_suffix}"

    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        task_type="CAUSAL_LM",
    )

    sft_args = SFTConfig(
        output_dir="outputs/bolao-sft",
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        max_steps=args.max_steps,
        warmup_ratio=0.05,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=50,
        save_strategy="steps",
        save_steps=50,
        bf16=True,
        report_to="trackio",
        project="api-noticia-bolao",
        run_name=run_name,
        push_to_hub=True,
        hub_model_id=args.hub_model_id,
        hub_strategy="every_save",
    )

    trainer = SFTTrainer(
        model=args.base_model,
        train_dataset=split["train"],
        eval_dataset=split["test"],
        args=sft_args,
        peft_config=peft_config,
    )
    trainer.train()
    trainer.push_to_hub()


if __name__ == "__main__":
    main()
