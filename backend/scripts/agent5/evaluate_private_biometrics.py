from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from agents.proctoring_agent.ai.audio import SpeakerEngine, decode_audio_bytes  # noqa: E402
from agents.proctoring_agent.ai.common import cosine_similarity  # noqa: E402
from agents.proctoring_agent.ai.face import FaceEngine  # noqa: E402
from agents.proctoring_agent.config import get_settings  # noqa: E402


@dataclass
class Trial:
    path_a: str
    path_b: str
    same: bool
    similarity: float | None
    accepted: bool | None
    error: str | None = None


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "same", "positive"}:
        return True
    if normalized in {"0", "false", "no", "different", "negative"}:
        return False
    raise ValueError(f"invalid same/different label: {value!r}")


def load_pairs(path: Path) -> list[tuple[Path, Path, bool]]:
    rows: list[tuple[Path, Path, bool]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"path_a", "path_b", "same"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("CSV requires columns: path_a,path_b,same")
        for number, row in enumerate(reader, start=2):
            try:
                a = Path(row["path_a"]).expanduser().resolve()
                b = Path(row["path_b"]).expanduser().resolve()
                same = parse_bool(row["same"])
            except Exception as exc:
                raise ValueError(f"invalid row {number}: {exc}") from exc
            rows.append((a, b, same))
    if not rows:
        raise ValueError("pair CSV contains no trials")
    return rows


def face_vector(engine: FaceEngine, path: Path) -> np.ndarray:
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError("image could not be decoded")
    faces = engine.detect(image)
    if len(faces) != 1:
        raise ValueError(f"expected exactly one face, found {len(faces)}")
    quality = engine.quality(image, faces[0])
    if not quality.accepted:
        raise ValueError("face quality rejected: " + ", ".join(quality.reasons))
    return engine.embedding(image, faces[0])


def speaker_vector(engine: SpeakerEngine, path: Path) -> np.ndarray:
    mime = mimetypes.guess_type(path.name)[0] or ("audio/wav" if path.suffix.lower() == ".wav" else "audio/webm")
    signal, sample_rate = decode_audio_bytes(path.read_bytes(), mime)
    result = engine.enroll(signal, sample_rate)
    if not result.passed or result.vector is None:
        reasons = result.measurements.get("reasons") or result.measurements.get("quality", {}).get("reasons") or [result.label]
        raise ValueError("audio enrollment rejected: " + ", ".join(map(str, reasons)))
    return result.vector


def run_trials(
    pairs: list[tuple[Path, Path, bool]],
    vectorizer: Callable[[Path], np.ndarray],
    threshold: float,
) -> list[Trial]:
    cache: dict[Path, np.ndarray] = {}
    output: list[Trial] = []
    for path_a, path_b, same in pairs:
        try:
            for path in (path_a, path_b):
                if not path.exists() or not path.is_file():
                    raise ValueError(f"file not found: {path}")
                if path not in cache:
                    cache[path] = vectorizer(path)
            similarity = cosine_similarity(cache[path_a], cache[path_b])
            output.append(Trial(str(path_a), str(path_b), same, similarity, similarity >= threshold))
        except Exception as exc:
            output.append(Trial(str(path_a), str(path_b), same, None, None, str(exc)))
    return output


def metrics(trials: list[Trial], threshold: float) -> dict[str, object]:
    valid = [trial for trial in trials if trial.similarity is not None]
    positives = [trial for trial in valid if trial.same]
    negatives = [trial for trial in valid if not trial.same]
    true_accepts = sum(bool(trial.accepted) for trial in positives)
    false_rejects = len(positives) - true_accepts
    false_accepts = sum(bool(trial.accepted) for trial in negatives)
    true_rejects = len(negatives) - false_accepts
    far = false_accepts / len(negatives) if negatives else None
    frr = false_rejects / len(positives) if positives else None

    eer = None
    eer_threshold = None
    if positives and negatives:
        scores = sorted({float(trial.similarity) for trial in valid})
        candidates = [scores[0] - 1e-6, *scores, scores[-1] + 1e-6]
        best = None
        for candidate in candidates:
            candidate_far = sum(float(trial.similarity) >= candidate for trial in negatives) / len(negatives)
            candidate_frr = sum(float(trial.similarity) < candidate for trial in positives) / len(positives)
            difference = abs(candidate_far - candidate_frr)
            if best is None or difference < best[0]:
                best = (difference, (candidate_far + candidate_frr) / 2.0, candidate)
        assert best is not None
        eer, eer_threshold = best[1], best[2]

    def distribution(items: list[Trial]) -> dict[str, float | int | None]:
        values = [float(item.similarity) for item in items if item.similarity is not None]
        return {
            "count": len(values),
            "minimum": min(values) if values else None,
            "maximum": max(values) if values else None,
            "mean": float(np.mean(values)) if values else None,
            "standard_deviation": float(np.std(values)) if values else None,
        }

    return {
        "configured_threshold": threshold,
        "total_trials": len(trials),
        "valid_trials": len(valid),
        "failed_trials": len(trials) - len(valid),
        "positive_trials": len(positives),
        "negative_trials": len(negatives),
        "true_accepts": true_accepts,
        "false_rejects": false_rejects,
        "true_rejects": true_rejects,
        "false_accepts": false_accepts,
        "false_accept_rate": far,
        "false_reject_rate": frr,
        "eer_estimate": eer,
        "eer_threshold_estimate": eer_threshold,
        "positive_similarity_distribution": distribution(positives),
        "negative_similarity_distribution": distribution(negatives),
    }


def evaluate(kind: str, csv_path: Path, threshold: float) -> dict[str, object]:
    pairs = load_pairs(csv_path)
    if kind == "face":
        engine = FaceEngine()
        if not engine.available:
            raise FileNotFoundError("YuNet/SFace files are missing; run setup_agent5.ps1")
        trials = run_trials(pairs, lambda path: face_vector(engine, path), threshold)
        engine_name = "opencv-yunet-sface"
    else:
        engine = SpeakerEngine()
        if engine.mode != "ecapa-tdnn":
            raise FileNotFoundError("SpeechBrain ECAPA files are missing; run setup_agent5.ps1")
        trials = run_trials(pairs, lambda path: speaker_vector(engine, path), threshold)
        engine_name = engine.mode
    return {
        "kind": kind,
        "engine": engine_name,
        "pair_file": str(csv_path),
        "metrics": metrics(trials, threshold),
        "trials": [asdict(trial) for trial in trials],
        "limitations": [
            "Results apply only to the supplied consented evaluation fixtures and deployment hardware.",
            "Threshold selection must reflect the organization’s false-accept and false-reject risk tolerance.",
            "Small or unrepresentative samples do not establish production accuracy.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Agent5 face or speaker verification on a private, consented pair CSV.")
    parser.add_argument("--kind", choices=("face", "speaker"), required=True)
    parser.add_argument("--pairs", type=Path, required=True, help="CSV with path_a,path_b,same columns")
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    settings = get_settings()
    threshold = args.threshold
    if threshold is None:
        threshold = settings.face_similarity_threshold if args.kind == "face" else settings.speaker_similarity_threshold
    result = evaluate(args.kind, args.pairs.expanduser().resolve(), float(threshold))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["metrics"], indent=2))
    return 0 if result["metrics"]["failed_trials"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
