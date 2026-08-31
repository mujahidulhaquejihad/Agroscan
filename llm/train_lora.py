"""LoRA fine-tune a small instruct model on AgroScan agri Q&A (JSONL).

Uses Hugging Face Trainer + PEFT (stable on Windows). Designed for RTX 3060.

Default model: Qwen2.5-1.5B-Instruct (fp16 + gradient checkpointing).

Example (VS Code terminal or Tasks: Run Task → Train 1.5B):

  python -m llm.build_qa_dataset
  python -m llm.train_lora
  python -m llm.train_lora --resume

Smoke test:

  python -m llm.train_lora --max-steps 5 --out llm_data/adapters/smoke-1.5b
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Avoid Transformers importing TensorFlow/Keras (Windows + Keras 3 conflict).
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRAIN = ROOT / "Datasets" / "llm" / "train_qa.jsonl"
DEFAULT_EVAL = ROOT / "Datasets" / "llm" / "eval_qa.jsonl"
DEFAULT_OUT = ROOT / "llm_data" / "adapters" / "agroscan-1.5b"


def _require_pkgs() -> None:
    missing = []
    for pkg in ("torch", "transformers", "datasets", "peft", "accelerate"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(
            "Missing packages: "
            + ", ".join(missing)
            + "\nInstall with:\n"
            "  pip install -r llm/requirements-train.txt\n"
            "  pip install torch --index-url https://download.pytorch.org/whl/cu124",
            file=sys.stderr,
        )
        raise SystemExit(1)


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    if not rows:
        raise SystemExit(f"No rows in {path}")
    return rows


def format_example(ex: dict) -> str:
    instr = (ex.get("instruction") or "").strip()
    inp = (ex.get("input") or "").strip()
    out = (ex.get("output") or "").strip()
    if inp:
        prompt = f"### Instruction:\n{instr}\n\n### Input:\n{inp}\n\n### Response:\n"
    else:
        prompt = f"### Instruction:\n{instr}\n\n### Response:\n"
    return prompt + out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AgroScan LoRA fine-tune")
    p.add_argument(
        "--model",
        default="Qwen/Qwen2.5-1.5B-Instruct",
        help="Base instruct model (default: 1.5B for RTX 3060)",
    )
    p.add_argument("--data", type=Path, default=DEFAULT_TRAIN)
    p.add_argument("--eval", type=Path, default=DEFAULT_EVAL)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--epochs", type=float, default=2.0)
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--grad-accum", type=int, default=16)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--max-seq-len", type=int, default=512)
    p.add_argument("--lora-r", type=int, default=16)
    p.add_argument("--lora-alpha", type=int, default=32)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--max-steps", type=int, default=-1)
    p.add_argument(
        "--load-in-4bit",
        action="store_true",
        help="QLoRA via bitsandbytes (optional; can crash on some Windows setups)",
    )
    p.add_argument(
        "--gradient-checkpointing",
        action="store_true",
        default=True,
        help="Lower VRAM (default on for 1.5B). Pass --no-gradient-checkpointing to disable.",
    )
    p.add_argument(
        "--no-gradient-checkpointing",
        action="store_false",
        dest="gradient_checkpointing",
    )
    p.add_argument(
        "--resume",
        action="store_true",
        help="Resume from latest checkpoint under --out",
    )
    p.add_argument("--merge", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    _require_pkgs()

    import torch
    from datasets import Dataset
    from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    if not args.data.exists():
        raise SystemExit(
            f"Missing {args.data}\nRun first: python -m llm.build_qa_dataset"
        )

    print("CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))
        print(
            "VRAM (GB):",
            round(torch.cuda.get_device_properties(0).total_memory / 1e9, 2),
        )

    train_rows = load_jsonl(args.data)
    eval_rows = load_jsonl(args.eval) if args.eval.exists() else []
    print(f"Train examples: {len(train_rows)} | Eval: {len(eval_rows)}")

    train_ds = Dataset.from_list([{"text": format_example(r)} for r in train_rows])
    eval_ds = (
        Dataset.from_list([{"text": format_example(r)} for r in eval_rows])
        if eval_rows
        else None
    )

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    def tokenize(batch: dict) -> dict:
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=args.max_seq_len,
            padding=False,
        )

    print("Tokenizing…")
    train_tok = train_ds.map(
        tokenize, batched=True, remove_columns=["text"], desc="tokenize-train"
    )
    eval_tok = None
    if eval_ds is not None:
        eval_tok = eval_ds.map(
            tokenize, batched=True, remove_columns=["text"], desc="tokenize-eval"
        )

    quant_cfg = None
    torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    if args.load_in_4bit:
        quant_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch_dtype,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )

    # Single-GPU: avoid device_map="auto" (Trainer + accelerate can OOM / mis-place).
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        trust_remote_code=True,
        quantization_config=quant_cfg,
        torch_dtype=None if quant_cfg else torch_dtype,
        device_map={"": 0} if (torch.cuda.is_available() and args.load_in_4bit) else None,
    )
    if torch.cuda.is_available() and not args.load_in_4bit:
        model = model.to("cuda")
    model.config.use_cache = False
    if getattr(model.config, "pad_token_id", None) is None:
        model.config.pad_token_id = tokenizer.pad_token_id

    use_gc = bool(args.gradient_checkpointing)
    if args.load_in_4bit:
        model = prepare_model_for_kbit_training(
            model, use_gradient_checkpointing=use_gc
        )
    elif use_gc:
        model.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs={"use_reentrant": False}
        )

    lora = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()
    if use_gc and hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()

    args.out.mkdir(parents=True, exist_ok=True)
    print(
        f"Config: model={args.model} | batch={args.batch_size} "
        f"accum={args.grad_accum} | seq={args.max_seq_len} | "
        f"gc={use_gc} | 4bit={bool(args.load_in_4bit)}"
    )

    targs = dict(
        output_dir=str(args.out),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        logging_steps=10,
        save_steps=500,
        save_total_limit=3,
        bf16=False,
        fp16=torch.cuda.is_available() and not args.load_in_4bit,
        optim="paged_adamw_8bit" if args.load_in_4bit else "adamw_torch",
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        report_to=[],
        seed=args.seed,
        dataloader_pin_memory=False,
        gradient_checkpointing=use_gc,
        max_grad_norm=1.0,
    )
    if args.max_steps and args.max_steps > 0:
        targs["max_steps"] = args.max_steps
        targs["num_train_epochs"] = 1.0
    if eval_tok is not None:
        targs["evaluation_strategy"] = "steps"
        targs["eval_steps"] = 500

    try:
        training_args = TrainingArguments(**targs)
    except TypeError:
        # Newer transformers renamed evaluation_strategy -> eval_strategy
        if "evaluation_strategy" in targs:
            targs["eval_strategy"] = targs.pop("evaluation_strategy")
        # paged_adamw_8bit needs bitsandbytes; fall back
        if targs.get("optim") == "paged_adamw_8bit":
            targs["optim"] = "adamw_torch"
        training_args = TrainingArguments(**targs)

    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_tok,
        eval_dataset=eval_tok,
        data_collator=collator,
    )

    resume_from = None
    if args.resume:
        resume_from = True  # Trainer picks latest checkpoint under output_dir
        print("Resuming from latest checkpoint under:", args.out)

    trainer.train(resume_from_checkpoint=resume_from)
    trainer.save_model(str(args.out))
    tokenizer.save_pretrained(str(args.out))

    meta = {
        "base_model": args.model,
        "train_file": str(args.data),
        "eval_file": str(args.eval) if args.eval.exists() else None,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "epochs": args.epochs,
        "max_seq_len": args.max_seq_len,
        "batch_size": args.batch_size,
        "grad_accum": args.grad_accum,
        "gradient_checkpointing": use_gc,
        "load_in_4bit": bool(args.load_in_4bit),
        "trainer": "transformers.Trainer+peft",
    }
    (args.out / "agroscan_train_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    print("Saved LoRA adapter to:", args.out)

    if args.merge:
        print("Merging LoRA into base weights…")
        base = AutoModelForCausalLM.from_pretrained(
            args.model,
            trust_remote_code=True,
            torch_dtype=torch_dtype,
            device_map="cpu",
        )
        merged = PeftModel.from_pretrained(base, str(args.out))
        merged = merged.merge_and_unload()
        merge_dir = args.out / "merged"
        merge_dir.mkdir(parents=True, exist_ok=True)
        merged.save_pretrained(str(merge_dir))
        tokenizer.save_pretrained(str(merge_dir))
        print("Saved merged model to:", merge_dir)

    print("Done. Next: keep this adapter; we will add GGUF export + /api/chat wiring later.")


if __name__ == "__main__":
    main()
