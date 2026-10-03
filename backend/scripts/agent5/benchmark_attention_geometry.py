from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import psutil

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from agents.proctoring_agent.ai.attention import AttentionAnalyzer, AttentionTemporalTracker


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * p))))
    return ordered[index]


def pose_landmarks(width: int, height: int) -> np.ndarray:
    model = np.asarray([
        (0.0, 0.0, 0.0), (0.0, -63.6, -12.5), (-43.3, 32.7, -26.0),
        (43.3, 32.7, -26.0), (-28.9, -28.9, -24.1), (28.9, -28.9, -24.1),
    ], dtype=np.float64)
    camera = np.asarray([[640.0, 0.0, width / 2], [0.0, 640.0, height / 2], [0.0, 0.0, 1.0]], dtype=np.float64)
    projected, _ = cv2.projectPoints(model, np.zeros((3, 1)), np.asarray([[0.0], [0.0], [700.0]]), camera, np.zeros((4, 1)))
    points = np.zeros((478, 3), dtype=np.float64)
    for index, point in zip((1, 152, 33, 263, 61, 291), projected.reshape(-1, 2)):
        points[index, :2] = (point[0] / width, point[1] / height)
    return points


def gaze_landmarks(width: int, height: int) -> np.ndarray:
    points = pose_landmarks(width, height)
    coordinates = {
        33: (220, 205), 133: (295, 205), 159: (258, 194), 145: (258, 218),
        362: (345, 205), 263: (420, 205), 386: (382, 194), 374: (382, 218),
    }
    for index, (x, y) in coordinates.items():
        points[index, :2] = (x / width, y / height)
    for index in AttentionAnalyzer.LEFT_IRIS:
        points[index, :2] = (258 / width, 206 / height)
    for index in AttentionAnalyzer.RIGHT_IRIS:
        points[index, :2] = (382 / width, 206 / height)
    return points


def measure(function, iterations: int) -> list[float]:
    values: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        function()
        values.append((time.perf_counter_ns() - started) / 1_000_000.0)
    return values


def stats(values: list[float]) -> dict[str, float]:
    return {
        "iterations": len(values),
        "mean_ms": round(statistics.fmean(values), 6),
        "median_ms": round(statistics.median(values), 6),
        "p95_ms": round(percentile(values, 0.95), 6),
        "max_ms": round(max(values), 6),
    }


def main() -> None:
    width, height = 640, 480
    analyzer = AttentionAnalyzer()
    image = np.random.default_rng(42).integers(20, 230, size=(height, width, 3), dtype=np.uint8)
    pose_points = pose_landmarks(width, height)
    gaze_points = gaze_landmarks(width, height)
    process = psutil.Process(os.getpid())
    memory_before = process.memory_info().rss
    cpu_before = process.cpu_times().user + process.cpu_times().system
    wall_before = time.perf_counter()

    pose_values = measure(lambda: analyzer._head_pose(pose_points, width, height), 5000)
    gaze_values = measure(lambda: analyzer._gaze(image, gaze_points, width, height), 5000)
    tracker = AttentionTemporalTracker()
    tick = 0
    def tracker_call():
        nonlocal tick
        tick += 200
        tracker.update(
            "benchmark", combined_state="combined_look_away", direction="left", confidence=0.9,
            relative_ms=tick, confirm_ms=2500, confirm_count=3, recovery_ms=1200,
        )
    tracker_values = measure(tracker_call, 5000)

    wall = time.perf_counter() - wall_before
    cpu_after = process.cpu_times().user + process.cpu_times().system
    memory_after = process.memory_info().rss
    result = {
        "scope": "Synthetic geometry/state-machine benchmark only; excludes MediaPipe landmark inference, camera capture, network, database, and FFmpeg.",
        "environment": {
            "python": os.sys.version.split()[0],
            "opencv": cv2.__version__,
            "numpy": np.__version__,
            "logical_cpu_count": psutil.cpu_count(logical=True),
        },
        "head_pose_solvepnp": stats(pose_values),
        "gaze_iris_geometry": stats(gaze_values),
        "temporal_tracker": stats(tracker_values),
        "process": {
            "wall_seconds": round(wall, 4),
            "cpu_seconds": round(cpu_after - cpu_before, 4),
            "single_process_cpu_percent_of_one_core": round(100.0 * (cpu_after - cpu_before) / max(wall, 1e-9), 2),
            "rss_before_bytes": memory_before,
            "rss_after_bytes": memory_after,
            "rss_delta_bytes": memory_after - memory_before,
        },
        "not_measured": [
            "MediaPipe Face Landmarker inference latency",
            "webcam end-to-end event latency",
            "real-device CPU and memory",
            "real-device dropped frames",
        ],
    }
    output = PROJECT_ROOT / "validation_logs" / "attention_geometry_benchmark.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
