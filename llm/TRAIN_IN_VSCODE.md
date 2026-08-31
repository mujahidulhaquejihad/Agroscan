# Train AgroScan 1.5B LLM in VS Code

Target: **Qwen2.5-1.5B-Instruct** LoRA on your **RTX 3060 (12 GB)**.  
Time: often **~15–30+ hours** for 2 epochs on ~69k examples — that is expected.

---

## One-time setup

In a VS Code terminal (`Ctrl+`` `):

```powershell
cd "I:\Agroscan\Agroscan"
python -m pip install --upgrade pip
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -r llm\requirements-train.txt
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Build data if needed:

```powershell
python -m llm.build_qa_dataset
```

---

## Train 1.5B from VS Code (recommended)

### Option A — Task Runner (easiest)

1. Open this folder in **VS Code / Cursor**: `I:\Agroscan\Agroscan`
2. `Ctrl+Shift+P` → **Tasks: Run Task**
3. Choose:
   - **AgroScan: Smoke test LoRA (5 steps)** — quick GPU check
   - **AgroScan: Train 1.5B LoRA (full)** — full run
   - **AgroScan: Resume 1.5B LoRA from checkpoint** — if interrupted

Leave the terminal open. Do not close VS Code while training.

### Option B — Terminal command

```powershell
cd "I:\Agroscan\Agroscan"
$env:USE_TF='0'
$env:TRANSFORMERS_NO_TF='1'

python -m llm.train_lora `
  --model Qwen/Qwen2.5-1.5B-Instruct `
  --epochs 2 `
  --batch-size 1 `
  --grad-accum 16 `
  --max-seq-len 512 `
  --gradient-checkpointing `
  --lr 1e-4 `
  --out llm_data\adapters\agroscan-1.5b
```

Defaults already point at **1.5B**, so this also works:

```powershell
python -m llm.train_lora
```

### Resume after sleep / crash

```powershell
python -m llm.train_lora --resume --out llm_data\adapters\agroscan-1.5b
```

Checkpoints save every **500** steps under `llm_data\adapters\agroscan-1.5b\checkpoint-*`.

---

## Why not `--load-in-4bit` by default?

On this Windows + Python 3.13 setup, QLoRA (`--load-in-4bit`) previously hard-crashed.  
**fp16 + gradient checkpointing** is the stable path for 1.5B on a 3060. It uses more VRAM carefully and takes longer — that is fine.

Only try 4-bit if you want:

```powershell
python -m llm.train_lora --load-in-4bit --out llm_data\adapters\agroscan-1.5b-qlora
```

---

## What “done” looks like

Terminal prints:

```text
Saved LoRA adapter to: ...\llm_data\adapters\agroscan-1.5b
Done.
```

Folder should contain `adapter_model.safetensors` (or `.bin`) + `adapter_config.json` + `agroscan_train_meta.json`.

---

## Quick generation check

```powershell
python -c "
from agroscan.llm_chat import chat_reply, llm_status
print(llm_status())
print(chat_reply('টমেটো লেট ব্লাইটে কী করব?', None, 'bn'))
"
```

---

## Chat API + 6 GB server

`/api/chat` is wired to LoRA + KB fallback (`agroscan/llm_chat.py`).

See **`llm/DEPLOY_6GB.md`** for GGUF / small-VPS options.

```powershell
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000
# GET /api/status → llm.enabled / llm.loaded
```

---

## Status

| Item | Notes |
|------|--------|
| Dataset | `Datasets/llm/train_qa.jsonl` (~69k) |
| Trainer | `llm/train_lora.py` (default = 1.5B) |
| VS Code tasks | `.vscode/tasks.json` |
| Adapter out | `llm_data/adapters/agroscan-1.5b` |
| `/api/chat` LoRA + KB | Done |
| GGUF on 6 GB server | Optional — `llm/DEPLOY_6GB.md` |
