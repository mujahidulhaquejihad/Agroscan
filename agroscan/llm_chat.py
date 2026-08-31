"""AgroScan chat: Qwen2.5-3B-Instruct + RAG, with knowledge-base fallback.

Designed for local RTX 3060 + 16 GB RAM. Tries 4-bit first, then fp16.
Loads the 3B base model even if no LoRA adapter is present. Never attach a
1.5B adapter to the 3B base.

Env:
  AGROSCAN_LLM_ENABLED   auto|1|0   default auto (on if CUDA)
  AGROSCAN_LLM_BASE      HuggingFace base id
  AGROSCAN_LLM_ADAPTER   path to LoRA adapter dir (optional)
  AGROSCAN_LLM_MAX_NEW   max new tokens (default 220)
  AGROSCAN_LLM_DEVICE    cuda|cpu|auto
  AGROSCAN_LLM_PRELOAD   1 to load at import/startup
  AGROSCAN_LLM_4BIT      auto|1|0   default auto (4-bit on CUDA)
"""
from __future__ import annotations

import gc
import os
import re
import threading
from pathlib import Path
from typing import Optional

from . import config

DEFAULT_ADAPTER = config.LLM_ADAPTERS / "agroscan-3b"
DEFAULT_BASE = "Qwen/Qwen2.5-3B-Instruct"

_lock = threading.Lock()
_model = None
_tokenizer = None
_load_error: Optional[str] = None
_device: Optional[str] = None
_disabled: bool = False
_using_adapter: Optional[str] = None
_quant: Optional[str] = None


def _env_flag(name: str, default: str = "auto") -> str:
    return (os.environ.get(name) or default).strip().lower()


def _adapter_path() -> Optional[Path]:
    raw = (os.environ.get("AGROSCAN_LLM_ADAPTER") or "").strip()
    if raw:
        p = Path(raw)
        return p if p.exists() else None
    if DEFAULT_ADAPTER.exists():
        return DEFAULT_ADAPTER
    return None


def llm_configured() -> bool:
    if _disabled:
        return False
    flag = _env_flag("AGROSCAN_LLM_ENABLED", "auto")
    if flag in ("0", "false", "off", "no"):
        return False
    if flag in ("1", "true", "on", "yes"):
        return True
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def llm_status() -> dict:
    adapter = _adapter_path()
    return {
        "enabled": llm_configured(),
        "loaded": _model is not None,
        "load_error": _load_error,
        "disabled": _disabled,
        "adapter": str(adapter) if adapter else None,
        "base_model": os.environ.get("AGROSCAN_LLM_BASE") or DEFAULT_BASE,
        "device": _device,
        "quant": _quant,
        "rag": True,
    }


def _structural_intent(message: str) -> bool:
    """Keep contacts / gov / how-to / greetings on the deterministic KB."""
    msg = (message or "").lower().strip()
    if not msg:
        return True
    if re.search(r"\b(hi|hello|hey|salam|assalam|নমস্কার|হ্যালো|আসসালাম)\b", msg):
        return True
    if re.search(
        r"\b(emergency|vet|call|hotline|help ?line|doctor|urgent|জরুরি|পশুচিকিৎসক|কল|হেল্পলাইন)\b",
        msg,
    ):
        return True
    if re.search(
        r"\b(gov|government|link|website|ministry|dae|bari|brri|সরকার|মন্ত্রণালয়|লিংক)\b",
        msg,
    ):
        return True
    if re.search(
        r"\b(how|use|work|start|upload|scan|guide|help|কীভাবে|ব্যবহার|আপলোড|সাহায্য)\b",
        msg,
    ):
        return True
    return False


def _kb_is_generic(reply: str, lang: str) -> bool:
    r = (reply or "").lower()
    if (lang or "").startswith("bn"):
        return "আমি পাতার রোগ" in r or "যেমন জিজ্ঞাসা" in r
    return "i can help with plant-leaf" in r or "try asking" in r


def _build_prompt(message: str, context_disease: Optional[str], lang: str) -> str:
    from agroscan.knowledge import advice_for, resolve_disease_query
    from agroscan.rag import retrieve

    lang = (lang or "en").lower()
    if lang.startswith("bn"):
        system = (
            "আপনি AgroScan কৃষি সহকারী। শুধু নিচের retrieved guide অনুসরণ করুন। "
            "এক ফসল/রোগের পরামর্শ অন্য ফসলে মিশাবেন না। "
            "guide-এ যা নেই তা আবিষ্কার করবেন না; না জানলে বলুন অনিশ্চিত এবং 16123 কল করতে বলুন।"
        )
    else:
        system = (
            "You are AgroScan, an agriculture assistant for Bangladeshi farmers. "
            "ONLY use the retrieved guides below. Never mix advice from one crop/disease into another "
            "(e.g. do not give maize northern leaf blight steps for potato late blight). "
            "If the guides do not cover the question, say you are unsure and suggest calling 16123. "
            "Do not invent products, doses, or symptoms."
        )

    parts = [f"### Instruction:\n{system}\n"]
    query = resolve_disease_query(message, "bn" if lang.startswith("bn") else "en")
    pack = query.get("info") if query.get("status") == "matched" else None
    allow_keys = None
    if pack:
        title = pack.get("title") or ""
        summary = pack.get("summary") or ""
        parts.append(f"Matched disease record (authoritative):\n{title}\n{summary}\n")
        allow_keys = {pack.get("matched_key"), pack.get("class_name")}
        allow_keys = {k for k in allow_keys if k}
    elif context_disease:
        info = advice_for(context_disease, "bn" if lang.startswith("bn") else "en")
        if info:
            title = info.get("title") or context_disease
            summary = info.get("summary") or ""
            parts.append(f"Recent leaf scan result: {title}. {summary}\n")
            allow_keys = {info.get("matched_key"), context_disease}
            allow_keys = {k for k in allow_keys if k}
        else:
            parts.append(f"Recent leaf scan class: {context_disease}\n")

    snippets = retrieve(
        message,
        lang=lang,
        k=6,
        extra=context_disease,
        allow_keys=allow_keys,
    )
    if snippets:
        parts.append("Retrieved guides:\n")
        for i, snip in enumerate(snippets, 1):
            parts.append(f"[{i}]\n{snip}\n\n")
    else:
        parts.append("Retrieved guides: none. Say you are unsure.\n")

    parts.append(f"### Input:\n{(message or '').strip()}\n\n### Response:\n")
    return "".join(parts)


def _resolve_device() -> str:
    import torch

    want = (os.environ.get("AGROSCAN_LLM_DEVICE") or "auto").lower()
    if want == "cpu":
        return "cpu"
    if want == "cuda":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _want_4bit(device: str) -> bool:
    flag = _env_flag("AGROSCAN_LLM_4BIT", "auto")
    if flag in ("0", "false", "off", "no"):
        return False
    if flag in ("1", "true", "on", "yes"):
        return device == "cuda"
    return device == "cuda"


def _load_base(base_id: str, device: str, dtype):
    import torch
    from transformers import AutoModelForCausalLM

    kwargs = dict(
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )
    if device == "cuda" and _want_4bit(device):
        try:
            from transformers import BitsAndBytesConfig

            bnb = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )
            model = AutoModelForCausalLM.from_pretrained(
                base_id,
                quantization_config=bnb,
                device_map={"": 0},
                **kwargs,
            )
            return model, "4bit"
        except Exception as exc:
            print(f"[AgroScan LLM] 4-bit load failed ({exc}); falling back to fp16.")

    if device == "cuda":
        model = AutoModelForCausalLM.from_pretrained(
            base_id,
            dtype=dtype,
            device_map={"": 0},
            **kwargs,
        )
        return model, "fp16"
    model = AutoModelForCausalLM.from_pretrained(base_id, dtype=dtype, **kwargs)
    return model.to("cpu"), "fp32"


def _ensure_loaded() -> bool:
    global _model, _tokenizer, _load_error, _device, _disabled, _using_adapter, _quant
    if _disabled:
        return False
    if _model is not None:
        return True

    with _lock:
        if _disabled:
            return False
        if _model is not None:
            return True
        try:
            os.environ.setdefault("USE_TF", "0")
            os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
            os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

            import torch
            from transformers import AutoTokenizer

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            base_id = os.environ.get("AGROSCAN_LLM_BASE") or DEFAULT_BASE
            adapter = _adapter_path()
            if adapter and "1.5b" in adapter.name.lower() and "3b" in base_id.lower():
                print(
                    f"[AgroScan LLM] Ignoring {adapter} — do not load a 1.5B adapter on {base_id}."
                )
                adapter = None

            device = _resolve_device()
            _device = device
            dtype = torch.float16 if device == "cuda" else torch.float32

            tok_src = str(adapter) if adapter else base_id
            print(f"[AgroScan LLM] Loading {base_id} on {device}…")
            tok = AutoTokenizer.from_pretrained(tok_src, trust_remote_code=True)
            if tok.pad_token is None:
                tok.pad_token = tok.eos_token

            model, quant = _load_base(base_id, device, dtype)
            _quant = quant

            if adapter and adapter.exists():
                from peft import PeftModel

                print(f"[AgroScan LLM] Attaching adapter {adapter}")
                model = PeftModel.from_pretrained(model, str(adapter))
                _using_adapter = str(adapter)
            else:
                _using_adapter = None
                print("[AgroScan LLM] No 3B adapter found; using base Instruct model.")

            model.eval()
            _tokenizer = tok
            _model = model
            _load_error = None
            print(f"[AgroScan LLM] Ready ({quant}).")
            return True
        except Exception as exc:
            _load_error = f"{type(exc).__name__}: {exc}"
            print(f"[AgroScan LLM] Load failed: {_load_error}")
            if "paging file" in str(exc).lower() or "1455" in str(exc):
                _disabled = True
                print(
                    "[AgroScan LLM] Disabled for this process. "
                    "Free RAM / enlarge Windows pagefile, then restart the API."
                )
            return False


def preload() -> dict:
    """Call from FastAPI startup to warm the model on the GPU PC."""
    if not llm_configured():
        return llm_status()
    _ensure_loaded()
    return llm_status()


def generate_reply(
    message: str,
    context_disease: Optional[str] = None,
    lang: str = "bn",
) -> Optional[str]:
    """Return generated text, or None if LLM unavailable / empty."""
    if not llm_configured():
        return None
    if not _ensure_loaded():
        return None
    assert _model is not None and _tokenizer is not None

    import torch

    prompt = _build_prompt(message, context_disease, lang)
    max_new = int(os.environ.get("AGROSCAN_LLM_MAX_NEW") or "220")
    inputs = _tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
    try:
        model_device = next(_model.parameters()).device
    except StopIteration:
        model_device = torch.device(_device or "cpu")
    inputs = {k: v.to(model_device) for k, v in inputs.items()}

    with torch.inference_mode():
        out = _model.generate(
            **inputs,
            max_new_tokens=max_new,
            do_sample=False,
            pad_token_id=_tokenizer.pad_token_id,
            eos_token_id=_tokenizer.eos_token_id,
        )

    gen = out[0][inputs["input_ids"].shape[-1] :]
    text = _tokenizer.decode(gen, skip_special_tokens=True).strip()
    if not text:
        return None
    for stop in ("\n### ", "\n###Instruction", "\n### Input"):
        if stop in text:
            text = text.split(stop, 1)[0].strip()
    return text or None


def chat_reply(
    message: str,
    context_disease: Optional[str] = None,
    lang: str = "bn",
    confirm_class: Optional[str] = None,
) -> dict:
    """Pack/KB first for named diseases; Qwen only for open questions with RAG."""
    from agroscan.knowledge import (
        _format_pack_reply,
        _suggestions,
        chatbot_reply,
        resolve_disease_query,
    )

    lang = lang or "en"
    sug_lang = "bn" if (lang or "").startswith("bn") else "en"

    # Authoritative pack answer — ask to confirm when the disease name fits several crops.
    query = resolve_disease_query(message, lang, confirm_class=confirm_class)
    if query.get("status") == "matched":
        pack = query["info"]
        return {
            "reply": _format_pack_reply(pack, lang),
            "suggestions": _suggestions(sug_lang),
            "source": "pack",
            "matched_key": pack.get("matched_key"),
            "class_name": pack.get("class_name"),
        }
    if query.get("status") == "clarify":
        return {
            "reply": query["reply"],
            "suggestions": query.get("suggestions") or [],
            "options": query.get("options") or [],
            "source": "clarify",
        }

    kb = chatbot_reply(message, context_disease, lang, confirm_class=confirm_class)
    if kb.get("source") in ("pack", "context", "clarify"):
        return kb

    if _structural_intent(message):
        kb["source"] = kb.get("source") or "kb"
        return kb

    if not _kb_is_generic(kb.get("reply") or "", lang):
        kb["source"] = "kb"
        return kb

    try:
        llm_text = generate_reply(message, context_disease, lang)
    except Exception as exc:
        print(f"[AgroScan LLM] generate failed: {exc}")
        llm_text = None

    if llm_text:
        return {
            "reply": llm_text,
            "suggestions": kb.get("suggestions") or [],
            "source": "llm",
        }

    kb["source"] = "kb"
    return kb


def _scan_header(best: dict, leaf: dict, crop: dict, lang: str) -> str:
    bn = (lang or "").startswith("bn")
    leaf_p = leaf.get("leaf_probability")
    crop_name = crop.get("crop") or best.get("plant") or ""
    plant = best.get("plant") or crop_name
    cond = best.get("condition") or best.get("prediction") or ""
    conf = best.get("confidence")
    pct = f"{round(float(conf) * 100)}%" if conf is not None else "—"
    leaf_pct = f"{round(float(leaf_p) * 100)}%" if leaf_p is not None else "—"
    if bn:
        return (
            f"মডেল ফলাফল: পাতা {leaf_pct} · ফসল {crop_name or '—'} · "
            f"রোগ {plant} — {cond} ({pct})।\n\n"
        )
    return (
        f"Model result: leaf {leaf_pct} · crop {crop_name or '—'} · "
        f"disease {plant} — {cond} ({pct}).\n\n"
    )


def _build_vision_prompt(best: dict, leaf: dict, crop: dict, lang: str, pack: dict | None) -> str:
    lang = (lang or "en").lower()
    bn = lang.startswith("bn")
    class_name = best.get("prediction") or ""
    if bn:
        system = (
            "আপনি AgroScan কৃষি সহকারী। শুধু নিচের মডেল ফলাফল ও verified guide ব্যবহার করুন। "
            "কোনো নতুন ওষুধ/ডোজ আবিষ্কার করবেন না। একই শব্দ বারবার লিখবেন না। "
            "৩–৬টি সংক্ষিপ্ত বাক্যে কৃষককে পরামর্শ দিন।"
        )
        ask = (
            "মডেল ফলাফল ও গাইড থেকে কৃষককে সহজ বাংলায় বলুন কী রোগ হতে পারে, "
            "এখন কী করবেন, এবং কখন ১৬১২৩ কল করবেন।"
        )
    else:
        system = (
            "You are AgroScan for Bangladeshi farmers. Use ONLY the scan result and verified guide. "
            "Do not invent products or doses. Do not repeat words. Write 3–6 short sentences."
        )
        ask = (
            "From the model result and guide, tell the farmer what it likely is, "
            "what to do now, and when to call 16123."
        )

    parts = [f"### Instruction:\n{system}\n"]
    parts.append(_scan_header(best, leaf, crop, lang))
    if pack:
        title = pack.get("title") or class_name
        summary = pack.get("summary") or pack.get("description") or ""
        parts.append(f"Verified guide title: {title}\n")
        if summary:
            parts.append(f"Summary: {summary}\n")
        steps = pack.get("next_steps") or []
        if steps:
            parts.append("Steps:\n")
            for i, step in enumerate(steps[:5], 1):
                if isinstance(step, dict):
                    parts.append(
                        f"{i}. {(step.get('title') or '').strip()}: {(step.get('detail') or '').strip()}\n"
                    )
                else:
                    parts.append(f"{i}. {step}\n")
        treatments = pack.get("treatment") or []
        if treatments:
            parts.append("Treatment notes:\n")
            for t in treatments[:4]:
                parts.append(f"- {t}\n")
        prevention = pack.get("prevention") or []
        if prevention:
            parts.append("Prevention:\n")
            for p in prevention[:3]:
                parts.append(f"- {p}\n")
    else:
        parts.append(f"Disease class label: {class_name}\nNo verified guide found.\n")

    parts.append(f"### Input:\n{ask}\n\n### Response:\n")
    return "".join(parts)


def _llm_text_is_bad(text: str) -> bool:
    """Detect collapsed/repetitive generations from the small local model."""
    words = [w for w in (text or "").split() if w]
    if len(words) < 12:
        return False
    from collections import Counter

    counts = Counter(w.lower().strip(".,;:!?'\"") for w in words)
    top_n = counts.most_common(1)[0][1]
    if top_n >= max(10, int(len(words) * 0.22)):
        return True
    # Long run of identical tokens
    run = 1
    for i in range(1, len(words)):
        if words[i] == words[i - 1]:
            run += 1
            if run >= 6:
                return True
        else:
            run = 1
    return False


def generate_vision_feedback(
    best: dict,
    leaf: dict,
    crop: dict,
    lang: str,
    pack: dict | None,
) -> Optional[str]:
    """Qwen narrative grounded on vision model + pack guide."""
    if not llm_configured():
        return None
    if not _ensure_loaded():
        return None
    assert _model is not None and _tokenizer is not None

    import torch

    prompt = _build_vision_prompt(best, leaf, crop, lang, pack)
    max_new = int(os.environ.get("AGROSCAN_LLM_VISION_MAX_NEW") or os.environ.get("AGROSCAN_LLM_MAX_NEW") or "180")
    inputs = _tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1800)
    try:
        model_device = next(_model.parameters()).device
    except StopIteration:
        model_device = torch.device(_device or "cpu")
    inputs = {k: v.to(model_device) for k, v in inputs.items()}

    with torch.inference_mode():
        out = _model.generate(
            **inputs,
            max_new_tokens=max_new,
            do_sample=False,
            pad_token_id=_tokenizer.pad_token_id,
            eos_token_id=_tokenizer.eos_token_id,
        )

    gen = out[0][inputs["input_ids"].shape[-1] :]
    text = _tokenizer.decode(gen, skip_special_tokens=True).strip()
    if not text:
        return None
    for stop in ("\n### ", "\n###Instruction", "\n### Input"):
        if stop in text:
            text = text.split(stop, 1)[0].strip()
    if _llm_text_is_bad(text):
        print("[AgroScan LLM] vision feedback rejected (repetitive); using pack fallback.")
        return None
    return text or None


def vision_scan_reply(predict_result: dict, lang: str = "bn") -> dict:
    """Pipeline: vision predict dict → status + farmer reply (Qwen when possible)."""
    from agroscan.knowledge import _format_pack_reply, _suggestions, advice_for

    lang = lang or "bn"
    sug_lang = "bn" if (lang or "").startswith("bn") else "en"
    bn = (lang or "").startswith("bn")

    leaf = predict_result.get("stage1_leaf_gate") or {}
    crop = predict_result.get("stage2_leaf_type") or {}
    disease = predict_result.get("stage3_disease") or predict_result.get("stage2_disease")
    best = (disease or {}).get("best_answer") or {}

    base = {
        "stage1_leaf_gate": leaf,
        "stage2_leaf_type": crop,
        "stage3_disease": disease,
        "message": predict_result.get("message"),
        "suggestions": _suggestions(sug_lang),
    }

    if leaf.get("available") is not False and leaf.get("is_leaf") is False:
        base.update(
            {
                "status": "not_leaf",
                "reply": (
                    "এই ছবিটি পাতা বলে মনে হয় না, তাই রোগ বিশ্লেষণ করা হয়নি। "
                    "একটি পাতার কাছ থেকে স্পষ্ট ছবি পাঠান।"
                    if bn
                    else "This does not look like a leaf, so disease analysis was skipped. "
                    "Please send a clear close-up of one leaf."
                ),
                "source": "vision",
            }
        )
        return base

    if crop.get("needs_user_pick") and not crop.get("user_selected"):
        options = []
        for item in (crop.get("top3") or [])[:3]:
            options.append(
                {
                    "label": item.get("crop") or "",
                    "crop": item.get("crop") or "",
                    "confidence": item.get("confidence"),
                }
            )
        base.update(
            {
                "status": "need_crop",
                "reply": (
                    "ফসল চেনার আত্মবিশ্বাস কম। নিচ থেকে সঠিক ফসল বেছে নিন, "
                    "তারপর পরামর্শ দেওয়া হবে।"
                    if bn
                    else "Crop confidence is low. Pick the correct crop below, then advice will continue."
                ),
                "options": options,
                "source": "vision",
            }
        )
        return base

    if not best.get("prediction"):
        base.update(
            {
                "status": "no_disease",
                "reply": predict_result.get("message")
                or (
                    "রোগ নির্ণয় করা যায়নি। আরেকটি স্পষ্ট পাতার ছবি চেষ্টা করুন।"
                    if bn
                    else "Could not diagnose a disease. Try another clear leaf photo."
                ),
                "source": "vision",
            }
        )
        return base

    class_name = best["prediction"]
    pack = advice_for(class_name, sug_lang) or None
    header = _scan_header(best, leaf, crop, lang)

    llm_text = None
    try:
        llm_text = generate_vision_feedback(best, leaf, crop, lang, pack)
    except Exception as exc:
        print(f"[AgroScan LLM] vision feedback failed: {exc}")
        llm_text = None

    if llm_text:
        reply = header + llm_text
        source = "vision+llm"
    elif pack:
        reply = header + _format_pack_reply(pack, lang)
        source = "vision+pack"
    else:
        plant = best.get("plant") or ""
        cond = best.get("condition") or class_name
        conf = best.get("confidence")
        pct = f"{round(float(conf) * 100)}%" if conf is not None else "—"
        reply = header + (
            f"সম্ভাব্য রোগ: {plant} — {cond} (আত্মবিশ্বাস {pct})। "
            "বিস্তারিত চিকিৎসার জন্য ১৬১২৩ কল করুন।"
            if bn
            else f"Likely: {plant} — {cond} (confidence {pct}). "
            "For detailed treatment, call 16123."
        )
        source = "vision"

    base.update(
        {
            "status": "ok",
            "reply": reply,
            "source": source,
            "class_name": class_name,
            "matched_key": (pack or {}).get("matched_key") if pack else class_name,
            "suggestions": [
                "কীভাবে চিকিৎসা করব?" if bn else "How do I treat this?",
                "কোন স্প্রে নিরাপদ?" if bn else "Which spray is safer?",
                "কীভাবে প্রতিরোধ করব?" if bn else "How can I prevent it?",
            ]
            + (base.get("suggestions") or [])[:2],
        }
    )
    return base
