from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from agents.proctoring_agent.config import get_settings  # noqa: E402
from agents.proctoring_agent.db import engine  # noqa: E402
from agents.proctoring_agent.main import app  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def command_version(command: str, args: list[str]) -> str | None:
    executable = shutil.which(command)
    if not executable:
        return None
    result = subprocess.run([executable, *args], capture_output=True, text=True, timeout=20, check=False)
    output = (result.stdout or result.stderr).splitlines()
    return output[0].strip() if result.returncode == 0 and output else None


def verify_models() -> list[dict[str, object]]:
    manifest = json.loads((ROOT / "models" / "model_manifest.json").read_text(encoding="utf-8"))
    results: list[dict[str, object]] = []
    for model in manifest["models"]:
        destination = ROOT / "models" / model["destination"]
        item: dict[str, object] = {"name": model["name"], "path": str(destination), "exists": destination.exists()}
        if destination.is_file() and model.get("sha256"):
            actual = sha256(destination)
            item.update({"sha256": actual, "checksum_ok": actual == model["sha256"]})
        elif destination.is_dir():
            missing = [name for name in model.get("required_files", []) if not (destination / name).exists()]
            item.update({"missing_files": missing, "checksum_ok": not missing})
            for relative, expected in model.get("checksums", {}).items():
                model_file = destination / relative
                if not model_file.exists() or sha256(model_file) != expected:
                    item["checksum_ok"] = False
        else:
            item["checksum_ok"] = False
        results.append(item)
    return results


def media_smoke(ffmpeg: str, ffprobe: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="agent5_verify_") as directory:
        path = Path(directory) / "smoke.webm"
        command = [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=10:duration=3",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=3",
            "-c:v",
            "libvpx-vp9",
            "-deadline",
            "realtime",
            "-cpu-used",
            "8",
            "-c:a",
            "libopus",
            "-shortest",
            str(path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr[-1000:]}
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if probe.returncode != 0:
            return {"ok": False, "error": probe.stderr[-1000:]}
        payload = json.loads(probe.stdout)
        streams = payload.get("streams", [])
        video = next((item for item in streams if item.get("codec_type") == "video"), None)
        audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
        duration = float(payload.get("format", {}).get("duration") or 0)
        return {
            "ok": bool(video and audio and duration >= 2.5),
            "duration": duration,
            "video_codec": video.get("codec_name") if video else None,
            "audio_codec": audio.get("codec_name") if audio else None,
            "size_bytes": path.stat().st_size,
        }


def main() -> int:
    settings = get_settings()
    failures: list[str] = []
    react_index = settings.frontend_dir / "index.html"
    react_assets = settings.frontend_dir / "assets"
    report: dict[str, object] = {
        "platform": platform.platform(),
        "python": sys.version,
        "node": command_version("node", ["--version"]),
        "ffmpeg": command_version(settings.ffmpeg_path, ["-version"]),
        "ffprobe": command_version(settings.ffprobe_path, ["-version"]),
        "storage": str(settings.resolved_storage_dir),
        "database_url": settings.resolved_database_url,
        "react_frontend": {
            "index": str(react_index),
            "index_exists": react_index.exists(),
            "assets_exists": react_assets.exists(),
        },
    }
    if not react_index.exists() or not react_assets.exists():
        failures.append("React production build is missing; run npm run build in frontend")
    if sys.version_info[:2] != (3, 11):
        failures.append(f"Python 3.11 is required, found {sys.version.split()[0]}")
    node_text = str(report["node"] or "").lstrip("v").split("-")[0]
    try:
        node_parts = tuple(int(part) for part in node_text.split(".")[:3])
    except ValueError:
        node_parts = (0, 0, 0)
    if node_parts < (22, 12, 0) or node_parts >= (23, 0, 0):
        failures.append("Node.js 22.12 or newer in the Node 22 LTS line was not detected")
    ffmpeg = shutil.which(settings.ffmpeg_path)
    ffprobe = shutil.which(settings.ffprobe_path)
    if not ffmpeg or not ffprobe:
        failures.append("FFmpeg and FFprobe are required")
    else:
        report["media_smoke"] = media_smoke(ffmpeg, ffprobe)
        if not report["media_smoke"]["ok"]:  # type: ignore[index]
            failures.append("FFmpeg/FFprobe media smoke test failed")

    settings.ensure_directories()
    writable = settings.resolved_storage_dir / "tmp" / "write_test.txt"
    try:
        writable.write_text("agent5", encoding="utf-8")
        writable.unlink()
        report["storage_writable"] = True
    except OSError as exc:
        report["storage_writable"] = False
        failures.append(f"Storage is not writable: {exc}")

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        report["database"] = "ok"
    except Exception as exc:  # pragma: no cover - runtime diagnostic
        report["database"] = f"error: {exc}"
        failures.append("Database connectivity failed")

    models = verify_models()
    report["models"] = models
    for model in models:
        if not model.get("exists") or not model.get("checksum_ok"):
            failures.append(f"Model validation failed: {model['name']}")

    with TestClient(app) as client:
        health = client.get("/health")
        ready = client.get("/ready")
        report["health"] = health.json()
        report["ready"] = ready.json()
        if health.status_code != 200 or health.json().get("status") != "ok":
            failures.append("Health endpoint failed")
        if ready.status_code != 200 or not ready.json().get("ready"):
            failures.append("Readiness endpoint is false")

    output = settings.resolved_storage_dir / "logs" / "runtime_verification.json"
    report["failures"] = failures
    output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    print(f"Runtime verification report: {output}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
