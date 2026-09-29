"""One check: every model disease class has a pack card with valid steps."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "data" / "agroscan" / "disease_treatments.json"
MODEL = ROOT / "web" / "offline-pack.json"
BN = re.compile(r"[ঀ-৿]")


def test_every_model_class_has_steps():
    classes = json.loads(MODEL.read_text(encoding="utf-8"))["models"]["disease"]["classes"]
    rows = json.loads(PACK.read_text(encoding="utf-8"))
    by = {r["class_name"]: r for r in rows}
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


if __name__ == "__main__":
    test_every_model_class_has_steps()
    print("ok", len(json.loads(MODEL.read_text(encoding="utf-8"))["models"]["disease"]["classes"]), "model classes covered")
