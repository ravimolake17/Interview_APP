from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import psutil
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from agents.proctoring_agent.ai.audio import MFCCSpeakerEmbedder, analyze_quality  # noqa: E402
from agents.proctoring_agent.services.recordings import ffprobe  # noqa: E402


def timed(label: str, callback, iterations: int = 1) -> dict[str, float | str]:
    process = psutil.Process(os.getpid())
    before = process.memory_info().rss
    started = time.perf_counter()
    for _ in range(iterations):
        callback()
    elapsed = time.perf_counter() - started
    after = process.memory_info().rss
    return {
        "name": label,
        "iterations": iterations,
        "total_seconds": round(elapsed, 6),
        "mean_ms": round(elapsed * 1000 / iterations, 3),
        "rss_before_mb": round(before / 1024**2, 3),
        "rss_after_mb": round(after / 1024**2, 3),
        "rss_delta_mb": round((after - before) / 1024**2, 3),
    }


def main() -> int:
    sample_rate = 16000
    seconds = 6
    time_axis = np.arange(sample_rate * seconds, dtype=np.float32) / sample_rate
    signal = (0.13 * np.sin(2 * np.pi * 190 * time_axis) + 0.05 * np.sin(2 * np.pi * 360 * time_axis)).astype(np.float32)
    results = [
        timed("audio_quality_6s", lambda: analyze_quality(signal, sample_rate), 20),
        timed("mfcc_embedding_6s", lambda: MFCCSpeakerEmbedder.encode(signal, sample_rate), 20),
    ]
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        with tempfile.TemporaryDirectory(prefix="agent5_benchmark_") as directory:
            wav = Path(directory) / "signal.wav"
            media = Path(directory) / "media.webm"
            sf.write(wav, signal, sample_rate)
            command = [
                "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=15:duration=10",
                "-i", str(wav), "-c:v", "libvpx-vp9", "-deadline", "realtime", "-cpu-used", "8",
                "-c:a", "libopus", "-shortest", str(media),
            ]
            results.append(timed("ffmpeg_create_10s_webm", lambda: subprocess.run(command, check=True, capture_output=True), 1))
            results.append(timed("ffprobe_10s_webm", lambda: ffprobe(media), 10))
    report = {
        "scope": "container CPU microbenchmark; not the target Windows host and not a full production model benchmark",
        "platform": platform.platform(),
        "python": sys.version,
        "logical_cpu_count": psutil.cpu_count(logical=True),
        "physical_cpu_count": psutil.cpu_count(logical=False),
        "memory_total_gb": round(psutil.virtual_memory().total / 1024**3, 3),
        "results": results,
    }
    output = ROOT / "docs" / "validation" / "cpu_memory_benchmark.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
