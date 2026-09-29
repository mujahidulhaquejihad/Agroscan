"""AgroScan chat: pack/KB first, then RAG + local Gemma (Gemini optional).

Local Gemma 2 9B Instruct generates RAG answers when AGROSCAN_LLM_LOCAL=1.
Gemini stays off unless AGROSCAN_GEMINI=1. Never attach a Qwen adapter to Gemma.

Env:
  AGROSCAN_GEMINI          1 to use Gemini; default 0 (off)
  GEMINI_API_KEY           Google AI Studio key (unused while Gemini is off)
  AGROSCAN_GEMINI_MODEL    default gemini-flash-latest
  AGROSCAN_LLM_ENABLED     auto|1|0   default auto (Gemini on, or CUDA)
  AGROSCAN_LLM_LOCAL       1 to load local Gemma/Qwen on GPU
  AGROSCAN_LLM_BASE        HuggingFace id (default google/gemma-2-9b-it)
  AGROSCAN_LLM_ADAPTER     Qwen LoRA dir only (ignored on Gemma)
  AGROSCAN_LLM_MAX_NEW     max new tokens (default 1024)
  AGROSCAN_LLM_DEVICE      cuda|cpu|auto
  AGROSCAN_LLM_PRELOAD     1 to load the local model at startup
  AGROSCAN_LLM_4BIT        auto|1|0   default auto (4-bit on CUDA)
  HF_TOKEN                 HuggingFace token (Gemma is a gated model)
"""
from __future__ import annotations

import base64
import gc
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from . import config

config.load_dotenv()

DEFAULT_ADAPTER = config.LLM_ADAPTERS / "agroscan-3b"
DEFAULT_BASE = "google/gemma-2-9b-it"
DEFAULT_GEMINI_MODELS = (
    "gemini-flash-latest",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
)
STT_GEMINI_MODELS = (
    "gemini-3.5-flash",
    "gemini-flash-latest",
)

_lock = threading.Lock()
_model = None
_tokenizer = None
_load_error: Optional[str] = None
_device: Optional[str] = None
_disabled: bool = False
_using_adapter: Optional[str] = None
_quant: Optional[str] = None
_gemini_model: Optional[str] = None
_gemini_dead: set[str] = set()


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


def _gemini_key() -> str:
    return (
        (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_GENAI_API_KEY") or "")
        .strip()
    )


def _gemini_enabled() -> bool:
    """Gemini is opt-in. Default off even if GEMINI_API_KEY is present."""
    if _env_flag("AGROSCAN_GEMINI", "0") in ("0", "false", "off", "no"):
        return False
    return bool(_gemini_key())


def _want_local_llm() -> bool:
    return _env_flag("AGROSCAN_LLM_LOCAL", "0") in ("1", "true", "on", "yes")


def _local_base_id() -> str:
    return (os.environ.get("AGROSCAN_LLM_BASE") or DEFAULT_BASE).strip()


def _local_provider() -> str:
    base = _local_base_id().lower()
    if "gemma" in base:
        return "gemma"
    if "qwen" in base:
        return "qwen"
    return "local"


def llm_configured() -> bool:
    if _disabled:
        return False
    flag = _env_flag("AGROSCAN_LLM_ENABLED", "auto")
    if flag in ("0", "false", "off", "no"):
        return False
    if _gemini_enabled():
        return True
    if flag in ("1", "true", "on", "yes"):
        return True
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def llm_status() -> dict:
    adapter = _adapter_path()
    gemini = _gemini_enabled()
    local_on = _want_local_llm() or _model is not None
    return {
        "enabled": llm_configured(),
        "loaded": _model is not None or (gemini and not local_on),
        "load_error": _load_error,
        "disabled": _disabled,
        "adapter": str(adapter) if adapter and "qwen" in _local_base_id().lower() else None,
        "base_model": (
            (_gemini_model or os.environ.get("AGROSCAN_GEMINI_MODEL") or DEFAULT_GEMINI_MODELS[0])
            if gemini and not local_on
            else _local_base_id()
        ),
        "provider": "gemini" if gemini and not local_on else (_local_provider() if local_on else None),
        "device": "api" if gemini and not local_on else _device,
        "quant": _quant,
        "rag": True,
        "gemini": gemini,
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
    from agroscan.knowledge import _APP_HOWTO_RE, wants_catalog

    if _APP_HOWTO_RE.search(message or "") or wants_catalog(message or ""):
        return True
    return False


def _kb_is_generic(reply: str, lang: str) -> bool:
    r = (reply or "").lower()
    if (lang or "").startswith("bn"):
        return "আমি পাতার রোগ" in r or "যেমন জিজ্ঞাসা" in r
    return "i can help with plant-leaf" in r or "try asking" in r


def _relevant_context(message: str, context_disease: Optional[str]) -> Optional[str]:
    """Drop last-scan pinning when the farmer names a different crop."""
    if not context_disease:
        return None
    msg = (message or "").lower()
    if not msg:
        return context_disease
    ctx = context_disease.lower()
    try:
        from agroscan.bd_data import treatments

        recs = treatments()
    except Exception:
        return context_disease
    scan_crops = set()
    for rec in recs:
        cn = str(rec.get("class_name") or "").lower()
        if cn and (cn == ctx or ctx in cn or cn in ctx):
            for c in (rec.get("crop_en"), rec.get("crop_bn")):
                c = str(c or "").lower().strip()
                if c:
                    scan_crops.add(c)
    if not scan_crops:
        return context_disease
    for rec in recs:
        crop_en = str(rec.get("crop_en") or "").lower().strip()
        crop_bn = str(rec.get("crop_bn") or "").lower().strip()
        mentioned = (len(crop_en) >= 3 and crop_en in msg) or (
            len(crop_bn) >= 2 and crop_bn in msg
        )
        if not mentioned:
            continue
        if crop_en in scan_crops or crop_bn in scan_crops:
            continue
        return None
    return context_disease


_BANGLISH_RE = re.compile(
    r"\b(ki|kon|kemon|korte|parbe|parbo|parben|rog|dhan|dhaner|alu|alur|"
    r"gach|pata|osudh?|oshudh?|chikitsa|kivabe|apni|amake|kothay|kothai|"
    r"korbo|korben|lagbe|naki|bhai|vai|sprei|blaste|dhosa|dhvosa)\b",
    re.I,
)


HISTORY_MAX_TURNS = 8
HISTORY_MAX_CHARS = 1200
DEFAULT_MAX_NEW = 1024


def _sanitize_history(history, current_message: str) -> list:
    """Keep the last few user/assistant turns. Drop a duplicate of the live message."""
    if not history:
        return []
    out: list[dict] = []
    current = (current_message or "").strip()
    for turn in history:
        if isinstance(turn, dict):
            role = str(turn.get("role") or "").strip().lower()
            content = str(turn.get("content") or "").strip()
        else:
            role = str(getattr(turn, "role", "") or "").strip().lower()
            content = str(getattr(turn, "content", "") or "").strip()
        if role in ("assistant", "model", "bot"):
            role = "assistant"
        elif role != "user":
            continue
        if not content:
            continue
        if len(content) > HISTORY_MAX_CHARS:
            content = content[:HISTORY_MAX_CHARS]
        out.append({"role": role, "content": content})
    if out and out[-1]["role"] == "user" and current and out[-1]["content"] == current:
        out.pop()
    return out[-HISTORY_MAX_TURNS:]


def _pack_keys(pack: Optional[dict], context_disease: Optional[str]) -> Optional[set]:
    keys = set()
    if pack:
        keys.update((pack.get("matched_key"), pack.get("class_name")))
    elif context_disease:
        keys.add(context_disease)
    keys = {k for k in keys if k}
    return keys or None


def _llm_looks_unsure(text: str) -> bool:
    """True when Gemini refused instead of using a matched guide."""
    raw = (text or "").strip()
    if not raw:
        return True
    t = raw.lower()
    hedge = (
        "i am unsure",
        "i'm unsure",
        "i am not sure",
        "i'm not sure",
        "do not have enough",
        "don't have enough",
        "not covered",
        "cannot answer",
        "can't answer",
        "no retrieved",
        "guides do not",
        "guides don't",
        "retrieved guides: none",
        "অনিশ্চিত",
        "নিশ্চিত নই",
        "পর্যাপ্ত তথ্য নেই",
        "গাইডে নেই",
        "গাইডে এই",
    )
    if not any(h in t for h in hedge):
        return False
    if any(
        x in t
        for x in (
            "spray",
            "স্প্রে",
            "মিলি",
            " ml",
            "g/",
            "গ্রাম",
            "dose",
            "ডোজ",
            "tricyclazole",
            "mancozeb",
            "urea",
            "ইউরিয়া",
        )
    ):
        return False
    return True


def _gemini_contents(messages: list) -> tuple[str, list]:
    """Split chat messages into Gemini systemInstruction + alternating contents."""
    system = ""
    contents: list[dict] = []
    for m in messages:
        role = str((m or {}).get("role") or "").lower()
        text = str((m or {}).get("content") or "").strip()
        if not text:
            continue
        if role == "system":
            system = text if not system else system + "\n" + text
            continue
        grole = "user" if role == "user" else "model"
        if contents and contents[-1]["role"] == grole:
            contents[-1]["parts"][0]["text"] += "\n" + text
        else:
            contents.append({"role": grole, "parts": [{"text": text}]})
    if contents and contents[0]["role"] != "user":
        contents.insert(0, {"role": "user", "parts": [{"text": "(continued)"}]})
    return system, contents


def _reply_lang(message: str, lang: str) -> str:
    """Answer language from the farmer's text, not only the UI toggle.

    Banglish (Latin letters) must still get Bangla-script replies.
    """
    text = message or ""
    if re.search(r"[\u0980-\u09FF]", text):
        return "bn"
    if re.search(r"\bki\s+ki\b|\bkorte\s+par|\bkon\s+kon\b", text, re.I):
        return "bn"
    if len(_BANGLISH_RE.findall(text)) >= 2:
        return "bn"
    if (lang or "").lower().startswith("bn"):
        return "bn"
    return "en"


def _build_chat_messages(
    message: str,
    context_disease: Optional[str],
    lang: str,
    location: Optional[dict] = None,
    history: Optional[list] = None,
) -> list:
    from agroscan.knowledge import (
        _format_pack_reply,
        advice_for,
        pack_catalog_reply,
        resolve_disease_query,
        wants_catalog,
    )
    from agroscan.rag import retrieve

    lang = _reply_lang(message, lang)
    context_disease = _relevant_context(message, context_disease)
    prior = _sanitize_history(history, message)
    if lang.startswith("bn"):
        system = (
            "আপনি AgroScan কৃষি সহকারী। কৃষকের যেকোনো প্রশ্নের উত্তর দিন। "
            "উত্তর সবসময় বাংলা লিপিতে লিখুন (বাংলা অক্ষর), ইংরেজি বাক্য নয়। "
            "কৃষক ব্যাংলিশে (ইংরেজি অক্ষরে) লিখলেও আপনি বাংলায় উত্তর দেবেন। "
            "ওষুধের ব্র্যান্ড নাম ল্যাটিন অক্ষরে রাখতে পারেন (যেমন Mancozeb, Trooper)। "
            "রোগের চিকিৎসা, স্প্রে, ব্র্যান্ড ও ডোজ শুধু নিচের retrieved guide, matched record, বা coverage list থেকে বলুন — "
            "না থাকলে অনিশ্চিত বলুন ও ১৬১২৩ কল করতে বলুন। "
            "সার রাখা, আবহাওয়া, রোপণের সময় — এসব সাধারণ চাষাবাদে বাংলাদেশের কৃষি সম্প্রসারণ জ্ঞান ব্যবহার করতে পারেন; "
            "নতুন কীটনাশকের নাম বা ডোজ আবিষ্কার করবেন না। "
            "প্রশ্নের সাথে মিলছে না এমন guide কপি করবেন না। "
            "সংক্ষিপ্ত ফলো-আপ (ডোজ, স্প্রে, প্রতিরোধ) আগের রোগ ও কথোপকথন ধরে উত্তর দিন। "
            "উত্তর শেষ করুন; বাক্য মাঝপথে কাটবেন না।"
        )
    else:
        system = (
            "You are AgroScan, an agriculture assistant for Bangladeshi farmers. "
            "Answer in English. If the farmer writes in Bangla or Banglish, answer in Bangla script instead. "
            "For disease treatment, sprays, product brands, and doses, use ONLY the retrieved guides, matched record, or coverage list below. "
            "If those do not cover a pesticide/dose question, say you are unsure and suggest calling 16123. "
            "For general farm practice (fertilizer storage, weather, planting time) you may use standard Bangladesh extension knowledge. "
            "Do not invent pesticide brands, doses, or disease symptoms. "
            "Ignore retrieved guides that do not match the question. "
            "Short follow-ups (dose, spray, prevention) refer to the pinned disease and earlier turns. "
            "Finish the answer; do not stop mid-sentence."
        )

    parts: list[str] = []
    loc = location or {}
    area = ", ".join(
        str(x).strip() for x in (loc.get("upazila"), loc.get("district")) if x and str(x).strip()
    )
    if area:
        parts.append(f"Farmer area (Bangladesh): {area}. Prefer local crop/season advice when relevant.\n")

    query = resolve_disease_query(message, "bn" if lang.startswith("bn") else "en")
    pack = query.get("info") if query.get("status") == "matched" else None
    allow_keys = _pack_keys(pack, context_disease)
    meta = wants_catalog(message) or _structural_intent(message)
    pack_lang = "bn" if lang.startswith("bn") else "en"
    if pack:
        parts.append("Matched disease record (authoritative):\n")
        parts.append(_format_pack_reply(pack, pack_lang))
        parts.append("\n")
    elif context_disease:
        info = advice_for(context_disease, pack_lang)
        if info:
            parts.append("Recent leaf scan (authoritative for follow-ups):\n")
            parts.append(_format_pack_reply(info, pack_lang))
            parts.append("\n")
        else:
            parts.append(f"Recent leaf scan class: {context_disease}\n")

    if wants_catalog(message):
        cat = pack_catalog_reply("diseases list", lang)
        if cat and cat.get("reply"):
            parts.append("Coverage list (verified treatment pages):\n")
            parts.append(cat["reply"])
            parts.append("\n")

    extra_bits = [context_disease or ""]
    if pack:
        extra_bits.append(str(pack.get("title") or ""))
        extra_bits.append(str(pack.get("class_name") or ""))
    for turn in reversed(prior):
        if turn.get("role") == "user" and turn.get("content"):
            extra_bits.append(turn["content"][:400])
            break
    extra = " ".join(b for b in extra_bits if b).strip() or None

    snippets: list[str] = []
    if pack:
        snippets = []
    elif not (meta and not pack):
        snippets = retrieve(
            message,
            lang=lang,
            k=4,
            extra=extra,
            allow_keys=allow_keys,
        )
    if snippets:
        parts.append("Retrieved guides:\n")
        for i, snip in enumerate(snippets, 1):
            parts.append(f"[{i}]\n{snip}\n\n")
    else:
        parts.append("Retrieved guides: none.\n")

    parts.append(f"Farmer question:\n{(message or '').strip()}")
    if lang.startswith("bn"):
        parts.append("\n\nReply in Bangla script (বাংলা) only.")
    out = [{"role": "system", "content": system}]
    out.extend(prior)
    out.append({"role": "user", "content": "".join(parts)})
    return out


def _fold_system_into_user(messages: list) -> list:
    """Gemma-2 chat templates have no system role — fold it into the user turn."""
    if not messages or messages[0].get("role") != "system":
        return messages
    sys = messages[0].get("content") or ""
    rest = list(messages[1:])
    if rest and rest[0].get("role") == "user":
        rest[0] = {
            "role": "user",
            "content": (sys + "\n\n" + (rest[0].get("content") or "")).strip(),
        }
        return rest
    return [{"role": "user", "content": sys}] + rest


def _to_chat_prompt(tokenizer, messages: list) -> str:
    name = str(getattr(tokenizer, "name_or_path", "") or "").lower()
    if "gemma" in name or "gemma" in _local_base_id().lower():
        messages = _fold_system_into_user(messages)
    try:
        return tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    except Exception:
        sys = messages[0]["content"] if messages else ""
        user = messages[-1]["content"] if messages else ""
        return f"### Instruction:\n{sys}\n\n### Input:\n{user}\n\n### Response:\n"


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
    if _gemini_enabled() and not _want_local_llm():
        return False
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

            base_id = _local_base_id()
            adapter = _adapter_path()
            if adapter and "qwen" not in base_id.lower():
                print(
                    f"[AgroScan LLM] Skipping adapter {adapter} — not for {base_id}."
                )
                adapter = None
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
                print("[AgroScan LLM] No adapter attached; using instruct base.")

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
    if _gemini_enabled() and not _want_local_llm():
        print("[AgroScan LLM] Gemini on — RAG generation uses Gemini, local model not preloaded.")
        return llm_status()
    if not _want_local_llm():
        return llm_status()
    _ensure_loaded()
    return llm_status()


def _generate_text(prompt: str, max_new: int, max_length: int = 2048) -> Optional[str]:
    import torch

    assert _model is not None and _tokenizer is not None
    inputs = _tokenizer(prompt, return_tensors="pt", truncation=True, max_length=max_length)
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
    for stop in ("\n### ", "\n###Instruction", "\n### Input", "<|im_end|>", "<end_of_turn>"):
        if stop in text:
            text = text.split(stop, 1)[0].strip()
    return text or None


def _gemini_models() -> list:
    preferred = (os.environ.get("AGROSCAN_GEMINI_MODEL") or "").strip()
    out = []
    if preferred:
        out.append(preferred)
    for m in DEFAULT_GEMINI_MODELS:
        if m not in out:
            out.append(m)
    live = [m for m in out if m not in _gemini_dead]
    return live or out


def _gemini_extract_text(data: dict) -> Optional[str]:
    text, _reason = _gemini_extract(data)
    return text


def _gemini_extract(data: dict) -> tuple[Optional[str], str]:
    cands = data.get("candidates") or []
    if not cands:
        return None, ""
    c0 = cands[0] or {}
    reason = str(c0.get("finishReason") or "")
    parts = ((c0.get("content") or {}).get("parts") or [])
    text = "".join(str(p.get("text") or "") for p in parts).strip()
    return (text or None), reason


def _gemini_http(url: str, body: bytes, headers: dict, timeout: int = 45) -> tuple[Optional[dict], Optional[str], Optional[int]]:
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")), None, 200
    except urllib.error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            pass
        return None, f"HTTP {exc.code}: {err_body or exc.reason}", exc.code
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}", None


def _gemini_generate(messages: list, max_new: int) -> Optional[str]:
    """Generate from RAG chat messages via Gemini REST (stdlib only)."""
    global _gemini_model, _load_error
    key = _gemini_key()
    if not key:
        return None
    system, contents = _gemini_contents(messages)
    if not contents:
        return None
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.15,
            "maxOutputTokens": int(max_new),
        },
    }
    last_err = None
    models = _gemini_models()
    if _gemini_model:
        models = [_gemini_model] + [m for m in models if m != _gemini_model]
    for model in models:
        if not model:
            continue
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        attempts = (
            {"Content-Type": "application/json", "x-goog-api-key": key},
            None,  # query-string key (classic AI Studio)
        )
        for headers in attempts:
            req_url = url if headers else f"{url}?key={urllib.parse.quote(key)}"
            req_headers = headers or {"Content-Type": "application/json"}
            busy = False
            for try_n in (0, 1):
                body = json.dumps(payload).encode("utf-8")
                data, err, code = _gemini_http(req_url, body, req_headers)
                if err:
                    last_err = f"{err} {model}"
                    if key:
                        last_err = last_err.replace(key, "[redacted]")
                    if code == 404:
                        _gemini_dead.add(model)
                    if code in (429, 503) and try_n == 0:
                        busy = True
                        time.sleep(1.5)
                        continue
                    break
                text, reason = _gemini_extract(data or {})
                if not text:
                    last_err = f"{model}: empty/blocked response"
                    break
                _gemini_model = model
                _load_error = None
                if reason == "MAX_TOKENS":
                    cont = list(contents)
                    cont.append({"role": "model", "parts": [{"text": text}]})
                    cont.append(
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": "Continue from where you stopped. Do not repeat. Finish the answer."
                                }
                            ],
                        }
                    )
                    more_payload = dict(payload)
                    more_payload["contents"] = cont
                    more_body = json.dumps(more_payload).encode("utf-8")
                    more_data, more_err, _code = _gemini_http(req_url, more_body, req_headers)
                    if more_err:
                        print(f"[AgroScan LLM] Gemini continue failed: {more_err}")
                    else:
                        more_text, _more_reason = _gemini_extract(more_data or {})
                        if more_text:
                            text = (text.rstrip() + "\n" + more_text.lstrip()).strip()
                return text
            if busy:
                break  # next model, not the other auth header
    if last_err:
        _load_error = last_err
        print(f"[AgroScan LLM] Gemini generate failed: {last_err}")
    return None


def generate_reply(
    message: str,
    context_disease: Optional[str] = None,
    lang: str = "bn",
    location: Optional[dict] = None,
    history: Optional[list] = None,
) -> Optional[str]:
    """Return generated text, or None if LLM unavailable / empty."""
    if not llm_configured():
        return None
    messages = _build_chat_messages(
        message, context_disease, lang, location=location, history=history
    )
    max_new = int(os.environ.get("AGROSCAN_LLM_MAX_NEW") or str(DEFAULT_MAX_NEW))
    if _want_local_llm() and _ensure_loaded():
        assert _model is not None and _tokenizer is not None
        prompt = _to_chat_prompt(_tokenizer, messages)
        return _generate_text(prompt, max_new)
    if _gemini_enabled():
        return _gemini_generate(messages, max_new)
    return None


_BN_CHAR_RE = re.compile(r"[\u0980-\u09FF]")


def transcribe_audio(audio: bytes, mime: str = "audio/wav", lang: str = "bn") -> Optional[str]:
    """Speech-to-text via Gemini. Bangla UI → Bangla script, not Latin gibberish."""
    global _gemini_model
    key = _gemini_key()
    if not key or not audio:
        return None
    mime = (mime or "audio/wav").split(";")[0].strip().lower() or "audio/wav"
    if mime in ("audio/x-wav", "audio/wave"):
        mime = "audio/wav"
    if mime not in ("audio/wav", "audio/mpeg", "audio/mp3", "audio/mp4", "audio/aac", "audio/ogg", "audio/flac", "audio/webm"):
        mime = "audio/wav"
    want_bn = (lang or "").lower().startswith("bn")
    if want_bn:
        prompts = (
            (
                "You are transcribing a Bangladeshi farmer speaking Bangla (বাংলা). "
                "Write ONLY in Bengali script (Unicode বাংলা অক্ষর). "
                "Do not romanize. Do not invent English sentences from similar sounds. "
                "English crop/chemical names (potato, rice, blast, urea) may stay in English. "
                "Return only the transcript."
            ),
            (
                "Wrong: Latin/English gibberish. The speaker used Bangla. "
                "Transcribe again in বাংলা হরফ only. Transcript only."
            ),
        )
    else:
        prompts = (
            (
                "Transcribe this farmer. If they spoke Bangla, use Bengali script. "
                "If they spoke English, use English. Transcript only."
            ),
        )
    b64 = base64.b64encode(audio).decode("ascii")
    models = [m for m in STT_GEMINI_MODELS if m not in _gemini_dead]
    if not models:
        models = list(STT_GEMINI_MODELS)
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}

    def _once(prompt: str) -> Optional[str]:
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inlineData": {"mimeType": mime, "data": b64}},
                ],
            }],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 512},
        }
        body = json.dumps(payload).encode("utf-8")
        for model in models:
            if not model:
                continue
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent"
            )
            data, err, code = _gemini_http(url, body, headers, timeout=25)
            if err:
                if code == 404:
                    _gemini_dead.add(model)
                continue
            text, _reason = _gemini_extract(data or {})
            if not text:
                continue
            text = text.strip().strip('"').strip("'")
            low = text.lower()
            for prefix in ("transcript:", "transcription:"):
                if low.startswith(prefix):
                    text = text.split(":", 1)[1].strip()
                    break
            if low in ("none", "n/a", "[none]", "(none)"):
                return None
            return text or None
        return None

    last = None
    for prompt in prompts:
        text = _once(prompt)
        if not text:
            continue
        last = text
        if want_bn and not _BN_CHAR_RE.search(text):
            continue
        return text
    if last and want_bn and len(_BANGLISH_RE.findall(last)) >= 2:
        return last
    return last if last and not want_bn else None


def chat_reply(
    message: str,
    context_disease: Optional[str] = None,
    lang: str = "bn",
    confirm_class: Optional[str] = None,
    location: Optional[dict] = None,
    history: Optional[list] = None,
) -> dict:
    """Gemini + RAG when enabled; pack/KB fallback otherwise."""
    from agroscan.knowledge import (
        _format_pack_reply,
        _suggestions,
        chatbot_reply,
        pack_catalog_reply,
        resolve_disease_query,
    )

    lang = lang or "en"
    sug_lang = "bn" if (lang or "").startswith("bn") else "en"
    context_disease = _relevant_context(message, context_disease)
    suggestions = _suggestions(sug_lang)

    query = resolve_disease_query(message, lang, confirm_class=confirm_class)
    if query.get("status") == "clarify":
        return {
            "reply": query["reply"],
            "suggestions": query.get("suggestions") or [],
            "options": query.get("options") or [],
            "source": "clarify",
        }

    kb = chatbot_reply(message, context_disease, lang, confirm_class=confirm_class)
    pack = query.get("info") if query.get("status") == "matched" else None

    catalog = pack_catalog_reply(message, lang)
    if catalog:
        return catalog

    if kb.get("source") in ("clarify", "catalog"):
        return kb
    if _structural_intent(message):
        kb["source"] = kb.get("source") or "kb"
        return kb

    if pack:
        return {
            "reply": _format_pack_reply(pack, lang),
            "suggestions": suggestions,
            "source": "pack",
            "matched_key": pack.get("matched_key"),
            "class_name": pack.get("class_name"),
        }
    if kb.get("source") in ("pack", "context"):
        return kb

    if (message or "").strip() and llm_configured() and _gemini_enabled() and not _want_local_llm():
        try:
            llm_text = generate_reply(
                message, context_disease, lang, location=location, history=history
            )
        except Exception as exc:
            print(f"[AgroScan LLM] Gemini RAG failed: {exc}")
            llm_text = None
        if llm_text and not _llm_text_is_bad(llm_text):
            out = {
                "reply": llm_text,
                "suggestions": kb.get("suggestions") or suggestions,
                "source": "gemini+rag",
            }
            if context_disease:
                out["class_name"] = context_disease
            return out
        print("[AgroScan LLM] Gemini empty/rejected; using pack/KB fallback.")

    if not _gemini_enabled() and not _kb_is_generic(kb.get("reply") or "", lang):
        kb["source"] = "kb"
        return kb

    if _want_local_llm():
        try:
            llm_text = generate_reply(
                message, context_disease, lang, location=location, history=history
            )
        except Exception as exc:
            print(f"[AgroScan LLM] generate failed: {exc}")
            llm_text = None
        if llm_text and not _llm_text_is_bad(llm_text):
            return {
                "reply": llm_text,
                "suggestions": kb.get("suggestions") or [],
                "source": "llm",
            }

    kb["source"] = kb.get("source") or "kb"
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


def _build_vision_messages(best: dict, leaf: dict, crop: dict, lang: str, pack: dict | None) -> list:
    lang = (lang or "en").lower()
    bn = lang.startswith("bn")
    class_name = best.get("prediction") or ""
    if bn:
        system = (
            "আপনি AgroScan কৃষি সহকারী। শুধু নিচের মডেল ফলাফল ও verified guide ব্যবহার করুন। "
            "কোনো নতুন ওষুধ/ডোজ আবিষ্কার করবেন না। একই শব্দ বারবার লিখবেন না। "
            "'Section:' হেডার কপি করবেন না। ৩–৬টি সংক্ষিপ্ত বাক্যে কৃষককে পরামর্শ দিন।"
        )
        ask = (
            "মডেল ফলাফল ও গাইড থেকে কৃষককে সহজ বাংলায় বলুন কী রোগ হতে পারে, "
            "এখন কী করবেন, এবং কখন ১৬১২৩ কল করবেন।"
        )
    else:
        system = (
            "You are AgroScan for Bangladeshi farmers. Use ONLY the scan result and verified guide. "
            "Do not invent products or doses. Do not repeat words. "
            "Do not copy headers like 'Section:'. Write 3–6 short sentences."
        )
        ask = (
            "From the model result and guide, tell the farmer what it likely is, "
            "what to do now, and when to call 16123."
        )

    parts = [_scan_header(best, leaf, crop, lang)]
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

    parts.append(ask)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "".join(parts)},
    ]


def _llm_text_is_bad(text: str) -> bool:
    """Detect collapsed/repetitive generations and raw RAG dumps."""
    raw = text or ""
    head = raw[:280].lower()
    if "section:" in head or "treatment plan for" in head or "chemical option" in head:
        return True
    if "\ufffd" in raw:
        return True
    words = [w for w in raw.split() if w]
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
    """Narrative grounded on vision model + pack guide (Gemma, else Gemini)."""
    if not llm_configured():
        return None
    messages = _build_vision_messages(best, leaf, crop, lang, pack)
    max_new = int(os.environ.get("AGROSCAN_LLM_VISION_MAX_NEW") or os.environ.get("AGROSCAN_LLM_MAX_NEW") or "512")
    if _want_local_llm() and _ensure_loaded():
        assert _model is not None and _tokenizer is not None
        prompt = _to_chat_prompt(_tokenizer, messages)
        text = _generate_text(prompt, max_new, max_length=1800)
    elif _gemini_enabled():
        text = _gemini_generate(messages, max_new)
    else:
        text = None
    if text and _llm_text_is_bad(text):
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
        for item in crop.get("top3") or []:
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
                    "তালিকায় না থাকলে অন্যান্য চাপুন।"
                    if bn
                    else "Crop confidence is low. Pick the correct crop below, "
                    "or Other if this plant is not in the list."
                ),
                "options": options,
                "source": "vision",
            }
        )
        return base

    from agroscan.label_map import is_other_crop

    if is_other_crop(crop.get("crop")):
        base.update(
            {
                "status": "unsupported_crop",
                "reply": predict_result.get("message")
                or (
                    "এই গাছ AgroScan-এর প্রশিক্ষিত ফসলের তালিকায় নেই, "
                    "তাই রোগ বিশ্লেষণ করা হয়নি।"
                    if bn
                    else "This plant is not in AgroScan's trained crops, "
                    "so disease diagnosis was skipped."
                ),
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
    if not pack:
        try:
            llm_text = generate_vision_feedback(best, leaf, crop, lang, pack)
        except Exception as exc:
            print(f"[AgroScan LLM] vision feedback failed: {exc}")
            llm_text = None

    if llm_text:
        reply = header + llm_text
        source = "vision+gemini" if _gemini_enabled() else "vision+llm"
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
