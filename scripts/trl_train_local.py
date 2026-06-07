# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "datasets>=2.18.0",
#   "transformers>=4.40.0",
#   "trl>=0.12.0",
#   "peft>=0.12.0",
#   "accelerate>=0.30.0",
#   "torch",
# ]
# ///
"""SFT do bolão com TRL+LoRA (sem Unsloth). Funciona no Mac (MPS/CPU) e em GPU NVIDIA.

Uso:
  run-pipeline export
  python scripts/trl_train_local.py --dataset data/training/bolao_train.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from models.dataset import export_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SFT bolão local com TRL (sem Unsloth)")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/training/bolao_train.jsonl"),
    )
    parser.add_argument("--base-model", type=str, default="Qwen/Qwen2.5-0.5B-Instruct")
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


def resolve_dtype():
    import torch

    if torch.cuda.is_available():
        if torch.cuda.is_bf16_supported():
            return torch.bfloat16, True
        return torch.float16, True
    return torch.float32, False


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

    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from trl import SFTConfig, SFTTrainer

    dtype, use_bf16 = resolve_dtype()
    device = (
        "cuda"
        if torch.cuda.is_available()
        else "mps"
        if torch.backends.mps.is_available()
        else "cpu"
    )
    print(f"Dispositivo: {device} | dtype: {dtype} | exemplos: {len(examples)}")

    texts = [f"{ex['prompt']}\nResposta:\n{ex['completion']}".strip() for ex in examples]
    ds = Dataset.from_dict({"text": texts})

    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        task_type="CAUSAL_LM",
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    sft_args = SFTConfig(
        output_dir=str(args.output_dir),
        learning_rate=args.learning_rate,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=8,
        max_steps=args.max_steps,
        warmup_ratio=0.05,
        logging_steps=10,
        save_steps=50,
        bf16=use_bf16,
        fp16=not use_bf16 and device == "cuda",
        report_to="none",
        dataset_text_field="text",
        model_init_kwargs={"torch_dtype": dtype},
    )

    trainer = SFTTrainer(
        model=args.base_model,
        train_dataset=ds,
        args=sft_args,
        peft_config=peft_config,
    )
    trainer.train()
    trainer.save_model(str(args.output_dir))
    trainer.processing_class.save_pretrained(str(args.output_dir))
    print(f"Modelo salvo em {args.output_dir}")


if __name__ == "__main__":
    main()
