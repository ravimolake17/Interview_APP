from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from sqlalchemy import select, text

import numpy as np

from .api import admin, candidate, media, monitoring, recording, ws
from .config import get_settings
from .db import SessionLocal, engine, init_db
from .models import InterviewSession
from .runtime import face_engine, pose_gaze_engine, speaker_engine

logger = logging.getLogger("agent5")
settings = get_settings()


class InMemoryRateLimiter:
    def __init__(self, requests: int = 180, window_seconds: int = 60, max_keys: int = 5000) -> None:
        self.requests = requests
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allowed(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            # Bound memory even if a hostile client generates many path/IP keys.
            if key not in self.hits and len(self.hits) >= self.max_keys:
                stale = [name for name, queue in self.hits.items() if not queue or now - queue[-1] > self.window_seconds]
                for name in stale:
                    self.hits.pop(name, None)
                if len(self.hits) >= self.max_keys:
                    oldest = min(self.hits, key=lambda name: self.hits[name][-1] if self.hits[name] else float("-inf"))
                    self.hits.pop(oldest, None)
            q = self.hits[key]
            while q and now - q[0] > self.window_seconds:
                q.popleft()
            if len(q) >= self.requests:
                return False
            q.append(now)
            return True


general_limiter = InMemoryRateLimiter(requests=240, window_seconds=60)
stream_limiters = {
    "analyze-frame": InMemoryRateLimiter(requests=180, window_seconds=60),
    "analyze-audio": InMemoryRateLimiter(requests=30, window_seconds=60),
    "recording-chunks": InMemoryRateLimiter(requests=90, window_seconds=60),
}


def _rate_limit_bucket(path: str) -> tuple[str, InMemoryRateLimiter]:
    # High-frequency interview streams must not share one limiter bucket.
    # The old key grouped every /api/sessions/<id>/... route together, so
    # frame, audio and recording uploads exhausted 180 requests/minute.
    if path.endswith("/analyze-frame"):
        return "analyze-frame", stream_limiters["analyze-frame"]
    if path.endswith("/analyze-audio"):
        return "analyze-audio", stream_limiters["analyze-audio"]
    if path.endswith("/recording/chunks"):
        return "recording-chunks", stream_limiters["recording-chunks"]
    return "general", general_limiter


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.validate_runtime_security()
    settings.validate_runtime_configuration()
    settings.ensure_directories()
    init_db()
    with SessionLocal() as db:
        legacy_terminating = db.scalars(select(InterviewSession).where(InterviewSession.status == "terminating")).all()
        for session in legacy_terminating:
            session.status = "terminated"
            session.termination_reason = session.termination_reason or "interrupted_termination_recovery"
            session.ended_at = session.ended_at or session.termination_requested_at or session.started_at or session.created_at
            logger.warning("Recovered legacy terminating session as terminated", extra={"session_id": session.id})
        db.commit()
    logger.info("Agent5 startup complete")
    yield
    engine.dispose()


app = FastAPI(
    title="Agent5 Fraud Detection API",
    version=settings.app_version,
    description="Local-first interview proctoring decision-support system. AI events require human review.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Chunk-Checksum"],
)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])


@app.middleware("http")
async def security_and_rate_limit(request: Request, call_next):
    client = request.client.host if request.client else "unknown"
    bucket, active_limiter = _rate_limit_bucket(request.url.path)
    key = f"{client}:{bucket}"
    if request.url.path.startswith("/api/") and not active_limiter.allowed(key):
        logger.warning("rate_limit_exceeded", extra={"client": client, "bucket": bucket, "path": request.url.path})
        return JSONResponse(
            status_code=429,
            content={"detail": "rate limit exceeded", "bucket": bucket, "retry_after_seconds": 1},
            headers={"Retry-After": "1"},
        )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(self), geolocation=()"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    if request.url.path.startswith(("/candidate", "/monitor", "/proctoring")):
        interview_origin = (os.getenv("INTERVIEW_API_PUBLIC_URL") or "").rstrip("/")
        connect_src = "'self' ws: wss: blob:"
        if interview_origin:
            connect_src = f"{connect_src} {interview_origin}"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; "
            f"connect-src {connect_src}; style-src 'self' 'unsafe-inline'; script-src 'self'"
        )
    return response


app.include_router(candidate.router)
app.include_router(monitoring.router)
app.include_router(recording.router)
app.include_router(admin.router)
app.include_router(media.router)
app.include_router(ws.router)


@app.get("/api/runtime-config")
def runtime_config():
    """Tell the browser where Agent 4 (interview API) lives when VMs are split."""
    origin = (os.getenv("INTERVIEW_API_PUBLIC_URL") or "").strip().rstrip("/")
    return {"interview_api_origin": origin}


@app.get("/health/live")
def health_live():
    return {"status": "ok"}


@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database = "ok"
    except Exception as exc:
        database = f"error: {exc}"
    return {"status": "ok" if database == "ok" else "degraded", "database": database, "version": settings.app_version}


@lru_cache(maxsize=1)
def _model_integrity_report() -> dict[str, dict[str, object]]:
    """Validate every pinned model asset against the release manifest.

    The setup/start scripts run the same verification before launching. The
    endpoint repeats it inside the running process so readiness is not inferred
    from file existence alone.
    """
    manifest_path = settings.models_dir / "model_manifest.json"
    report: dict[str, dict[str, object]] = {}
    if not manifest_path.is_file():
        return {"manifest": {"ready": False, "error": f"missing manifest: {manifest_path}"}}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"manifest": {"ready": False, "error": f"{type(exc).__name__}: {exc}"}}

    def checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    for item in manifest.get("models", []):
        name = str(item.get("name", "unknown"))
        destination = settings.models_dir / str(item.get("destination", ""))
        errors: list[str] = []
        files: dict[str, object] = {}
        if item.get("source_type") == "url":
            if not destination.is_file():
                errors.append(f"missing file: {destination}")
            else:
                expected_size = item.get("size_bytes")
                if expected_size is not None and destination.stat().st_size != int(expected_size):
                    errors.append(f"size mismatch: expected {expected_size}, got {destination.stat().st_size}")
                actual = checksum(destination)
                expected = str(item.get("sha256") or "").lower()
                if expected and actual.lower() != expected:
                    errors.append(f"sha256 mismatch: {actual}")
                files[destination.name] = {"path": str(destination), "sha256": actual, "size_bytes": destination.stat().st_size}
        else:
            for relative in item.get("required_files", []):
                path = destination / str(relative)
                if not path.is_file():
                    errors.append(f"missing file: {relative}")
                    continue
                actual = checksum(path)
                expected_size = item.get("sizes", {}).get(relative)
                expected = str(item.get("checksums", {}).get(relative) or "").lower()
                if expected_size is not None and path.stat().st_size != int(expected_size):
                    errors.append(f"size mismatch for {relative}: expected {expected_size}, got {path.stat().st_size}")
                if expected and actual.lower() != expected:
                    errors.append(f"sha256 mismatch for {relative}: {actual}")
                files[str(relative)] = {"path": str(path), "sha256": actual, "size_bytes": path.stat().st_size}
        report[name] = {
            "ready": not errors,
            "path": str(destination),
            "version": item.get("revision") or item.get("version") or item.get("model_version"),
            "checksum_ok": not errors,
            "errors": errors,
            "files": files,
        }
    return report


@lru_cache(maxsize=1)
def _mandatory_model_self_test() -> dict[str, dict[str, object]]:
    """Load mandatory CPU engines and execute one finite inference per engine."""
    if settings.test_mode:
        return {
            "face": {"ready": True, "inference_test": "test_mode_fixture"},
            "attention": {"ready": True, "inference_test": "test_mode_fixture"},
            "speaker": {"ready": True, "inference_test": "test_mode_fixture"},
        }
    results: dict[str, dict[str, object]] = {}
    blank = np.zeros((320, 320, 3), dtype=np.uint8)

    started = time.perf_counter()
    try:
        faces = face_engine.detect(blank)
        synthetic = np.full((320, 320, 3), 127, dtype=np.uint8)
        synthetic_face = np.array(
            [80, 50, 160, 210, 125, 120, 195, 120, 160, 155, 132, 205, 188, 205, 0.99],
            dtype=np.float32,
        )
        embedding = face_engine.embedding(synthetic, synthetic_face)
        valid = faces.ndim == 2 and embedding.shape == (128,) and np.isfinite(embedding).all()
        results["face"] = {
            "ready": bool(valid),
            "engine": face_engine.engine_name,
            "model_version": face_engine.model_version,
            "device": "cpu",
            "embedding_shape": list(embedding.shape),
            "inference_latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": None if valid else "unexpected face inference output",
        }
    except Exception as exc:
        results["face"] = {"ready": False, "engine": getattr(face_engine, "engine_name", "unknown"), "device": "cpu", "error": f"{type(exc).__name__}: {exc}"}

    started = time.perf_counter()
    try:
        landmarks = pose_gaze_engine.provider.detect(blank)
        results["attention"] = {
            "ready": True,
            "engine": getattr(pose_gaze_engine.provider, "model_name", "mediapipe-face-landmarker"),
            "model_version": getattr(pose_gaze_engine.provider, "package_version", "unknown"),
            "device": "cpu",
            "blank_frame_result": "no_face_expected" if landmarks is None else "landmarks_returned",
            "inference_latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": None,
        }
    except Exception as exc:
        results["attention"] = {"ready": False, "engine": "mediapipe-face-landmarker", "device": "cpu", "error": f"{type(exc).__name__}: {exc}"}

    started = time.perf_counter()
    try:
        sample_rate = 16000
        t = np.arange(sample_rate * 3, dtype=np.float32) / sample_rate
        signal = (0.15 * np.sin(2 * np.pi * 190 * t)).astype(np.float32)
        vector = speaker_engine.encode(signal, sample_rate)
        valid = vector.ndim == 1 and vector.size >= 128 and np.isfinite(vector).all()
        results["speaker"] = {
            "ready": bool(valid),
            "engine": speaker_engine.engine_name,
            "model_version": speaker_engine.model_version,
            "device": "cpu",
            "embedding_shape": list(vector.shape),
            "inference_latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": None if valid else "unexpected speaker embedding",
        }
    except Exception as exc:
        results["speaker"] = {"ready": False, "engine": getattr(speaker_engine, "engine_name", "unknown"), "device": "cpu", "error": f"{type(exc).__name__}: {exc}"}
    return results


def _database_readiness() -> dict[str, object]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            table_exists = connection.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = :schema AND table_name = 'sessions'"
                    ")"
                ),
                {"schema": "agent5"},
            ).scalar_one()
            migration_ok = bool(table_exists or settings.test_mode)
            return {
                "ready": migration_ok,
                "connectivity": "ok",
                "backend": "postgresql",
                "schema": "agent5",
                "migration_ok": migration_ok,
                "error": None if migration_ok else "agent5 schema tables are not initialized",
            }
    except Exception as exc:
        return {"ready": False, "connectivity": "error", "migration_ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _storage_readiness() -> dict[str, object]:
    settings.ensure_directories()
    required = [
        settings.resolved_storage_dir / "recordings",
        settings.resolved_storage_dir / "chunks",
        settings.resolved_storage_dir / "evidence" / "screenshots",
        settings.resolved_storage_dir / "evidence" / "video",
        settings.resolved_storage_dir / "evidence" / "audio",
        settings.resolved_storage_dir / "reports",
        settings.resolved_storage_dir / "tmp",
    ]
    errors: list[str] = []
    for directory in required:
        probe = directory / f".ready_{os.getpid()}_{threading.get_ident()}"
        try:
            probe.write_text("agent5", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            errors.append(f"{directory}: {exc}")
    return {"ready": not errors, "root": str(settings.resolved_storage_dir), "writable_directories": [str(item) for item in required], "errors": errors}


@app.get("/ready")
def readiness():
    database = _database_readiness()
    storage = _storage_readiness()
    ffmpeg_path = shutil.which(settings.ffmpeg_path)
    ffprobe_path = shutil.which(settings.ffprobe_path)
    media = {
        "ready": bool(ffmpeg_path and ffprobe_path),
        "ffmpeg": ffmpeg_path,
        "ffprobe": ffprobe_path,
    }
    frontend_index = settings.frontend_dir / "index.html"
    frontend_assets = settings.frontend_dir / "assets"
    frontend = {
        "ready": frontend_index.is_file() and frontend_assets.is_dir(),
        "index": str(frontend_index),
        "assets": str(frontend_assets),
    }
    integrity = _model_integrity_report()
    model_integrity_ready = bool(integrity) and all(bool(item.get("ready")) for item in integrity.values())
    self_tests = _mandatory_model_self_test()
    model_inference_ready = all(bool(item.get("ready")) for item in self_tests.values())

    face_test = self_tests.get("face", {})
    attention_test = self_tests.get("attention", {})
    speaker_test = self_tests.get("speaker", {})
    models = {
        # Backward-compatible fields used by the candidate UI and scripts.
        "face_detection_yunet": face_engine.detector_path.exists(),
        "face_recognition_sface": face_engine.recognizer_path.exists(),
        "face_engine_ready": bool(face_test.get("ready")),
        "face_engine_error": face_test.get("error"),
        "attention_face_landmarker": bool(attention_test.get("ready")),
        "attention_model_path": str(getattr(getattr(pose_gaze_engine, "provider", None), "model_path", "")),
        "attention_model_checksum": getattr(getattr(pose_gaze_engine, "provider", None), "installed_asset_checksum", lambda: None)(),
        "attention_engine_error": attention_test.get("error"),
        "speaker": {
            **speaker_engine.readiness(load=False),
            **speaker_test,
        },
        "integrity_ready": model_integrity_ready,
        "integrity": integrity,
        "inference_tests": self_tests,
    }
    production_ready = all(
        (
            bool(database.get("ready")),
            bool(storage.get("ready")),
            bool(media.get("ready")),
            bool(frontend.get("ready")),
            model_integrity_ready,
            model_inference_ready,
        )
    )
    if settings.test_mode:
        # Test mode uses deterministic fixture engines and metadata-created
        # schemas. Media, database and storage must still be genuinely usable.
        production_ready = all((bool(database.get("ready")), bool(storage.get("ready")), bool(media.get("ready"))))
    return {
        "ready": bool(production_ready),
        "database": database,
        "storage": storage,
        "media": media,
        "frontend": frontend,
        "models": models,
        "ffmpeg": bool(media.get("ready")),
        "test_mode": settings.test_mode,
    }


@app.get("/")
def root():
    return RedirectResponse(url="/proctoring/")


frontend = settings.frontend_dir
if frontend.exists():
    app.mount("/ui", StaticFiles(directory=str(frontend), html=False), name="ui")
    assets = frontend / "assets"
    if assets.is_dir():
        app.mount(
            "/proctoring/assets",
            StaticFiles(directory=str(assets), html=False),
            name="agent5-proctoring-assets",
        )


def _react_index():
    path = frontend / "index.html"
    if not path.exists():
        return JSONResponse(
            status_code=503,
            content={"detail": "Proctoring UI is not built. From repo root run: cd frontend && npm install && npm run build"},
        )
    return FileResponse(path, headers={"Cache-Control": "no-cache"})


@app.get("/proctoring/")
def proctoring_page():
    return _react_index()


@app.get("/candidate/")
def candidate_page():
    return _react_index()


@app.get("/monitor/")
def admin_page():
    return _react_index()
