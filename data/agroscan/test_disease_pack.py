"""One check: every model disease class has its own file in diseases/ with valid steps."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISEASES = ROOT / "data" / "agroscan" / "diseases"
MODEL = ROOT / "web" / "offline-pack.json"
BN = re.compile(r"[ঀ-৿]")


def test_every_model_class_has_steps():
    classes = json.loads(MODEL.read_text(encoding="utf-8"))["models"]["disease"]["classes"]
    files = sorted(DISEASES.glob("*.json"))
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    for p, rec in zip(files, rows):
        assert p.name == re.sub(r"[^\w]+", "_", rec["class_name"]).strip("_") + ".json", p.name
    by = {n: r for r in rows for n in [r["class_name"], *r.get("aliases", [])]}
    missing = [c for c in classes if c not in by]
    assert missing == [], missing[:10]
    for rec in rows:
        en, bn = rec["immediate_actions_en"], rec["immediate_actions_bn"]
        assert len(en) == len(bn) >= 3, rec["class_name"]
        for i, (a, b) in enumerate(zip(en, bn), 1):
            assert a["step"] == b["step"] == i
            assert BN.search(b["title"] + b["detail"])
        if "healthy" in rec["kb_key"].lower() or rec.get("disease_en") == "Healthy":
            assert rec.get("chemical_treatments") == []
    return len(rows), len(classes)


if __name__ == "__main__":
    n, c = test_every_model_class_has_steps()
    print("ok", n, "disease files,", c, "model classes covered")
