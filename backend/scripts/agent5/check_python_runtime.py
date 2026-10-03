from __future__ import annotations

import importlib
import json
import platform
import struct
import sys

REQUIRED_IMPORTS = {
    "fastapi": "FastAPI",
    "uvicorn": "Uvicorn",
    "sqlalchemy": "SQLAlchemy",
    "alembic": "Alembic",
    "pydantic": "Pydantic",
    "cv2": "OpenCV",
    "numpy": "NumPy",
    "torch": "PyTorch",
    "torchaudio": "Torchaudio",
    "speechbrain": "SpeechBrain",
    "librosa": "librosa",
    "soundfile": "SoundFile",
    "mediapipe": "MediaPipe",
    "playwright": "Playwright",
    "reportlab": "ReportLab",
    "cryptography": "cryptography",
    "argon2": "argon2-cffi",
}


def main() -> int:
    failures: list[str] = []
    imports: dict[str, dict[str, object]] = {}
    if sys.version_info[:2] != (3, 11):
        failures.append(f"Python 3.11 is required; found {sys.version.split()[0]}")
    bits = struct.calcsize("P") * 8
    if bits != 64:
        failures.append(f"64-bit Python is required; found {bits}-bit")

    for module_name, label in REQUIRED_IMPORTS.items():
        try:
            module = importlib.import_module(module_name)
            imports[module_name] = {
                "ready": True,
                "label": label,
                "version": getattr(module, "__version__", None),
            }
        except Exception as exc:
            imports[module_name] = {
                "ready": False,
                "label": label,
                "error": f"{type(exc).__name__}: {exc}",
            }
            failures.append(f"{label} import failed: {type(exc).__name__}: {exc}")

    try:
        import torch

        torch_details = {
            "version": torch.__version__,
            "cuda_available": bool(torch.cuda.is_available()),
            "device": "cpu",
        }
        if "+cpu" not in str(torch.__version__) and torch.cuda.is_available():
            failures.append("CPU-only PyTorch is required for the supported Agent5 runtime")
    except Exception as exc:
        torch_details = {"error": f"{type(exc).__name__}: {exc}"}

    report = {
        "ready": not failures,
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "architecture_bits": bits,
        "imports": imports,
        "torch": torch_details,
        "failures": failures,
    }
    print(json.dumps(report, indent=2, default=str))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
