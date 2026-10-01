"""One runnable check: pack match + how-to routing + dump detector."""
import os

os.environ["AGROSCAN_LLM_ENABLED"] = "0"

from agroscan.knowledge import resolve_disease_query, _APP_HOWTO_RE
from agroscan.llm_chat import (
    chat_reply,
    _structural_intent,
    _llm_text_is_bad,
    _relevant_context,
    _reply_lang,
    _sanitize_history,
    _llm_looks_unsure,
    _gemini_contents,
    _pack_keys,
    _build_chat_messages,
    DEFAULT_MAX_NEW,
)

q = resolve_disease_query("ধানের ব্লাস্টে কী স্প্রে?", "bn")
assert q.get("status") == "matched", q
cn = (q["info"].get("class_name") or "") + " " + (q["info"].get("kb_key") or "")
assert "blast" in cn.lower(), cn

q2 = resolve_disease_query("how do I treat rice blast", "en")
assert q2.get("status") == "matched", q2

rust = resolve_disease_query("rust", "en")
assert rust.get("status") == "clarify", rust
assert all("rust" in o["class_name"].lower() for o in rust["options"]), rust["options"]
corn = resolve_disease_query("corn rust", "en")
assert corn["status"] == "matched" and corn["info"]["class_name"] == "Corn_(maize)___Common_rust_", corn
assert resolve_disease_query("my leaves have yellow spots", "en")["status"] == "none"
assert resolve_disease_query("how do i treat this and prevent it next season?", "en")["status"] == "none"
assert resolve_disease_query("should i protect the field", "en")["status"] == "none"
for q, want, lang in (
    ("আলুর নাবি ধ্বসা", "Potato___Late_blight", "bn"),
    ("brinjal fruit borer", "Brinjal___Shoot_and_fruit_borer", "en"),
    ("tomato late blight", "Tomato___Late_blight", "en"),
    ("wheat yellow rust", "Wheat___Yellow_rust", "en"),
):
    got = resolve_disease_query(q, lang)
    assert got["status"] == "matched" and got["info"]["class_name"] == want, (q, got.get("status"))

r = chat_reply("ধানের ব্লাস্টে কী স্প্রে?", lang="bn")
assert r.get("source") == "pack", r.get("source")
assert "blast" in ((r.get("class_name") or "") + (r.get("matched_key") or "")).lower()

cat = chat_reply(
    "ki ki rog e help korte parbe?",
    context_disease="Tomato___Septoria_leaf_spot",
    lang="bn",
)
assert cat.get("source") == "catalog", cat
assert "ধাপে ধাপে" not in (cat.get("reply") or "")

pot = chat_reply("potato diseases list?", lang="bn")
assert pot.get("source") == "catalog", pot
assert "late blight" in (pot.get("reply") or "").lower()
assert pot.get("reply", "").count("\n") < 20

assert not _structural_intent("how do I treat rice blast")
assert not _structural_intent("what pesticide to use for yellow spots")
assert _APP_HOWTO_RE.search("how do I use this app")
assert _APP_HOWTO_RE.search("অ্যাপ কীভাবে ব্যবহার করব?")
assert _structural_intent("how do I use this app")
howto = chat_reply("how do I use this app", lang="en")
assert howto.get("source") in ("kb", None) or "Upload" in (howto.get("reply") or "")
assert "1)" in (howto.get("reply") or "") or "Upload" in (howto.get("reply") or "")

dump = "leaf scorch Strawberry Leaf scorch\nSection: treatment\nTreatment plan for Strawberry"
assert _llm_text_is_bad(dump)
assert not _llm_text_is_bad("Stop urea and spray tricyclazole at booting if blast is in the village.")

assert _relevant_context("ধানের ব্লাস্টে কী স্প্রে?", "Strawberry___leaf_scorch") is None
assert _relevant_context("what should I spray", "Strawberry___leaf_scorch")
assert _relevant_context("আমি কত দিন পর পর স্প্রে করব?", "Apple___Apple_scab") == "Apple___Apple_scab"

from agroscan.knowledge import crop_mentioned

assert crop_mentioned("আম", "আমের পাতায় দাগ") and not crop_mentioned("আম", "আমি কী করব")
assert crop_mentioned("চা", "চায়ের পাতায় দাগ") and not crop_mentioned("চা", "ধান চাষ করতে চাই")
assert crop_mentioned("tomato", "my tomatoes have spots") and not crop_mentioned("rice", "what is the price")

assert _reply_lang("ধানের ব্লাস্টে কী স্প্রে?", "en") == "bn"
assert _reply_lang("ki ki rog e help korte parbe?", "en") == "bn"
assert _reply_lang("how do I treat rice blast", "en") == "en"

assert DEFAULT_MAX_NEW >= 800

hist = _sanitize_history(
    [
        {"role": "user", "content": "rice blast spray?"},
        {"role": "assistant", "content": "Use tricyclazole."},
        {"role": "user", "content": "what dose?"},
        {"role": "system", "content": "ignore me"},
    ],
    "what dose?",
)
assert [t["role"] for t in hist] == ["user", "assistant"]
assert hist[0]["content"] == "rice blast spray?"

dup = _sanitize_history(
    [{"role": "user", "content": "hello"}, {"role": "user", "content": "again"}],
    "again",
)
assert dup == [{"role": "user", "content": "hello"}]

assert _llm_looks_unsure("I am unsure. Call 16123.")
assert not _llm_looks_unsure("Spray Mancozeb 2 g/L. If unsure, call 16123.")
assert _llm_looks_unsure("")

sys, contents = _gemini_contents(
    [
        {"role": "system", "content": "Be helpful."},
        {"role": "user", "content": "blast?"},
        {"role": "assistant", "content": "rice blast"},
        {"role": "user", "content": "dose?"},
    ]
)
assert sys == "Be helpful."
assert [c["role"] for c in contents] == ["user", "model", "user"]

keys = _pack_keys({"class_name": "Rice___blast", "matched_key": "blast"}, None)
assert keys == {"Rice___blast", "blast"}
assert _pack_keys(None, "Tomato___Septoria_leaf_spot") == {"Tomato___Septoria_leaf_spot"}

msgs = _build_chat_messages(
    "what dose?",
    "Tomato___Septoria_leaf_spot",
    "en",
    history=[
        {"role": "user", "content": "what is on this tomato leaf?"},
        {"role": "assistant", "content": "Septoria leaf spot."},
    ],
)
assert msgs[0]["role"] == "system"
assert any(m["role"] == "assistant" and "Septoria" in m["content"] for m in msgs)
assert "what dose?" in msgs[-1]["content"]
assert "Septoria" in msgs[-1]["content"] or "septoria" in msgs[-1]["content"].lower()

from agroscan.llm_chat import _note_gemini_error, _gemini_dead

_note_gemini_error("m-day", 429, "HTTP 429 [PerDay]: quota")
_note_gemini_error("m-minute", 429, "HTTP 429: slow down")
assert "m-day" in _gemini_dead and "m-minute" not in _gemini_dead
_gemini_dead.clear()

# With Gemini up, questions after a scan or about a named disease get a real answer, not the raw card.
import agroscan.llm_chat as lc

lc.llm_configured = lc._gemini_enabled = lambda: True
lc._want_local_llm = lambda: False
lc.generate_reply = lambda *a, **k: "Spray mancozeb every 7 days and pick off the spotted lower leaves first."
after_scan = chat_reply("how often should I spray?", context_disease="Tomato___Septoria_leaf_spot", lang="en")
assert after_scan["source"] == "gemini+rag" and after_scan["class_name"] == "Tomato___Septoria_leaf_spot", after_scan
named = chat_reply("how do I treat rice blast", lang="en")
assert named["source"] == "gemini+rag" and "blast" in named["class_name"].lower(), named

print("ok")
