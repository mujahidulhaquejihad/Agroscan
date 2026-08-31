# Deploy AgroScan 1.5B to a 6 GB RAM server

The Windows **RTX 3060** can serve the LoRA adapter in fp16 via `/api/chat`.

A **6 GB RAM** Linux host usually **cannot** load Qwen2.5-1.5B + vision models in RAM.
Use one of these:

## Option A — Keep LLM on the GPU PC (simplest)

- Run FastAPI on the 3060 machine with `llm_data/adapters/agroscan-1.5b`.
- Point the public tunnel / mobile API at that host.
- On the small VPS, either proxy `/api/chat` or leave chat on KB-only (`AGROSCAN_LLM_ENABLED=0`).

## Option B — GGUF + llama.cpp / Ollama (for 6 GB RAM)

1. Merge LoRA into base (on the 3060):

```powershell
cd "I:\Agroscan\Agroscan"
python -m llm.train_lora --merge --out llm_data\adapters\agroscan-1.5b --max-steps 1
```

(Or merge with a small script using `PeftModel.merge_and_unload()` on the finished adapter.)

2. Convert merged weights to GGUF with [llama.cpp](https://github.com/ggerganov/llama.cpp) `convert_hf_to_gguf.py`.

3. Quantize to **Q4_K_M** (fits ~1–2 GB).

4. Serve with `llama-server` or Ollama; change AgroScan chat to call that HTTP API instead of in-process PeftModel.

`agrovet/llm_chat.py` is the in-process path. A GGUF HTTP client can replace `generate_reply()` later without changing the frontend.

## Env flags (FastAPI)

| Variable | Meaning |
|----------|---------|
| `AGROSCAN_LLM_ENABLED` | `auto` (CUDA), `1`, or `0` |
| `AGROSCAN_LLM_ADAPTER` | default `llm_data/adapters/agroscan-1.5b` |
| `AGROSCAN_LLM_BASE` | default `Qwen/Qwen2.5-1.5B-Instruct` |
| `AGROSCAN_LLM_DEVICE` | `auto` / `cuda` / `cpu` |
| `AGROSCAN_LLM_MAX_NEW` | max new tokens (default 256) |
