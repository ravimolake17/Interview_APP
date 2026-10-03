"""Text-to-speech for Agent 4.

Engines:
  - edge   — Microsoft Edge neural TTS (en-IN). Seconds per clip. Best on CPU.
  - parler — AI4Bharat Indic Parler-TTS. Needs NVIDIA CUDA to be practical.
  - auto   — parler when CUDA is available, otherwise edge.

Public API (synthesize_speech → audio bytes) is unchanged for the rest of the app.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from dotenv import load_dotenv

# Ensure HF_TOKEN / TTS_* from backend/.env are visible via os.getenv.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

logger = logging.getLogger(__name__)

MODEL_ID = (os.getenv("PARLER_TTS_MODEL") or "ai4bharat/indic-parler-tts").strip()
TTS_MODEL = MODEL_ID
TTS_PROVIDER = "indic_parler_tts"
TTS_VOICE = (os.getenv("PARLER_TTS_VOICE") or "female").strip().lower() or "female"
PARLER_SAMPLE_RATE_FALLBACK = 22050

# ~86 audio codes ≈ 1 second of Parler audio (DAC frame rate).
_PARLER_CODES_PER_SECOND = 86
# Cap spoken length so CPU does not generate multi-minute clips for long questions.
_PARLER_MAX_AUDIO_SECONDS = float(os.getenv("PARLER_TTS_MAX_AUDIO_SECONDS") or "25")
_PARLER_MAX_CHARS = int(os.getenv("PARLER_TTS_MAX_CHARS") or "420")

_EDGE_VOICES = {
    "female": (os.getenv("EDGE_TTS_VOICE_FEMALE") or "en-IN-NeerjaNeural").strip(),
    "male": (os.getenv("EDGE_TTS_VOICE_MALE") or "en-IN-PrabhatNeural").strip(),
}

# Logical voice → Indic Parler speaker description (Indian English interviewers).
_VOICE_DESCRIPTIONS: dict[str, str] = {
    "female": (
        "Mary speaks with a clear Indian English accent at a moderate pace and pitch. "
        "Her tone is professional, slightly expressive, and warm. "
        "The recording is of very high quality with very clear audio."
    ),
    "male": (
        "Thoma speaks with a clear Indian English accent at a moderate pace and pitch. "
        "His tone is professional, slightly expressive, and calm. "
        "The recording is of very high quality with very clear audio."
    ),
}

_model = None
_tokenizer = None
_description_tokenizer = None
_device: str | None = None
_dtype = None
_loaded_model_id: str | None = None
_lock = threading.Lock()
_warmup_done = False


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def resolve_engine() -> str:
    """Pick TTS engine: auto | edge | parler."""
    raw = (os.getenv("TTS_ENGINE") or "auto").strip().lower() or "auto"
    if raw in {"edge", "edge_tts", "microsoft"}:
        return "edge"
    if raw in {"parler", "indic_parler", "indic-parler-tts"}:
        return "parler"
    # auto
    return "parler" if _cuda_available() else "edge"


def tts_available() -> bool:
    engine = resolve_engine()
    if engine == "edge":
        try:
            import edge_tts  # noqa: F401

            return True
        except ImportError:
            return False
    try:
        import torch  # noqa: F401
        from parler_tts import ParlerTTSForConditionalGeneration  # noqa: F401
        from transformers import AutoTokenizer  # noqa: F401

        return True
    except ImportError:
        return False


def _hf_token() -> str | None:
    token = (
        os.getenv("HF_TOKEN")
        or os.getenv("HUGGINGFACE_HUB_TOKEN")
        or os.getenv("HUGGING_FACE_HUB_TOKEN")
        or ""
    ).strip()
    return token or None


def _resolve_device() -> str:
    forced = (os.getenv("PARLER_TTS_DEVICE") or "").strip().lower()
    if forced in {"cpu", "cuda"}:
        return forced
    return "cuda" if _cuda_available() else "cpu"


def _humanize_script(text: str) -> str:
    """Make text read more like natural spoken interview language."""
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned:
        return cleaned

    replacements = [
        (r"\be\.g\.", "for example"),
        (r"\bi\.e\.", "that is"),
        (r"\bAI/ML\b", "A I M L"),
        (r"\bAI\b", "A I"),
        (r"\bML\b", "M L"),
        (r"\bJD\b", "job description"),
        (r"\bAPI\b", "A P I"),
        (r"\bSQL\b", "sequel"),
        (r"\bC\+\+\b", "C plus plus"),
        (r"\b\.NET\b", "dot net"),
        (r"—", ", "),
        (r"–", ", "),
        (r"\s*/\s*", " or "),
    ]
    for pattern, repl in replacements:
        cleaned = re.sub(pattern, repl, cleaned, flags=re.IGNORECASE)

    if cleaned[-1] not in ".?!":
        cleaned += "."

    cleaned = re.sub(r"\s*;\s*", ", ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def _truncate_for_parler(text: str) -> str:
    """Keep Parler prompts short — generation time scales with spoken duration."""
    if len(text) <= _PARLER_MAX_CHARS:
        return text
    cut = text[:_PARLER_MAX_CHARS]
    # Prefer ending on a sentence boundary.
    for sep in (". ", "? ", "! "):
        idx = cut.rfind(sep)
        if idx >= int(_PARLER_MAX_CHARS * 0.55):
            return cut[: idx + 1].strip()
    return cut.rsplit(" ", 1)[0].strip() + "."


def _normalize_voice(voice: str | None) -> str:
    raw = (voice or TTS_VOICE).strip().lower() or "female"
    if raw in {"f", "woman", "lady", "mary", "neerja"}:
        return "female"
    if raw in {"m", "man", "thoma", "prabhat", "male_voice"}:
        return "male"
    if raw in _VOICE_DESCRIPTIONS:
        return raw
    return "female"


def _description_for_voice(voice: str) -> str:
    custom = (os.getenv("PARLER_TTS_DESCRIPTION") or "").strip()
    if custom:
        return custom
    return _VOICE_DESCRIPTIONS[_normalize_voice(voice)]


def _max_new_tokens_for_text(text: str) -> int:
    # ~2.5 words/sec speaking rate → rough audio seconds, then codes.
    words = max(1, len(text.split()))
    seconds = min(_PARLER_MAX_AUDIO_SECONDS, max(3.0, words / 2.4))
    return int(seconds * _PARLER_CODES_PER_SECOND)


def synthesize_speech(
    text: str,
    *,
    voice: str | None = None,
    model: str = MODEL_ID,
    speed: float | None = None,
) -> dict[str, Any]:
    """Convert interviewer text to WAV (or Edge MP3 tagged as WAV-compatible bytes)."""
    _ = speed
    cleaned = _humanize_script(text)
    if not cleaned:
        raise ValueError("Empty text for TTS.")
    if len(cleaned) > 4000:
        cleaned = cleaned[:3997] + "..."

    if not tts_available():
        raise RuntimeError(
            "TTS is not installed. For CPU: pip install edge-tts. "
            "For Parler: pip install git+https://github.com/huggingface/parler-tts.git "
            "transformers accelerate sentencepiece soundfile"
        )

    chosen_voice = _normalize_voice(voice)
    engine = resolve_engine()
    t0 = time.perf_counter()

    if engine == "edge":
        audio_bytes, sample_rate, content_type, provider, model_id = _synthesize_edge(
            cleaned, voice=chosen_voice
        )
    else:
        model_id = (model or MODEL_ID).strip() or MODEL_ID
        if not _cuda_available():
            logger.warning(
                "Parler-TTS on CPU is very slow (minutes/clip). "
                "Set TTS_ENGINE=edge for fast Indian English, or use an NVIDIA GPU."
            )
        audio_bytes, sample_rate = _synthesize_parler(
            cleaned, voice=chosen_voice, model_id=model_id
        )
        content_type = "audio/wav"
        provider = TTS_PROVIDER

    if not audio_bytes:
        raise RuntimeError("TTS returned empty audio.")

    elapsed = time.perf_counter() - t0
    logger.info(
        "TTS done engine=%s voice=%s seconds=%.2f chars=%s",
        engine,
        chosen_voice,
        elapsed,
        len(cleaned),
    )

    return {
        "audio_bytes": audio_bytes,
        "content_type": content_type,
        "provider": provider,
        "model": model_id if engine == "parler" else _EDGE_VOICES[chosen_voice],
        "voice": chosen_voice,
        "speed": None,
        "stt_companion": "whisper-large-v3",
        "sample_rate": sample_rate,
        "text": cleaned,
        "engine": engine,
        "elapsed_seconds": round(elapsed, 2),
    }


def warmup_tts() -> dict[str, Any]:
    """Load model / verify Edge once so the first user request is not cold."""
    global _warmup_done
    if _warmup_done:
        return {"ok": True, "already_warm": True, "engine": resolve_engine()}
    engine = resolve_engine()
    try:
        if engine == "parler":
            _get_runtime(MODEL_ID)
            # Tiny warmup generation so first real request is faster.
            _synthesize_parler(
                "Hello.",
                voice=_normalize_voice(TTS_VOICE),
                model_id=MODEL_ID,
            )
        else:
            _synthesize_edge("Hello.", voice=_normalize_voice(TTS_VOICE))
        _warmup_done = True
        return {"ok": True, "engine": engine}
    except Exception as exc:
        logger.warning("TTS warmup failed: %s", exc)
        return {"ok": False, "engine": engine, "error": str(exc)}


def _synthesize_edge(cleaned: str, *, voice: str) -> tuple[bytes, int, str, str, str]:
    """Fast cloud neural TTS (Indian English). Returns WAV bytes."""
    import edge_tts

    edge_voice = _EDGE_VOICES[_normalize_voice(voice)]

    async def _run() -> bytes:
        communicate = edge_tts.Communicate(cleaned, edge_voice)
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        return buf.getvalue()

    try:
        mp3_bytes = asyncio.run(_run())
    except RuntimeError:
        # Already inside an event loop (e.g. called from async thread wrongly).
        loop = asyncio.new_event_loop()
        try:
            mp3_bytes = loop.run_until_complete(_run())
        finally:
            loop.close()

    if not mp3_bytes:
        raise RuntimeError("Edge TTS returned empty audio.")

    wav_bytes, content_type = _mp3_to_wav(mp3_bytes)
    sample_rate = 24000 if content_type == "audio/wav" else 0
    return wav_bytes, sample_rate, content_type, "edge_tts_en_in", edge_voice


def _mp3_to_wav(mp3_bytes: bytes) -> tuple[bytes, str]:
    """Decode Edge MP3 to WAV. Prefer miniaudio; fall back to MP3 bytes."""
    try:
        import miniaudio

        decoded = miniaudio.decode(mp3_bytes, output_format=miniaudio.SampleFormat.FLOAT32)
        audio = np.frombuffer(decoded.samples, dtype=np.float32)
        if decoded.nchannels > 1:
            audio = audio.reshape(-1, decoded.nchannels).mean(axis=1)
        buf = io.BytesIO()
        sf.write(buf, audio, decoded.sample_rate, format="WAV")
        return buf.getvalue(), "audio/wav"
    except Exception:
        logger.debug("miniaudio MP3 decode unavailable; trying pydub/ffmpeg", exc_info=True)

    try:
        from pydub import AudioSegment

        segment = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
        buf = io.BytesIO()
        segment.export(buf, format="wav")
        return buf.getvalue(), "audio/wav"
    except Exception:
        logger.warning(
            "Could not convert Edge MP3→WAV (install miniaudio). Serving MP3 bytes."
        )
        return mp3_bytes, "audio/mpeg"


def _load_runtime(model_id: str):
    """Load Parler model + tokenizers once (CPU float32 or CUDA float16)."""
    import torch
    from parler_tts import ParlerTTSForConditionalGeneration
    from transformers import AutoTokenizer

    token = _hf_token()
    if not token:
        logger.warning(
            "HF_TOKEN is not set in environment; gated HuggingFace downloads may fail."
        )

    device = _resolve_device()
    dtype = torch.float16 if device.startswith("cuda") else torch.float32

    # Use more CPU threads when stuck on CPU.
    if device == "cpu":
        threads = int(os.getenv("PARLER_TTS_THREADS") or max(1, (os.cpu_count() or 4) - 1))
        torch.set_num_threads(threads)
        torch.set_num_interop_threads(max(1, threads // 2))

    logger.info(
        "Loading Indic Parler-TTS model=%s device=%s dtype=%s",
        model_id,
        device,
        dtype,
    )

    model = ParlerTTSForConditionalGeneration.from_pretrained(
        model_id,
        token=token,
        torch_dtype=dtype,
        attn_implementation="sdpa",
    ).to(device)
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(model_id, token=token)
    description_tokenizer = AutoTokenizer.from_pretrained(
        model.config.text_encoder._name_or_path,
        token=token,
    )

    return model, tokenizer, description_tokenizer, device, dtype


def _get_runtime(model_id: str):
    """Thread-safe singleton loader for model and tokenizers."""
    global _model, _tokenizer, _description_tokenizer, _device, _dtype, _loaded_model_id

    if (
        _model is not None
        and _tokenizer is not None
        and _description_tokenizer is not None
        and _loaded_model_id == model_id
    ):
        return _model, _tokenizer, _description_tokenizer, _device

    with _lock:
        if (
            _model is not None
            and _tokenizer is not None
            and _description_tokenizer is not None
            and _loaded_model_id == model_id
        ):
            return _model, _tokenizer, _description_tokenizer, _device

        model, tokenizer, description_tokenizer, device, dtype = _load_runtime(model_id)
        _model = model
        _tokenizer = tokenizer
        _description_tokenizer = description_tokenizer
        _device = device
        _dtype = dtype
        _loaded_model_id = model_id
        logger.info("Indic Parler-TTS ready on %s (%s)", device, dtype)
        return _model, _tokenizer, _description_tokenizer, _device


def _synthesize_parler(cleaned: str, *, voice: str, model_id: str) -> tuple[bytes, int]:
    import torch

    model, tokenizer, description_tokenizer, device = _get_runtime(model_id)
    prompt = _truncate_for_parler(cleaned)
    description = _description_for_voice(voice)
    max_new_tokens = _max_new_tokens_for_text(prompt)

    try:
        with torch.inference_mode():
            description_inputs = description_tokenizer(
                description, return_tensors="pt"
            ).to(device)
            prompt_inputs = tokenizer(prompt, return_tensors="pt").to(device)

            generation = model.generate(
                input_ids=description_inputs.input_ids,
                attention_mask=description_inputs.attention_mask,
                prompt_input_ids=prompt_inputs.input_ids,
                prompt_attention_mask=prompt_inputs.attention_mask,
                do_sample=True,
                temperature=1.0,
                max_new_tokens=max_new_tokens,
            )

        audio_arr = generation.detach().cpu().float().numpy().squeeze()
        if audio_arr.ndim > 1:
            audio_arr = audio_arr.reshape(-1)
        audio_arr = np.asarray(audio_arr, dtype=np.float32)

        peak = float(np.max(np.abs(audio_arr))) if audio_arr.size else 0.0
        if peak > 1e-6:
            audio_arr = audio_arr * min(0.95 / peak, 1.0)

        sample_rate = int(
            getattr(model.config, "sampling_rate", None) or PARLER_SAMPLE_RATE_FALLBACK
        )
        buf = io.BytesIO()
        sf.write(buf, audio_arr, sample_rate, format="WAV")
        return buf.getvalue(), sample_rate
    except Exception as exc:
        logger.exception("Indic Parler-TTS synthesis failed")
        raise RuntimeError(f"Indic Parler-TTS failed: {exc}") from exc
