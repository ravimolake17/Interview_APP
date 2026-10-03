from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

AGENT5_DB_SCHEMA = "agent5"

# Load backend/.env so standalone scripts and Agent5 settings see DATABASE_URL.
# config.py lives at backend/agents/proctoring_agent/config.py → parents[2] = backend
_BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(_BACKEND_DIR / ".env", override=False)


def resolve_shared_database_url() -> str | None:
    """Use the same PostgreSQL database as the main HR app when configured."""
    explicit = (os.getenv("AGENT5_DATABASE_URL") or "").strip()
    if explicit:
        return explicit

    checkpoint = (os.getenv("CHECKPOINT_DB_URL") or "").strip()
    if checkpoint:
        return checkpoint

    database = (os.getenv("DATABASE_URL") or "").strip()
    if database.startswith("postgresql+asyncpg://"):
        return "postgresql://" + database.removeprefix("postgresql+asyncpg://")
    if database.startswith("postgresql://"):
        return database
    return None


class Settings(BaseModel):
    app_name: str = "Agent5"
    app_version: str = "0.4.0"
    # Project root (Interview_Agentic_AI/), not backend/
    root_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3])
    storage_dir: Path | None = None
    database_url: str | None = None
    secret_key: str = "change-this-development-secret-before-real-use"
    candidate_token_minutes: int = 720
    admin_token_minutes: int = 480
    cors_origins: list[str] = ["http://127.0.0.1:8001", "http://localhost:8001"]
    face_similarity_threshold: float = 0.363
    face_detection_score_threshold: float = 0.55
    face_enrollment_min_samples: int = 3
    face_enrollment_max_samples: int = 5
    face_enrollment_duplicate_similarity: float = 0.9995
    speaker_similarity_threshold: float = 0.25
    tab_switch_dedupe_seconds: float = 1.25
    tab_switch_min_hidden_seconds: float = 0.35
    evidence_pre_seconds: float = 5.0
    evidence_post_seconds: float = 7.0
    max_upload_mb: int = 50
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    retention_days: int = 30
    test_mode: bool = False
    anti_spoof_live_class: int = 0
    no_face_confirm_seconds: float = 2.0
    no_face_confirm_count: int = 3
    multiple_faces_confirm_seconds: float = 1.2
    multiple_faces_confirm_count: int = 2
    face_mismatch_confirm_seconds: float = 2.0
    face_mismatch_confirm_count: int = 3
    face_mismatch_min_confidence: float = 0.55
    gaze_confirm_seconds: float = 2.5
    gaze_confirm_count: int = 3
    gaze_min_confidence: float = 0.28
    head_pose_min_confidence: float = 0.30
    attention_yaw_enter_degrees: float = 16.0
    attention_pitch_enter_degrees: float = 13.0
    attention_roll_enter_degrees: float = 16.0
    attention_gaze_horizontal_offset: float = 0.075
    attention_gaze_vertical_offset: float = 0.09
    attention_hysteresis_ratio: float = 0.72
    attention_blink_ear_threshold: float = 0.115
    head_pose_confirm_seconds: float = 2.2
    head_pose_confirm_count: int = 3
    attention_recovery_seconds: float = 1.2
    attention_frame_interval_ms: int = 750
    attention_baseline_min_samples: int = 10
    attention_baseline_window_samples: int = 18
    attention_baseline_min_span_seconds: float = 1.8
    attention_baseline_event_suppression_seconds: float = 3.0
    attention_baseline_fallback_seconds: float = 8.0
    attention_baseline_min_confidence: float = 0.50
    attention_baseline_max_abs_yaw_degrees: float = 16.0
    attention_baseline_max_abs_pitch_degrees: float = 14.0
    attention_baseline_max_abs_roll_degrees: float = 12.0
    attention_baseline_max_mad_yaw_degrees: float = 3.5
    attention_baseline_max_mad_pitch_degrees: float = 3.5
    attention_baseline_max_mad_roll_degrees: float = 3.0
    attention_baseline_fallback_threshold_multiplier: float = 1.35
    attention_baseline_fallback_confirmation_multiplier: float = 1.35
    attention_baseline_fallback_risk_scale: float = 0.50
    voice_mismatch_confirm_seconds: float = 3.0
    voice_mismatch_confirm_count: int = 2
    voice_mismatch_min_confidence: float = 0.55
    additional_speaker_confirm_seconds: float = 4.0
    additional_speaker_confirm_count: int = 2
    overlap_confirm_seconds: float = 4.0
    overlap_confirm_count: int = 2
    sentence_min_completion: float = 1.0
    sentence_max_skipped: int = 1
    sentence_max_incorrect: int = 1
    frame_request_timeout_seconds: float = 8.0
    audio_request_timeout_seconds: float = 25.0
    candidate_debug_payloads: bool = False

    def event_cooldowns(self) -> dict[str, float]:
        return {
            "face_mismatch": float(os.getenv("AGENT5_COOLDOWN_FACE_MISMATCH", "10")),
            "no_face": float(os.getenv("AGENT5_COOLDOWN_NO_FACE", "8")),
            "multiple_faces": float(os.getenv("AGENT5_COOLDOWN_MULTIPLE_FACES", "8")),
            "face_spoof_concern": float(os.getenv("AGENT5_COOLDOWN_FACE_SPOOF", "15")),
            "gaze_violation": float(os.getenv("AGENT5_COOLDOWN_GAZE", "8")),
            "head_pose_violation": float(os.getenv("AGENT5_COOLDOWN_HEAD_POSE", "8")),
            "attention_look_away": float(os.getenv("AGENT5_COOLDOWN_ATTENTION", "8")),
            "voice_mismatch": float(os.getenv("AGENT5_COOLDOWN_VOICE_MISMATCH", "12")),
            "possible_additional_speaker": float(os.getenv("AGENT5_COOLDOWN_ADDITIONAL_SPEAKER", "12")),
            "background_conversation": float(os.getenv("AGENT5_COOLDOWN_BACKGROUND_CONVERSATION", "12")),
            "overlapping_speech": float(os.getenv("AGENT5_COOLDOWN_OVERLAPPING_SPEECH", "12")),
            "camera_interruption": float(os.getenv("AGENT5_COOLDOWN_CAMERA_INTERRUPTION", "5")),
            "microphone_interruption": float(os.getenv("AGENT5_COOLDOWN_MICROPHONE_INTERRUPTION", "5")),
            "connection_loss": float(os.getenv("AGENT5_COOLDOWN_CONNECTION_LOSS", "5")),
            "recording_failure": float(os.getenv("AGENT5_COOLDOWN_RECORDING_FAILURE", "10")),
        }

    @property
    def resolved_storage_dir(self) -> Path:
        path = self.storage_dir or (self.root_dir / "storage")
        return Path(path).expanduser().resolve()

    @property
    def resolved_database_url(self) -> str:
        """PostgreSQL only — same DB as the HR app (schema agent5)."""
        url = self.database_url or resolve_shared_database_url()
        if not url:
            raise RuntimeError(
                "Agent5 requires PostgreSQL. Set DATABASE_URL, CHECKPOINT_DB_URL, "
                "or AGENT5_DATABASE_URL (postgresql://...)."
            )
        if not url.startswith("postgresql"):
            raise RuntimeError(
                f"Agent5 no longer supports SQLite. Got non-PostgreSQL URL scheme: {url.split(':', 1)[0]}"
            )
        return url

    @property
    def uses_postgres(self) -> bool:
        return True

    @property
    def models_dir(self) -> Path:
        override = os.getenv("AGENT5_MODELS_DIR")
        if override:
            return Path(override).expanduser().resolve()
        return (self.root_dir / "models" / "agent5").resolve()

    @property
    def frontend_dir(self) -> Path:
        override = os.getenv("AGENT5_FRONTEND_DIR")
        if override:
            return Path(override).expanduser().resolve()
        return (self.root_dir / "backend" / "agent5_static" / "dist").resolve()

    def validate_runtime_security(self) -> None:
        """Reject default signing secrets outside explicit test mode.

        HR reviewers use the main app JWT (public.users). Candidates use the
        hashed interview join link + short-lived session token — no Agent5 login.
        """
        if self.test_mode:
            return
        if self.secret_key == "change-this-development-secret-before-real-use" or len(self.secret_key) < 32:
            raise RuntimeError(
                "AGENT5_SECRET_KEY must be a unique secret of at least 32 characters "
                "(used to sign candidate session tokens, not a login password)"
            )

    def validate_runtime_configuration(self) -> None:
        """Fail fast on unsafe or internally inconsistent detector settings."""
        problems: list[str] = []

        def between(name: str, value: float, minimum: float, maximum: float) -> None:
            if not minimum <= float(value) <= maximum:
                problems.append(f"{name} must be between {minimum} and {maximum}; got {value}")

        def positive(name: str, value: float) -> None:
            if float(value) <= 0:
                problems.append(f"{name} must be greater than zero; got {value}")

        between("AGENT5_FACE_DETECTION_SCORE_THRESHOLD", self.face_detection_score_threshold, 0.05, 0.99)
        between("AGENT5_FACE_SIMILARITY_THRESHOLD", self.face_similarity_threshold, -1.0, 1.0)
        between("AGENT5_SPEAKER_SIMILARITY_THRESHOLD", self.speaker_similarity_threshold, -1.0, 1.0)
        between("AGENT5_GAZE_MIN_CONFIDENCE", self.gaze_min_confidence, 0.0, 1.0)
        between("AGENT5_HEAD_POSE_MIN_CONFIDENCE", self.head_pose_min_confidence, 0.0, 1.0)
        between("AGENT5_FACE_MISMATCH_MIN_CONFIDENCE", self.face_mismatch_min_confidence, 0.0, 1.0)
        between("AGENT5_VOICE_MISMATCH_MIN_CONFIDENCE", self.voice_mismatch_min_confidence, 0.0, 1.0)
        between("AGENT5_ATTENTION_HYSTERESIS_RATIO", self.attention_hysteresis_ratio, 0.1, 0.99)
        between("AGENT5_ATTENTION_BASELINE_FALLBACK_RISK_SCALE", self.attention_baseline_fallback_risk_scale, 0.0, 1.0)
        positive("AGENT5_ATTENTION_FRAME_INTERVAL_MS", self.attention_frame_interval_ms)
        positive("AGENT5_FRAME_REQUEST_TIMEOUT_SECONDS", self.frame_request_timeout_seconds)
        positive("AGENT5_AUDIO_REQUEST_TIMEOUT_SECONDS", self.audio_request_timeout_seconds)
        positive("AGENT5_TAB_SWITCH_DEDUPE_SECONDS", self.tab_switch_dedupe_seconds)
        if self.tab_switch_min_hidden_seconds < 0:
            problems.append("AGENT5_TAB_SWITCH_MIN_HIDDEN_SECONDS cannot be negative")
        if self.face_enrollment_min_samples < 2:
            problems.append("AGENT5_FACE_ENROLLMENT_MIN_SAMPLES must be at least 2")
        if self.face_enrollment_max_samples < self.face_enrollment_min_samples:
            problems.append("AGENT5_FACE_ENROLLMENT_MAX_SAMPLES must be greater than or equal to the minimum")
        for name, count in (
            ("AGENT5_NO_FACE_CONFIRM_COUNT", self.no_face_confirm_count),
            ("AGENT5_MULTIPLE_FACES_CONFIRM_COUNT", self.multiple_faces_confirm_count),
            ("AGENT5_FACE_MISMATCH_CONFIRM_COUNT", self.face_mismatch_confirm_count),
            ("AGENT5_GAZE_CONFIRM_COUNT", self.gaze_confirm_count),
            ("AGENT5_HEAD_POSE_CONFIRM_COUNT", self.head_pose_confirm_count),
            ("AGENT5_VOICE_MISMATCH_CONFIRM_COUNT", self.voice_mismatch_confirm_count),
        ):
            if int(count) < 1:
                problems.append(f"{name} must be at least 1; got {count}")
        if problems:
            raise RuntimeError("Invalid Agent5 runtime configuration: " + "; ".join(problems))

    def ensure_directories(self) -> None:
        base = self.resolved_storage_dir
        for rel in (
            "recordings",
            "chunks",
            "evidence/screenshots",
            "evidence/video",
            "evidence/audio",
            "evidence/metadata",
            "reports",
            "logs",
            "tmp",
        ):
            (base / rel).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    root = Path(os.getenv("AGENT5_ROOT", Path(__file__).resolve().parents[3]))
    storage = os.getenv("AGENT5_STORAGE_DIR")
    origins = os.getenv("AGENT5_CORS_ORIGINS")
    shared_db = resolve_shared_database_url()
    settings = Settings(
        root_dir=root,
        storage_dir=Path(storage) if storage else None,
        database_url=shared_db,
        secret_key=os.getenv("AGENT5_SECRET_KEY", "change-this-development-secret-before-real-use"),
        cors_origins=[x.strip() for x in origins.split(",")] if origins else ["http://127.0.0.1:8001", "http://localhost:8001"],
        face_similarity_threshold=float(os.getenv("AGENT5_FACE_SIMILARITY_THRESHOLD", "0.363")),
        face_detection_score_threshold=float(os.getenv("AGENT5_FACE_DETECTION_SCORE_THRESHOLD", "0.55")),
        face_enrollment_min_samples=int(os.getenv("AGENT5_FACE_ENROLLMENT_MIN_SAMPLES", "3")),
        face_enrollment_max_samples=int(os.getenv("AGENT5_FACE_ENROLLMENT_MAX_SAMPLES", "5")),
        face_enrollment_duplicate_similarity=float(os.getenv("AGENT5_FACE_ENROLLMENT_DUPLICATE_SIMILARITY", "0.9995")),
        speaker_similarity_threshold=float(os.getenv("AGENT5_SPEAKER_SIMILARITY_THRESHOLD", "0.25")),
        tab_switch_dedupe_seconds=float(os.getenv("AGENT5_TAB_SWITCH_DEDUPE_SECONDS", "1.25")),
        tab_switch_min_hidden_seconds=float(os.getenv("AGENT5_TAB_SWITCH_MIN_HIDDEN_SECONDS", "0.35")),
        evidence_pre_seconds=float(os.getenv("AGENT5_EVIDENCE_PRE_SECONDS", "5.0")),
        evidence_post_seconds=float(os.getenv("AGENT5_EVIDENCE_POST_SECONDS", "7.0")),
        max_upload_mb=int(os.getenv("AGENT5_MAX_UPLOAD_MB", "50")),
        ffmpeg_path=os.getenv("AGENT5_FFMPEG_PATH", "ffmpeg"),
        ffprobe_path=os.getenv("AGENT5_FFPROBE_PATH", "ffprobe"),
        retention_days=int(os.getenv("AGENT5_RETENTION_DAYS", "30")),
        test_mode=os.getenv("AGENT5_TEST_MODE", "0").lower() in {"1", "true", "yes"},
        anti_spoof_live_class=int(os.getenv("AGENT5_ANTI_SPOOF_LIVE_CLASS", "0")),
        no_face_confirm_seconds=float(os.getenv("AGENT5_NO_FACE_CONFIRM_SECONDS", "2.0")),
        no_face_confirm_count=int(os.getenv("AGENT5_NO_FACE_CONFIRM_COUNT", "3")),
        multiple_faces_confirm_seconds=float(os.getenv("AGENT5_MULTIPLE_FACES_CONFIRM_SECONDS", "1.2")),
        multiple_faces_confirm_count=int(os.getenv("AGENT5_MULTIPLE_FACES_CONFIRM_COUNT", "2")),
        face_mismatch_confirm_seconds=float(os.getenv("AGENT5_FACE_MISMATCH_CONFIRM_SECONDS", "2.0")),
        face_mismatch_confirm_count=int(os.getenv("AGENT5_FACE_MISMATCH_CONFIRM_COUNT", "3")),
        face_mismatch_min_confidence=float(os.getenv("AGENT5_FACE_MISMATCH_MIN_CONFIDENCE", "0.55")),
        gaze_confirm_seconds=float(os.getenv("AGENT5_GAZE_CONFIRM_SECONDS", "2.5")),
        gaze_confirm_count=int(os.getenv("AGENT5_GAZE_CONFIRM_COUNT", "3")),
        gaze_min_confidence=float(os.getenv("AGENT5_GAZE_MIN_CONFIDENCE", "0.28")),
        head_pose_min_confidence=float(os.getenv("AGENT5_HEAD_POSE_MIN_CONFIDENCE", "0.30")),
        attention_yaw_enter_degrees=float(os.getenv("AGENT5_ATTENTION_YAW_ENTER_DEGREES", "16.0")),
        attention_pitch_enter_degrees=float(os.getenv("AGENT5_ATTENTION_PITCH_ENTER_DEGREES", "13.0")),
        attention_roll_enter_degrees=float(os.getenv("AGENT5_ATTENTION_ROLL_ENTER_DEGREES", "16.0")),
        attention_gaze_horizontal_offset=float(os.getenv("AGENT5_ATTENTION_GAZE_HORIZONTAL_OFFSET", "0.075")),
        attention_gaze_vertical_offset=float(os.getenv("AGENT5_ATTENTION_GAZE_VERTICAL_OFFSET", "0.09")),
        attention_hysteresis_ratio=float(os.getenv("AGENT5_ATTENTION_HYSTERESIS_RATIO", "0.72")),
        attention_blink_ear_threshold=float(os.getenv("AGENT5_ATTENTION_BLINK_EAR_THRESHOLD", "0.115")),
        head_pose_confirm_seconds=float(os.getenv("AGENT5_HEAD_POSE_CONFIRM_SECONDS", "2.2")),
        head_pose_confirm_count=int(os.getenv("AGENT5_HEAD_POSE_CONFIRM_COUNT", "3")),
        attention_recovery_seconds=float(os.getenv("AGENT5_ATTENTION_RECOVERY_SECONDS", "1.2")),
        attention_frame_interval_ms=int(os.getenv("AGENT5_ATTENTION_FRAME_INTERVAL_MS", "750")),
        attention_baseline_min_samples=int(os.getenv("AGENT5_ATTENTION_BASELINE_MIN_SAMPLES", "10")),
        attention_baseline_window_samples=int(os.getenv("AGENT5_ATTENTION_BASELINE_WINDOW_SAMPLES", "18")),
        attention_baseline_min_span_seconds=float(os.getenv("AGENT5_ATTENTION_BASELINE_MIN_SPAN_SECONDS", "1.8")),
        attention_baseline_event_suppression_seconds=float(os.getenv("AGENT5_ATTENTION_BASELINE_EVENT_SUPPRESSION_SECONDS", "3.0")),
        attention_baseline_fallback_seconds=float(os.getenv("AGENT5_ATTENTION_BASELINE_FALLBACK_SECONDS", "8.0")),
        attention_baseline_min_confidence=float(os.getenv("AGENT5_ATTENTION_BASELINE_MIN_CONFIDENCE", "0.50")),
        attention_baseline_max_abs_yaw_degrees=float(os.getenv("AGENT5_ATTENTION_BASELINE_MAX_ABS_YAW_DEGREES", "16.0")),
        attention_baseline_max_abs_pitch_degrees=float(os.getenv("AGENT5_ATTENTION_BASELINE_MAX_ABS_PITCH_DEGREES", "14.0")),
        attention_baseline_max_abs_roll_degrees=float(os.getenv("AGENT5_ATTENTION_BASELINE_MAX_ABS_ROLL_DEGREES", "12.0")),
        attention_baseline_max_mad_yaw_degrees=float(os.getenv("AGENT5_ATTENTION_BASELINE_MAX_MAD_YAW_DEGREES", "3.5")),
        attention_baseline_max_mad_pitch_degrees=float(os.getenv("AGENT5_ATTENTION_BASELINE_MAX_MAD_PITCH_DEGREES", "3.5")),
        attention_baseline_max_mad_roll_degrees=float(os.getenv("AGENT5_ATTENTION_BASELINE_MAX_MAD_ROLL_DEGREES", "3.0")),
        attention_baseline_fallback_threshold_multiplier=float(os.getenv("AGENT5_ATTENTION_BASELINE_FALLBACK_THRESHOLD_MULTIPLIER", "1.35")),
        attention_baseline_fallback_confirmation_multiplier=float(os.getenv("AGENT5_ATTENTION_BASELINE_FALLBACK_CONFIRMATION_MULTIPLIER", "1.35")),
        attention_baseline_fallback_risk_scale=float(os.getenv("AGENT5_ATTENTION_BASELINE_FALLBACK_RISK_SCALE", "0.50")),
        voice_mismatch_confirm_seconds=float(os.getenv("AGENT5_VOICE_MISMATCH_CONFIRM_SECONDS", "3.0")),
        voice_mismatch_confirm_count=int(os.getenv("AGENT5_VOICE_MISMATCH_CONFIRM_COUNT", "2")),
        voice_mismatch_min_confidence=float(os.getenv("AGENT5_VOICE_MISMATCH_MIN_CONFIDENCE", "0.55")),
        additional_speaker_confirm_seconds=float(os.getenv("AGENT5_ADDITIONAL_SPEAKER_CONFIRM_SECONDS", "4.0")),
        additional_speaker_confirm_count=int(os.getenv("AGENT5_ADDITIONAL_SPEAKER_CONFIRM_COUNT", "2")),
        overlap_confirm_seconds=float(os.getenv("AGENT5_OVERLAP_CONFIRM_SECONDS", "4.0")),
        overlap_confirm_count=int(os.getenv("AGENT5_OVERLAP_CONFIRM_COUNT", "2")),
        sentence_min_completion=float(os.getenv("AGENT5_SENTENCE_MIN_COMPLETION", "1.0")),
        sentence_max_skipped=int(os.getenv("AGENT5_SENTENCE_MAX_SKIPPED", "1")),
        sentence_max_incorrect=int(os.getenv("AGENT5_SENTENCE_MAX_INCORRECT", "1")),
        frame_request_timeout_seconds=float(os.getenv("AGENT5_FRAME_REQUEST_TIMEOUT_SECONDS", "8.0")),
        audio_request_timeout_seconds=float(os.getenv("AGENT5_AUDIO_REQUEST_TIMEOUT_SECONDS", "25.0")),
        candidate_debug_payloads=os.getenv("AGENT5_CANDIDATE_DEBUG_PAYLOADS", "0").lower() in {"1", "true", "yes"},
    )
    settings.ensure_directories()
    return settings
