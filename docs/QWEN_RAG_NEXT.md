# Next steps: Qwen 2.5 (2–3B) + RAG chatbot

You already have most of the stack:

- Chat API loads **Qwen2.5-3B-Instruct** (`agroscan/llm_chat.py`)
- In-app **TF-IDF RAG** over disease guides / knowledge (`agroscan/rag.py`)
- LoRA trainer with resume (`llm/train_lora.py`) — currently oriented to **1.5B** adapters under `llm_data/adapters/`

Do this **before** the APK.

## 1. Build a disease-focused QA dataset

Pull from the Bangladesh pack + guides so the model learns AgroScan facts:

```bash
python -m llm.build_qa_dataset
```

Then extend `Datasets/llm/train_qa.jsonl` with:

- Treatment cards from `data/agroscan/` (dose, PHI, PPE, brands)
- “What should I do next?” flows (confirm crop → confirm disease → cultural control → product → licensed dealer)
- Safety refusals (fake AP numbers, HHP misuse)

Keep eval set separate (`eval_qa.jsonl`).

## 2. Train a **3B** LoRA adapter (on the high-end PC)

```bash
python -m llm.train_lora --model Qwen/Qwen2.5-3B-Instruct --out llm_data/adapters/agroscan-3b --resume
```

(Use `--load-in-4bit` if VRAM is tight. See `python -m llm.train_lora --help`.)

Point the app at it:

```text
AGROSCAN_LLM_ADAPTER=llm_data/adapters/agroscan-3b
AGROSCAN_LLM_BASE=Qwen/Qwen2.5-3B-Instruct
AGROSCAN_LLM_4BIT=1
AGROSCAN_LLM_PRELOAD=1
```

Or use `scripts/run_local_with_llm.ps1` after updating the adapter path.

**Do not** load a 1.5B adapter onto the 3B base — the runtime already rejects that mismatch.

## 3. Upgrade RAG content (highest ROI before fancy vectors)

Today RAG is TF-IDF over in-code guides. Next:

1. Index pack markdown/JSON (treatments, regulatory safety, product labels, LIMITS.md).
2. Chunk by disease + crop + language (EN/BN).
3. Return top-k snippets into the Qwen prompt (already the chat pattern).

Optional later: switch TF-IDF → FAISS/Chroma embeddings. Only worth it after the pack is indexed and quality is measured.

## 4. Chat UX / grounding rules

- Always show **sources** (disease id, guide section, pack file).
- Prefer pack text for doses; model paraphrases, does not invent AP numbers.
- Keep the deterministic KB path for known disease keys; use LLM+RAG for open questions.

## 5. Eval before mobile

- Run 50 farmer-style questions (BN + EN) against eval set.
- Fail closed on pesticide advice without PPE / label check warnings.
- Only then wire Capacitor APK (`mobile/`) — APK last, as planned.

## Suggested order

1. Vision models with `--resume` checkpoints  
2. Expand QA + index pack into RAG  
3. Train `agroscan-3b` LoRA  
4. Eval chatbot  
5. Build APK  
