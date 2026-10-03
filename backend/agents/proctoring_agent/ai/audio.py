from __future__ import annotations

import io
import os
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import librosa
import numpy as np
import soundfile as sf
import torch
from scipy.fft import dct
from scipy.signal import resample_poly

from ..config import get_settings
from .common import DetectionResult, ModelUnavailableError, cosine_similarity


_silero_model = None
_silero_lock = threading.Lock()
_speechbrain_lazy_guard_lock = threading.Lock()
_speechbrain_lazy_guard_installed = False


def _install_speechbrain_windows_lazy_import_guard() -> None:
    """Prevent optional SpeechBrain integrations from being imported by inspection.

    SpeechBrain 1.1.0 deliberately lazy-loads optional integrations. Its guard
    checks for ``/inspect.py`` using POSIX separators, so on Windows an
    introspection pass can accidentally import optional modules such as k2-FSA.
    Agent5 only needs the ECAPA inference interface; optional ASR integrations
    must not be imported or required.
    """
    global _speechbrain_lazy_guard_installed
    if os.name != "nt" or _speechbrain_lazy_guard_installed:
        return
    with _speechbrain_lazy_guard_lock:
        if _speechbrain_lazy_guard_installed:
            return
        import inspect
        import sys

        from speechbrain.utils.importutils import LazyModule

        original = LazyModule.ensure_module
        if getattr(original, "_agent5_windows_guard", False):
            _speechbrain_lazy_guard_installed = True
            return

        def ensure_module_windows_safe(self, stacklevel: int):
            try:
                frame = inspect.getframeinfo(sys._getframe(stacklevel + 1))
                filename = frame.filename.replace("\\", "/")
            except Exception:
                filename = ""
            if filename.endswith("/inspect.py"):
                raise AttributeError()
            # Account for this compatibility wrapper when delegating to the
            # upstream implementation's own frame inspection.
            return original(self, stacklevel + 1)

        ensure_module_windows_safe._agent5_windows_guard = True  # type: ignore[attr-defined]
        LazyModule.ensure_module = ensure_module_windows_safe
        _speechbrain_lazy_guard_installed = True


def _silero_voiced_ratio(signal: np.ndarray, sample_rate: int) -> float | None:
    """Return voiced-sample ratio using the packaged Silero VAD when installed."""
    global _silero_model
    try:
        from silero_vad import get_speech_timestamps, load_silero_vad
    except Exception:
        return None
    try:
        if sample_rate != 16000:
            signal = librosa.resample(signal, orig_sr=sample_rate, target_sr=16000)
            sample_rate = 16000
        with _silero_lock:
            if _silero_model is None:
                _silero_model = load_silero_vad(onnx=True)
            stamps = get_speech_timestamps(torch.from_numpy(np.asarray(signal, dtype=np.float32)), _silero_model, sampling_rate=sample_rate, return_seconds=False)
        voiced = sum(max(0, int(item["end"]) - int(item["start"])) for item in stamps)
        return float(voiced / max(len(signal), 1))
    except Exception:
        return None


@dataclass
class AudioQuality:
    accepted: bool
    reasons: list[str]
    duration_seconds: float
    rms_dbfs: float
    clipping_ratio: float
    voiced_ratio: float
    estimated_snr_db: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reasons": self.reasons,
            "duration_seconds": round(self.duration_seconds, 3),
            "rms_dbfs": round(self.rms_dbfs, 3),
            "clipping_ratio": round(self.clipping_ratio, 5),
            "voiced_ratio": round(self.voiced_ratio, 4),
            "estimated_snr_db": round(self.estimated_snr_db, 3),
            "vad_engine": "silero-vad" if _silero_model is not None else "energy-fallback",
        }


def _resolve_ffmpeg() -> str:
    """Return an ffmpeg executable: explicit path, PATH, or bundled imageio-ffmpeg."""
    import shutil

    configured = get_settings().ffmpeg_path
    if configured and configured.lower() not in {"ffmpeg", "ffprobe"}:
        path = Path(configured)
        if path.is_file():
            return str(path)
    found = shutil.which(configured or "ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).is_file():
            return bundled
    except Exception:
        pass
    raise ValueError(
        "ffmpeg is not available. Voice enrollment requires ffmpeg to decode browser audio (webm). "
        "Install ffmpeg on PATH, set AGENT5_FFMPEG_PATH in .env, or pip install imageio-ffmpeg."
    )


def decode_audio_bytes(data: bytes, mime_type: str = "audio/webm") -> tuple[np.ndarray, int]:
    ffmpeg = _resolve_ffmpeg()
    suffix = ".wav" if "wav" in mime_type else ".webm" if "webm" in mime_type else ".bin"
    with tempfile.TemporaryDirectory(prefix="agent5_audio_") as temp:
        source = Path(temp) / f"source{suffix}"
        target = Path(temp) / "decoded.wav"
        source.write_bytes(data)
        command = [ffmpeg, "-y", "-i", str(source), "-ac", "1", "-ar", "16000", "-f", "wav", str(target)]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
        except FileNotFoundError as exc:
            raise ValueError(
                f"ffmpeg executable not found at '{ffmpeg}'. Install ffmpeg or set AGENT5_FFMPEG_PATH."
            ) from exc
        if result.returncode != 0 or not target.exists():
            raise ValueError(f"audio decode failed: {result.stderr[-500:]}")
        signal, sr = sf.read(target, dtype="float32", always_2d=False)
    signal = np.asarray(signal, dtype=np.float32).reshape(-1)
    return signal, int(sr)


def analyze_quality(signal: np.ndarray, sample_rate: int = 16000, minimum_seconds: float = 1.5) -> AudioQuality:
    signal = np.asarray(signal, dtype=np.float32).reshape(-1)
    duration = len(signal) / max(sample_rate, 1)
    rms = float(np.sqrt(np.mean(signal ** 2) + 1e-12))
    rms_dbfs = float(20 * np.log10(max(rms, 1e-8)))
    clipping = float(np.mean(np.abs(signal) >= 0.985))
    frame = max(int(sample_rate * 0.03), 1)
    energies = np.array([np.sqrt(np.mean(signal[i:i + frame] ** 2) + 1e-12) for i in range(0, len(signal), frame)])
    noise_floor = float(np.percentile(energies, 20)) if len(energies) else 0.0
    speech_threshold = max(noise_floor * 3.0, 0.008)
    energy_voiced_ratio = float(np.mean(energies > speech_threshold)) if len(energies) else 0.0
    silero_ratio = _silero_voiced_ratio(signal, sample_rate)
    voiced_ratio = silero_ratio if silero_ratio is not None else energy_voiced_ratio
    speech_level = float(np.percentile(energies, 80)) if len(energies) else 0.0
    snr = float(20 * np.log10(max(speech_level, 1e-8) / max(noise_floor, 1e-8)))
    reasons: list[str] = []
    if duration < minimum_seconds:
        reasons.append("speech sample is too short")
    if rms_dbfs < -42:
        reasons.append("audio is too quiet or silent")
    if clipping > 0.02:
        reasons.append("audio is clipped")
    if voiced_ratio < 0.18:
        reasons.append("insufficient voiced speech")
    if snr < 6:
        reasons.append("signal-to-noise ratio is too low")
    return AudioQuality(not reasons, reasons, duration, rms_dbfs, clipping, voiced_ratio, snr)


class MFCCSpeakerEmbedder:
    """Deterministic MFCC statistics retained for diagnostics and test fixtures only.

    This class is never used by the production identity-verification path. Missing
    ECAPA model files make speaker enrollment and verification fail closed.
    """

    name = "mfcc-statistical-speaker-embedding"
    _filter_cache: dict[tuple[int, int, int], np.ndarray] = {}

    @staticmethod
    def _resample(signal: np.ndarray, sample_rate: int, target: int = 16000) -> np.ndarray:
        if sample_rate == target:
            return np.asarray(signal, dtype=np.float32)
        divisor = int(np.gcd(sample_rate, target))
        return resample_poly(signal, target // divisor, sample_rate // divisor).astype(np.float32)

    @classmethod
    def _mel_filters(cls, sample_rate: int, n_fft: int, n_mels: int = 40) -> np.ndarray:
        key = (sample_rate, n_fft, n_mels)
        cached = cls._filter_cache.get(key)
        if cached is not None:
            return cached

        def hz_to_mel(value):
            return 2595.0 * np.log10(1.0 + value / 700.0)

        def mel_to_hz(value):
            return 700.0 * (10.0 ** (value / 2595.0) - 1.0)

        mel_points = np.linspace(hz_to_mel(20.0), hz_to_mel(sample_rate / 2), n_mels + 2)
        bins = np.floor((n_fft + 1) * mel_to_hz(mel_points) / sample_rate).astype(int)
        bins = np.clip(bins, 0, n_fft // 2)
        filters = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
        for index in range(1, n_mels + 1):
            left, center, right = bins[index - 1], bins[index], bins[index + 1]
            if center <= left:
                center = min(left + 1, n_fft // 2)
            if right <= center:
                right = min(center + 1, n_fft // 2)
            if center > left:
                filters[index - 1, left:center] = (np.arange(left, center) - left) / (center - left)
            if right > center:
                filters[index - 1, center:right] = (right - np.arange(center, right)) / (right - center)
        cls._filter_cache[key] = filters
        return filters

    @classmethod
    def encode(cls, signal: np.ndarray, sample_rate: int) -> np.ndarray:
        signal = cls._resample(np.asarray(signal, dtype=np.float32).reshape(-1), sample_rate)
        if len(signal) < 1600:
            raise ValueError("not enough speech for speaker embedding")
        peak = float(np.max(np.abs(signal)))
        if peak <= 1e-8:
            raise ValueError("silent audio cannot produce a speaker embedding")
        active = np.flatnonzero(np.abs(signal) >= peak * 10 ** (-35 / 20))
        if len(active):
            signal = signal[max(0, active[0] - 400):min(len(signal), active[-1] + 401)]
        signal = np.append(signal[0], signal[1:] - 0.97 * signal[:-1]).astype(np.float32)

        frame_length, hop, n_fft = 400, 160, 512
        frame_count = max(1, 1 + int(np.ceil(max(0, len(signal) - frame_length) / hop)))
        padded_length = (frame_count - 1) * hop + frame_length
        if padded_length > len(signal):
            signal = np.pad(signal, (0, padded_length - len(signal)))
        frames = np.stack([signal[i * hop:i * hop + frame_length] for i in range(frame_count)])
        frames *= np.hamming(frame_length).astype(np.float32)
        power = (np.abs(np.fft.rfft(frames, n=n_fft, axis=1)) ** 2) / n_fft
        mel_energy = np.maximum(power @ cls._mel_filters(16000, n_fft).T, 1e-10)
        coefficients = dct(np.log(mel_energy), type=2, axis=1, norm="ortho")[:, :30].T.astype(np.float32)
        delta = np.gradient(coefficients, axis=1).astype(np.float32)
        delta2 = np.gradient(delta, axis=1).astype(np.float32)
        feature = np.concatenate(
            [coefficients.mean(1), coefficients.std(1), delta.mean(1), delta.std(1), delta2.mean(1), delta2.std(1)]
        ).astype(np.float32)
        norm = np.linalg.norm(feature)
        return feature / norm if norm else feature


class SpeakerEngine:
    """Mandatory text-independent SpeechBrain ECAPA-TDNN speaker verifier.

    Identity verification never falls back to MFCC, loudness, pitch, or speech
    content. When the pinned ECAPA model is missing or cannot load, enrollment
    and verification fail closed with a clear technical error.
    """

    engine_name = "speechbrain-ecapa-tdnn-voxceleb"
    model_version = "a025b9e8262be969a7b3f8f53c01d346eadf361b"

    required_files = (
        "hyperparams.yaml",
        "embedding_model.ckpt",
        "classifier.ckpt",
        "mean_var_norm_emb.ckpt",
        "label_encoder.txt",
        "config.json",
    )

    def __init__(self, model_dir: Path | None = None) -> None:
        self.model_dir = model_dir or get_settings().models_dir / "spkrec-ecapa-voxceleb"
        self._classifier = None
        self._load_error: str | None = None
        self._lock = threading.Lock()
        self.mode = self.engine_name if self.available else "unavailable"

    @property
    def missing_files(self) -> list[str]:
        return [name for name in self.required_files if not (self.model_dir / name).exists()]

    @property
    def available(self) -> bool:
        return not self.missing_files

    def readiness(self, *, load: bool = False) -> dict[str, Any]:
        if not self.available:
            return {
                "ready": False,
                "engine": self.engine_name,
                "model_version": self.model_version,
                "missing_files": self.missing_files,
                "error": "mandatory ECAPA model files are missing",
            }
        if load:
            try:
                self._load_ecapa()
            except ModelUnavailableError as exc:
                return {
                    "ready": False,
                    "engine": self.engine_name,
                    "model_version": self.model_version,
                    "missing_files": [],
                    "error": str(exc),
                }
        return {
            "ready": self._classifier is not None if load else True,
            "engine": self.engine_name,
            "model_version": self.model_version,
            "missing_files": [],
            "error": self._load_error,
        }

    def _load_ecapa(self) -> None:
        if self._classifier is not None:
            return
        missing = self.missing_files
        if missing:
            self.mode = "unavailable"
            raise ModelUnavailableError(
                "Mandatory SpeechBrain ECAPA speaker model is unavailable. "
                f"Missing files: {', '.join(missing)}. Run setup_agent5.ps1."
            )
        try:
            _install_speechbrain_windows_lazy_import_guard()
            from speechbrain.inference.speaker import EncoderClassifier
            from speechbrain.utils.fetching import LocalStrategy

            # PyTorch 2.6 defaults torch.load() to weights_only=True. Agent5
            # loads only the pinned, checksum-verified SpeechBrain snapshot.
            # Scope the compatibility override to this trusted model load.
            previous_no_weights_only = os.environ.get("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD")
            os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1"
            try:
                self._classifier = EncoderClassifier.from_hparams(
                    source=str(self.model_dir),
                    savedir=str(self.model_dir),
                    run_opts={"device": "cpu"},
                    # Standard Windows users cannot create symlinks by default.
                    # COPY is SpeechBrain's supported non-privileged strategy.
                    local_strategy=LocalStrategy.COPY,
                )
            finally:
                if previous_no_weights_only is None:
                    os.environ.pop("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", None)
                else:
                    os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = previous_no_weights_only
            self.mode = self.engine_name
            self._load_error = None
        except Exception as exc:
            self._classifier = None
            self.mode = "unavailable"
            self._load_error = f"{type(exc).__name__}: {exc}"
            raise ModelUnavailableError(
                "Mandatory SpeechBrain ECAPA speaker model failed to load; "
                "voice enrollment and interview start are blocked. "
                f"Technical error: {self._load_error}"
            ) from exc

    @staticmethod
    def _normalize_embedding(vector: np.ndarray, *, name: str) -> np.ndarray:
        vector = np.asarray(vector, dtype=np.float32).reshape(-1)
        if vector.size == 0 or not np.isfinite(vector).all():
            raise RuntimeError(f"{name} is empty or non-finite")
        norm = float(np.linalg.norm(vector))
        if not np.isfinite(norm) or norm <= 1e-8:
            raise RuntimeError(f"{name} has zero norm")
        return vector / norm

    @staticmethod
    def _to_16k_mono(signal: np.ndarray, sample_rate: int) -> np.ndarray:
        signal = np.asarray(signal, dtype=np.float32).reshape(-1)
        if sample_rate <= 0:
            raise ValueError("sample rate must be positive")
        if sample_rate != 16000 and signal.size:
            signal = librosa.resample(signal, orig_sr=sample_rate, target_sr=16000)
        return np.asarray(signal, dtype=np.float32).reshape(-1)

    @classmethod
    def _candidate_windows(cls, signal: np.ndarray, sample_rate: int) -> list[np.ndarray]:
        signal = cls._to_16k_mono(signal, sample_rate)
        window = int(2.5 * 16000)
        hop = int(1.25 * 16000)
        if len(signal) <= window:
            return [signal]
        windows: list[np.ndarray] = []
        for start in range(0, len(signal) - window + 1, hop):
            segment = signal[start:start + window]
            if analyze_quality(segment, 16000, minimum_seconds=1.5).accepted:
                windows.append(segment)
        if not windows and analyze_quality(signal, 16000, minimum_seconds=1.5).accepted:
            windows.append(signal)
        return windows

    def encode(self, signal: np.ndarray, sample_rate: int) -> np.ndarray:
        self._load_ecapa()
        signal = self._to_16k_mono(signal, sample_rate)
        waveform = torch.from_numpy(signal).unsqueeze(0)
        with self._lock, torch.inference_mode():
            embedding = self._classifier.encode_batch(waveform).squeeze().cpu().numpy().astype(np.float32)
        return self._normalize_embedding(embedding, name="ECAPA speaker embedding")

    def _aggregate_embeddings(self, signal: np.ndarray, sample_rate: int) -> tuple[np.ndarray, int]:
        windows = self._candidate_windows(signal, sample_rate)
        if not windows:
            raise ValueError("no valid voiced windows were available for speaker embedding")
        vectors = [self.encode(window, 16000) for window in windows]
        dimensions = {vector.shape for vector in vectors}
        if len(dimensions) != 1:
            raise RuntimeError("ECAPA returned inconsistent embedding shapes")
        aggregate = self._normalize_embedding(np.mean(np.stack(vectors), axis=0), name="aggregated ECAPA baseline")
        return aggregate, len(vectors)

    @staticmethod
    def _quality_label(quality: AudioQuality) -> str:
        if quality.rms_dbfs < -42 or quality.voiced_ratio <= 0.02:
            return "no_speech"
        if quality.voiced_ratio < 0.18 or quality.duration_seconds < 1.5:
            return "insufficient_speech"
        if quality.clipping_ratio > 0.02:
            return "audio_clipped"
        if quality.estimated_snr_db < 6:
            return "audio_too_noisy"
        return "poor_audio_quality"

    def enroll(self, signal: np.ndarray, sample_rate: int = 16000) -> DetectionResult:
        self._load_ecapa()
        quality = analyze_quality(signal, sample_rate, minimum_seconds=2.0)
        if not quality.accepted:
            return DetectionResult(False, self._quality_label(quality), 1.0, {"quality": quality.as_dict(), "engine": self.mode, "model_version": self.model_version})
        vector, window_count = self._aggregate_embeddings(signal, sample_rate)
        return DetectionResult(
            True,
            "voice_enrolled",
            1.0,
            {
                "quality": quality.as_dict(),
                "engine": self.mode,
                "model_version": self.model_version,
                "baseline_window_count": window_count,
                "embedding_dimension": int(vector.size),
            },
            vector,
        )

    def verify(self, signal: np.ndarray, baseline: np.ndarray, sample_rate: int = 16000, threshold: float | None = None) -> DetectionResult:
        self._load_ecapa()
        # Validate persisted biometric state before processing the live sample.
        # A corrupt baseline is a technical integrity failure, not "no speech".
        baseline = self._normalize_embedding(baseline, name="stored speaker baseline")
        quality = analyze_quality(signal, sample_rate, minimum_seconds=1.5)
        if not quality.accepted:
            label = self._quality_label(quality)
            return DetectionResult(False, label, 1.0, {"quality": quality.as_dict(), "engine": self.mode, "model_version": self.model_version})
        vector, window_count = self._aggregate_embeddings(signal, sample_rate)
        similarity = cosine_similarity(vector, baseline)
        threshold = threshold if threshold is not None else get_settings().speaker_similarity_threshold
        passed = similarity >= threshold
        confidence = min(1.0, abs(similarity - threshold) / max(1.0 - threshold, 1e-6) + 0.5)
        return DetectionResult(
            passed,
            "voice_match" if passed else "voice_mismatch",
            confidence,
            {
                "similarity": similarity,
                "threshold": threshold,
                "quality": quality.as_dict(),
                "engine": self.mode,
                "model_version": self.model_version,
                "verification_window_count": window_count,
                "embedding_dimension": int(vector.size),
            },
            vector,
        )

    @staticmethod
    def additional_speech_review(
        signal: np.ndarray,
        sample_rate: int = 16000,
        *,
        identity_label: str | None = None,
    ) -> dict[str, Any]:
        """Return conservative, quality-gated, review-only speech-source evidence.

        This deliberately does not claim diarization. It first classifies audio
        quality/VAD state, then computes a spectral variability proxy only for
        usable speech. Identity state comes only from ECAPA's result supplied by
        the caller; pitch or spectral statistics never replace speaker identity.
        """
        signal = np.asarray(signal, dtype=np.float32).reshape(-1)
        quality = analyze_quality(signal, sample_rate, minimum_seconds=1.0)
        quality_state = SpeakerEngine._quality_label(quality) if not quality.accepted else "candidate_speech"
        if identity_label in {"voice_match", "voice_mismatch"}:
            state = identity_label
        else:
            state = quality_state

        base: dict[str, Any] = {
            "state": state,
            "possible_additional_speaker": False,
            "probable_additional_speaker": False,
            "possible_overlapping_speech": False,
            "overlapping_speech_likely": False,
            "overlap_confidence": 0.0,
            "method": "spectral_review_proxy",
            "review_only": True,
            "engine": "agent5-spectral-review-proxy",
            "model_version": "review-proxy-v1",
            "quality": quality.as_dict(),
        }
        if not quality.accepted:
            return base

        signal = SpeakerEngine._to_16k_mono(signal, sample_rate)
        sample_rate = 16000
        if len(signal) < sample_rate:
            base["state"] = "insufficient_speech"
            return base

        frame_length, hop, n_fft = 400, 160, 512
        frame_count = 1 + max(0, (len(signal) - frame_length) // hop)
        frames = np.stack([signal[index * hop:index * hop + frame_length] for index in range(frame_count)])
        frames *= np.hanning(frame_length).astype(np.float32)
        power = np.abs(np.fft.rfft(frames, n=n_fft, axis=1)).astype(np.float32) ** 2 + 1e-10
        frequencies = np.fft.rfftfreq(n_fft, 1.0 / sample_rate).astype(np.float32)
        centroid = (power * frequencies).sum(axis=1) / power.sum(axis=1)
        flatness = np.exp(np.mean(np.log(power), axis=1)) / np.mean(power, axis=1)

        band_edges = np.linspace(0, power.shape[1], 9, dtype=int)
        bands = np.stack([power[:, band_edges[i]:band_edges[i + 1]].mean(axis=1) for i in range(8)], axis=1)
        log_bands = np.log10(bands + 1e-10)
        centroid_variation = float(np.std(centroid) / 1800.0)
        band_variation = float(np.mean(np.std(log_bands, axis=0)) / 1.5)
        flatness_variation = float(np.std(flatness) / 0.20)
        confidence = round(float(np.clip(0.50 * centroid_variation + 0.35 * band_variation + 0.15 * flatness_variation, 0, 1)), 3)
        possible = confidence >= 0.78
        probable = confidence >= 0.90
        overlap = confidence >= 0.92
        base.update(
            {
                "state": "probable_additional_speaker" if probable else "possible_additional_speaker" if possible else state,
                "possible_additional_speaker": possible,
                "probable_additional_speaker": probable,
                "possible_overlapping_speech": confidence >= 0.86,
                "overlapping_speech_likely": overlap,
                "overlap_confidence": confidence,
                "centroid_variation": round(centroid_variation, 3),
                "band_variation": round(band_variation, 3),
                "flatness_variation": round(flatness_variation, 3),
            }
        )
        return base
