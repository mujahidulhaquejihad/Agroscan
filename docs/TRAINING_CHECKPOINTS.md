# Vision training checkpoints & resume

Training now saves **two** kinds of files under `models/`:

| File | Purpose |
|------|---------|
| `leaf_gate.pt`, `leaf_type.pt`, `disease_{arch}.pt` | Best validation weights (used by the app for inference) |
| `*.train.pt` | Full resume snapshot: model + optimizer + scheduler + AMP scaler + epoch |

Optional epoch-tagged copies (when `--ckpt-every N` and `N > 1`):

- `leaf_gate.train.e5.pt`, `disease_resnet50.train.e10.pt`, …

## High-end PC workflow

Start fresh:

```bash
python -m agrovet.train_all
# or one stage:
python -m agrovet.train_leaf
python -m agrovet.train_crop
python -m agrovet.train_disease --arch efficientnet_b3
```

Stop anytime (Ctrl+C). Resume from the last finished epoch:

```bash
python -m agrovet.train_all --resume
python -m agrovet.train_leaf --resume
python -m agrovet.train_crop --resume
python -m agrovet.train_disease --arch efficientnet_b3 --resume
```

Keep extra snapshots every 5 epochs (in addition to the rolling `.train.pt`):

```bash
python -m agrovet.train_disease --arch resnet50 --resume --ckpt-every 5 --epochs 40
```

Skip finished stages when restarting the full pipeline:

```bash
python -m agrovet.train_all --resume --skip-leaf --skip-crop
```

## Notes

- Resume requires the **same class list** and architecture as the snapshot.
- If only a best `.pt` exists (no `.train.pt`), `--resume` loads weights and continues with a **fresh** optimizer/scheduler from the next epoch.
- LoRA chatbot training already supports resume: `python -m llm.train_lora --resume`.
