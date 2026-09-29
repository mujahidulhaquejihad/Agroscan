"""Level-2 Other option + Gemma/Gemini routing flags."""
import os

os.environ["AGROSCAN_LLM_ENABLED"] = "0"
os.environ["AGROSCAN_GEMINI"] = "0"

from agroscan.config import CROP_OTHER_LABEL, CROP_OTHER_THRESHOLD
from agroscan.infer import _decorate_crop, _ensure_other_option
from agroscan.label_map import classes_for_crop, is_other_crop
from agroscan.llm_chat import DEFAULT_BASE, _gemini_enabled, _local_base_id, _local_provider

assert is_other_crop("Other")
assert is_other_crop("other")
assert not is_other_crop("Tomato")
assert classes_for_crop(["Tomato___healthy", "Rice___Blast"], "Other") == []

top = _ensure_other_option([{"crop": "Tomato", "confidence": 0.92}])
assert top[-1]["crop"] == CROP_OTHER_LABEL
assert len(_ensure_other_option(top)) == len(top)

low = _decorate_crop(
    {
        "available": True,
        "crop": "Tomato",
        "confidence": CROP_OTHER_THRESHOLD - 0.1,
        "top3": [{"crop": "Tomato", "confidence": 0.4}],
    }
)
assert low["crop"] == CROP_OTHER_LABEL
assert low["is_other"]
assert low["guess"] == "Tomato"
assert any(is_other_crop(x["crop"]) for x in low["top3"])

high = _decorate_crop(
    {
        "available": True,
        "crop": "Rice",
        "confidence": 0.97,
        "top3": [{"crop": "Rice", "confidence": 0.97}],
    }
)
assert high["crop"] == "Rice"
assert not high["is_other"]
assert any(is_other_crop(x["crop"]) for x in high["top3"])

assert not _gemini_enabled()
assert "gemma" in DEFAULT_BASE.lower()
assert "gemma" in _local_base_id().lower()
assert _local_provider() == "gemma"

print("ok")
