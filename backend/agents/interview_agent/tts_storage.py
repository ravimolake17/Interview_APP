"""Filesystem storage for pre-generated Kokoro TTS question audio.

Audio blobs are stored on disk (not ChromaDB). Chroma is for vector search;
WAV files belong in dedicated object/file storage with Postgres metadata.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# backend/storage/tts_audio/{candidate_id}/{question_id}.wav
_STORAGE_ROOT = Path(__file__).resolve().parents[2] / "storage" / "tts_audio"


def get_tts_storage_root() -> Path:
    _STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    return _STORAGE_ROOT


def text_hash(text: str) -> str:
    return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()


def audio_path_for(candidate_id: str, question_id: str) -> Path:
    safe_candidate = "".join(c for c in candidate_id if c.isalnum() or c in "-_")
    safe_qid = "".join(c for c in question_id if c.isalnum() or c in "-_")
    folder = get_tts_storage_root() / safe_candidate
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{safe_qid}.wav"


def write_audio_file(candidate_id: str, question_id: str, audio_bytes: bytes) -> str:
    path = audio_path_for(candidate_id, question_id)
    path.write_bytes(audio_bytes)
    # Store path relative to storage root for portability.
    return str(path.relative_to(get_tts_storage_root())).replace("\\", "/")


def read_audio_file(relative_path: str) -> bytes | None:
    if not relative_path:
        return None
    path = get_tts_storage_root() / relative_path
    if not path.is_file():
        return None
    return path.read_bytes()


def delete_candidate_audio(candidate_id: str) -> None:
    safe_candidate = "".join(c for c in candidate_id if c.isalnum() or c in "-_")
    folder = get_tts_storage_root() / safe_candidate
    if not folder.exists():
        return
    for path in folder.glob("*.wav"):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.debug("Could not delete TTS file %s", path)
