# AgroScan

Bangladesh farmer app: leaf photo → crop → disease, plus pack-first chat (RAG + Qwen for leftover questions).

Same FastAPI backend powers the web UI, PWA, and Android app.

## Open this folder

Work in **`I:\Agroscan\Agroscan`** (the parent `I:\Agroscan` folder is only Syncthing).

## What lives where

```
Agroscan/                  ← you are here
├── agroscan/               Python core (vision, RAG, shop, chat)
├── backend/               FastAPI  (backend/main.py)
├── web/                   browser / PWA UI
├── mobile/                Capacitor Android (use this, not archive/apk)
├── llm/                   LoRA train / dataset-build scripts
├── scripts/               split / shop helper scripts
├── deploy/                Cloudflare tunnel example
├── docs/                  how-to, architecture PDF, deploy notes
├── notebooks/             model-comparison notebooks
│
├── data/                  runtime: users.db, shop.db, Bangladesh pack
├── Datasets/              training images + QA JSONL  (gitignored)
├── models/                vision .pt checkpoints      (gitignored)
├── llm_data/              LoRA adapters               (gitignored)
│
├── archive/               old zip, extra venvs, unused Android Studio tree
├── Dockerfile             API + web (CPU PyTorch)
└── start_server.bat       local uvicorn on port 8000
```

| Want… | Go here |
|--------|---------|
| Change API or chat routing | `agroscan/`, `backend/main.py` |
| Change the website | `web/` |
| Change Android wrapper | `mobile/` |
| Disease doses / 16123 pack | `data/agroscan/` |
| Train vision models | `python -m agroscan.train_all` |
| Train Qwen LoRA | `llm/train_lora.py` (see `docs/` + `.vscode/tasks.json`) |
| Architecture diagram | `docs/AgroScan_Architecture.pdf` |

## Pipeline (three levels)

1. **Leaf gate** — MobileNetV3-Large. Not a leaf → stop.
2. **Crop** — EfficientNet-B3. Low confidence → farmer picks from top-3.
3. **Disease** — EfficientNet-B3 + ResNet-50 + DenseNet-121. Masked to the crop. **Highest-confidence model wins** (no averaging).

Chat is pack-first. Qwen2.5-3B + TF-IDF RAG only for open questions. Details: `docs/AgroScan_Architecture.pdf`.

## Setup

GPU build of PyTorch (RTX 3060 / CUDA 12.x):

    python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
    python -m pip install -r requirements.txt

    python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"

## Run

    python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

or `start_server.bat`.

- Web UI: http://localhost:8000/
- Status: GET /api/status
- Predict: POST /api/predict
- Chat: POST /api/chat

LLM on this PC: `.\scripts\run_local_with_llm.ps1`

## Mobile / production

See [docs/DEPLOY_MOBILE.md](docs/DEPLOY_MOBILE.md) (Docker, Cloudflare Tunnel, PWA, Capacitor APK).

    cd mobile
    npm install
    npm run cap:sync
    cd android && ./gradlew assembleDebug

## Training

From this folder. Disease training uses unified `Datasets/train|valid|test`:

    python -m agroscan.train_all

    python -m agroscan.train_leaf
    python -m agroscan.train_disease --arch efficientnet_b3

Checkpoints: `models/leaf_gate.pt`, `models/leaf_type.pt`, `models/disease_<arch>.pt`.

If a Bangladesh zip is still packed: `python -m agroscan.prepare_bd_leaf_dataset extract`

## Troubleshooting

**[WinError 1455] paging file too small** — set `NUM_WORKERS = 0` in `agroscan/config.py`, or enlarge the Windows pagefile, then reboot.
