from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from agents.proctoring_agent.ai.audio import SpeakerEngine  # noqa: E402
from agents.proctoring_agent.ai.attention import MediaPipeLandmarkProvider  # noqa: E402
from agents.proctoring_agent.ai.face import AntiSpoofEngine, FaceEngine  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def timed(call: Callable[[], Any]) -> tuple[Any, float]:
    started = time.perf_counter()
    value = call()
    return value, time.perf_counter() - started


def integrity(item: dict[str, Any], models_dir: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    destination = models_dir / item["destination"]
    if item["source_type"] == "url":
        if not destination.is_file():
            return False, [f"missing file: {destination}"]
        if item.get("size_bytes") is not None and destination.stat().st_size != int(item["size_bytes"]):
            errors.append(f"size mismatch: expected {item['size_bytes']}, got {destination.stat().st_size}")
        if item.get("sha256") and sha256(destination).lower() != str(item["sha256"]).lower():
            errors.append(f"sha256 mismatch: {sha256(destination)}")
    else:
        for name in item.get("required_files", []):
            path = destination / name
            if not path.is_file():
                errors.append(f"missing file: {name}")
                continue
            expected_size = item.get("sizes", {}).get(name)
            if expected_size is not None and path.stat().st_size != int(expected_size):
                errors.append(f"size mismatch for {name}: expected {expected_size}, got {path.stat().st_size}")
            expected = item.get("checksums", {}).get(name)
            if expected and sha256(path).lower() != str(expected).lower():
                errors.append(f"sha256 mismatch for {name}: {sha256(path)}")
    return not errors, errors


def face_readiness(models_dir: Path) -> dict[str, Any]:
    engine = FaceEngine(
        models_dir / "face_detection_yunet_2023mar.onnx",
        models_dir / "face_recognition_sface_2021dec.onnx",
    )
    blank = np.zeros((320, 320, 3), dtype=np.uint8)
    faces, detector_seconds = timed(lambda: engine.detect(blank))
    synthetic = np.full((320, 320, 3), 127, dtype=np.uint8)
    face = np.array([80, 50, 160, 210, 125, 120, 195, 120, 160, 155, 132, 205, 188, 205, 0.99], dtype=np.float32)
    vector, recognizer_seconds = timed(lambda: engine.embedding(synthetic, face))
    if faces.ndim != 2 or (faces.size and faces.shape[1] != 15):
        raise RuntimeError(f"unexpected YuNet output shape: {faces.shape}")
    if vector.shape != (128,) or not np.isfinite(vector).all() or not np.isclose(np.linalg.norm(vector), 1.0, atol=1e-4):
        raise RuntimeError(f"unexpected SFace embedding: shape={vector.shape}, finite={np.isfinite(vector).all()}")
    return {"ready": True, "detector_seconds": detector_seconds, "recognizer_seconds": recognizer_seconds, "embedding_shape": list(vector.shape)}



def attention_readiness(models_dir: Path) -> dict[str, Any]:
    provider = MediaPipeLandmarkProvider(models_dir / "face_landmarker.task")
    if not provider.available:
        raise RuntimeError(provider.load_error or "MediaPipe Face Landmarker is unavailable")
    blank = np.zeros((320, 320, 3), dtype=np.uint8)
    _landmarks, seconds = timed(lambda: provider.detect(blank))
    return {
        "ready": True,
        "inference_seconds": seconds,
        "model_name": provider.model_name,
        "model_version": provider.package_version,
        "model_sha256": provider.installed_asset_checksum(),
        "expected_landmarks": 478,
        "blank_frame_result": "no_face_expected",
    }

def anti_spoof_readiness(models_dir: Path) -> dict[str, Any]:
    engine = AntiSpoofEngine(models_dir / "MiniFASNetV2.onnx")
    image = np.full((240, 320, 3), 127, dtype=np.uint8)
    face = np.array([80, 30, 160, 190, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.99], dtype=np.float32)
    result, seconds = timed(lambda: engine.analyze(image, face))
    probabilities = np.asarray(result.get("class_probabilities", []), dtype=np.float32)
    if not result.get("available") or probabilities.size < 2 or not np.isfinite(probabilities).all():
        raise RuntimeError(f"unexpected anti-spoof output: {result}")
    return {"ready": True, "inference_seconds": seconds, "output_shape": list(probabilities.shape), "review_only": True}


def speaker_readiness(models_dir: Path) -> dict[str, Any]:
    engine = SpeakerEngine(models_dir / "spkrec-ecapa-voxceleb")
    t = np.arange(16000 * 3, dtype=np.float32) / 16000.0
    signal = (0.15 * np.sin(2 * np.pi * 190 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 2.5 * t) ** 2)).astype(np.float32)
    vector, seconds = timed(lambda: engine.encode(signal, 16000))
    if vector.ndim != 1 or vector.size < 128 or not np.isfinite(vector).all() or not np.isclose(np.linalg.norm(vector), 1.0, atol=1e-4):
        raise RuntimeError(f"unexpected ECAPA embedding: shape={vector.shape}")
    return {"ready": True, "inference_seconds": seconds, "embedding_shape": list(vector.shape), "engine": engine.mode}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify model integrity, CPU loading and one finite inference")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    models_dir = root / "models"
    manifest = json.loads((models_dir / "model_manifest.json").read_text(encoding="utf-8"))
    by_name = {item["name"]: item for item in manifest["models"]}
    report: dict[str, Any] = {"root": str(root), "models": {}, "ready": True}

    checks = {
        "face": (by_name["OpenCV YuNet face detector"], by_name["OpenCV SFace recognizer"], face_readiness),
        "attention": (by_name["MediaPipe Face Landmarker float16 task"], attention_readiness),
        "anti_spoof": (by_name["MiniFASNetV2 ONNX"], anti_spoof_readiness),
        "speaker": (by_name["SpeechBrain ECAPA-TDNN VoxCeleb"], speaker_readiness),
    }
    for group, values in checks.items():
        *items, inference = values
        errors: list[str] = []
        for item in items:
            ok, item_errors = integrity(item, models_dir)
            if not ok:
                errors.extend(f"{item['name']}: {error}" for error in item_errors)
        entry: dict[str, Any] = {"integrity_ok": not errors, "errors": errors}
        if not errors:
            try:
                result = inference(models_dir)
                max_seconds = max(float(item.get("max_warmup_seconds", 90)) for item in items)
                measured = max(float(value) for key, value in result.items() if key.endswith("seconds"))
                if measured > max_seconds:
                    raise RuntimeError(f"warm-up {measured:.3f}s exceeds manifest limit {max_seconds:.3f}s")
                entry.update(result)
            except Exception as exc:
                entry.update({"ready": False, "errors": [f"{type(exc).__name__}: {exc}"]})
        else:
            entry["ready"] = False
        report["models"][group] = entry
        report["ready"] = bool(report["ready"] and entry.get("ready"))

    output = args.output or (root / "storage" / "logs" / "model_readiness.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Model readiness report: {output}")
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
