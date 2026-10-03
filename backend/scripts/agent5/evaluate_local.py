from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from agents.proctoring_agent.ai.audio import MFCCSpeakerEmbedder  # noqa: E402
from agents.proctoring_agent.ai.common import cosine_similarity  # noqa: E402
from agents.proctoring_agent.ai.face import FaceEngine  # noqa: E402
from agents.proctoring_agent.config import get_settings  # noqa: E402


def create_speech(path: Path, voice: str, text: str, speed: int, amplitude: float = 1.0, noise: float = 0.0) -> None:
    if not shutil.which("espeak"):
        raise RuntimeError("eSpeak is required for the local synthetic speaker evaluation")
    subprocess.run(["espeak", "-v", voice, "-s", str(speed), "-w", str(path), text], check=True, capture_output=True)
    signal, sample_rate = sf.read(path, dtype="float32")
    signal = np.asarray(signal, dtype=np.float32) * amplitude
    if noise:
        rng = np.random.default_rng(5005)
        signal = signal + rng.normal(0.0, noise, size=signal.shape).astype(np.float32)
    signal = np.clip(signal, -0.98, 0.98)
    sf.write(path, signal, sample_rate)


def speaker_evaluation() -> dict[str, object]:
    texts = [
        "Agent five validates the enrolled speaker throughout this interview session.",
        "Consistent effort and honest work create reliable professional results.",
        "The candidate speaks naturally during this secure online interview.",
    ]
    trials: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="agent5_speaker_eval_") as directory:
        root = Path(directory)
        baseline_path = root / "baseline.wav"
        create_speech(baseline_path, "en-us+m1", texts[0], 145)
        baseline_signal, baseline_rate = sf.read(baseline_path, dtype="float32")
        baseline = MFCCSpeakerEmbedder.encode(baseline_signal, baseline_rate)
        cases = [
            ("same_sentence", "en-us+m1", texts[0], 145, 1.0, 0.0, True),
            ("same_new_sentence", "en-us+m1", texts[1], 155, 1.0, 0.0, True),
            ("same_soft", "en-us+m1", texts[2], 135, 0.35, 0.0, True),
            ("same_loud", "en-us+m1", texts[1], 165, 1.55, 0.0, True),
            ("same_noise", "en-us+m1", texts[2], 150, 0.9, 0.006, True),
            ("different_female", "en-us+f3", texts[0], 170, 1.0, 0.0, False),
            ("different_male", "en-us+m3", texts[1], 135, 1.0, 0.0, False),
            ("different_female_2", "en-us+f2", texts[2], 180, 0.8, 0.003, False),
        ]
        threshold = 0.80
        for index, (name, voice, text, speed, amplitude, noise, expected_same) in enumerate(cases):
            path = root / f"trial_{index}.wav"
            create_speech(path, voice, text, speed, amplitude, noise)
            signal, sample_rate = sf.read(path, dtype="float32")
            vector = MFCCSpeakerEmbedder.encode(signal, sample_rate)
            similarity = cosine_similarity(baseline, vector)
            predicted_same = similarity >= threshold
            trials.append(
                {
                    "case": name,
                    "expected_same": expected_same,
                    "predicted_same": predicted_same,
                    "similarity": round(similarity, 6),
                    "threshold": threshold,
                }
            )
    positives = [trial for trial in trials if trial["expected_same"]]
    negatives = [trial for trial in trials if not trial["expected_same"]]
    ta = sum(bool(trial["predicted_same"]) for trial in positives)
    fr = len(positives) - ta
    fa = sum(bool(trial["predicted_same"]) for trial in negatives)
    tr = len(negatives) - fa
    return {
        "engine": MFCCSpeakerEmbedder.name,
        "status": "degraded-fallback-only",
        "threshold": threshold,
        "same_speaker_trials": len(positives),
        "different_speaker_trials": len(negatives),
        "true_accepts": ta,
        "false_rejects": fr,
        "true_rejects": tr,
        "false_accepts": fa,
        "false_accept_rate": fa / len(negatives) if negatives else None,
        "false_reject_rate": fr / len(positives) if positives else None,
        "trials": trials,
        "limitation": "Synthetic eSpeak trials do not validate ECAPA-TDNN or real human speaker verification. The fallback is not accepted as production identity verification.",
    }


def face_evaluation() -> dict[str, object]:
    engine = FaceEngine()
    missing = []
    if not engine.detector_path.exists():
        missing.append(str(engine.detector_path))
    if not engine.recognizer_path.exists():
        missing.append(str(engine.recognizer_path))
    return {
        "engine": "OpenCV YuNet + SFace",
        "status": "not-run" if missing else "models-present-no-consented-pair-fixtures",
        "missing_model_files": missing,
        "positive_pairs": 0,
        "negative_pairs": 0,
        "limitation": "No consented real-person pair fixture is redistributed. Run scripts/evaluate_private_biometrics.py with a locally approved evaluation set before deployment.",
    }


def main() -> int:
    output_dir = ROOT / "docs" / "validation"
    output_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "environment": {
            "python": sys.version,
            "platform": sys.platform,
            "models_directory": str(get_settings().models_dir),
        },
        "face": face_evaluation(),
        "speaker": speaker_evaluation() if shutil.which("espeak") else {"status": "not-run", "reason": "eSpeak unavailable"},
    }
    json_path = output_dir / "model_evaluation_local.json"
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    csv_path = output_dir / "speaker_evaluation_trials.csv"
    trials = data.get("speaker", {}).get("trials", [])
    if trials:
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(trials[0]))
            writer.writeheader()
            writer.writerows(trials)
    print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
