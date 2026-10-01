"""RAG chunking: treatment pages must split so option 2 is not truncated."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agroscan.rag import _chunks, _section_bodies, retrieve


def main() -> None:
    body = (
        "Treatment plan for Rice — Rice blast:\n"
        "Use only DAE products.\n\n"
        "Chemical option 1:\nProduct: Tricyclazole 75% WP\nDose: 0.6 g/L\n\n"
        "Chemical option 2:\nProduct: Nativo 75 WG\nDose: 0.4 g/L\n\n"
        "Organic / non-chemical options:\n- Trichoderma\n\n"
        "Safety: Wear gloves.\n\n"
        "Legal: Pesticide Act 2018.\n\n"
        "Pack notes: Verify AP numbers."
    )
    parts = _section_bodies("treatment", body)
    assert len(parts) == 4, [p[:40] for p in parts]
    assert "Chemical option 1:" in parts[0] and "Treatment plan" in parts[0]
    assert parts[1].startswith("Treatment plan") and "Chemical option 2:" in parts[1]
    assert "Nativo" in parts[1]
    assert "Organic /" in parts[2]
    assert "Safety:" in parts[3] and "Pack notes:" in parts[3]
    assert _section_bodies("symptoms", "diamond spots") == ["diamond spots"]

    pack = _chunks()
    treat = [c for c in pack if c["class_name"] == "Potato___Late_blight" and c["section"] == "treatment" and c["lang"] == "en"]
    assert len(treat) >= 4, len(treat)
    assert max(len(c["text"]) for c in treat) < 2200, max(len(c["text"]) for c in treat)
    blobs = " ".join(c["text"] for c in treat)
    assert "Chemical option 2:" in blobs
    assert "Chemical option 3:" in blobs or blobs.count("Chemical option") >= 2

    hits = retrieve(
        "late blight spray dose potato",
        lang="en",
        k=6,
        allow_keys={"Potato___Late_blight"},
    )
    joined = "\n".join(hits)
    assert "Chemical option 2:" in joined, "option 2 still missing from retrieve"
    print("ok", "potato treatment pieces", len(treat), "retrieve hits", len(hits))


if __name__ == "__main__":
    main()
