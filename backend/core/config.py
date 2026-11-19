"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "Agentic HR Recruitment System"
    debug: bool = False
    frontend_url: str = "http://localhost:5173"  # Public app URL used in candidate emails (schedule + join)
    api_prefix: str = "/api"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/interview_scheduler"
    # SQLAlchemy async pool (per Uvicorn process). Keep modest with --workers 1.
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout_seconds: int = 30

    # SMTP Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "hr@company.com"
    smtp_from_name: str = "RR Parkon HR Team"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: int = 30

    # Agent 5 — public URL for the in-app interview / proctoring room
    agent5_public_url: str = "http://127.0.0.1:8030"
    # When false, this process still bootstraps Agent 5 DB/tokens but does not
    # serve camera/WebSocket routes (use the standalone proctoring app on VM 2).
    agent5_embedded: bool = True

    # Scheduling (fallback only — job title comes from Agent 1 JD parsing)
    token_expiry_hours: int = 48
    interview_duration_minutes: int = 30

    # Agent 3 — Interview Blueprint
    blueprint_max_jd_text_chars: int = 100_000
    # blueprint_auto_generate_on_shortlist lives in SuperAdmin → Agent Control (DB).

    # LangGraph checkpoint (enterprise durable state for Agents 2/4/1)
    checkpoint_db_url: str = "postgresql://postgres:postgres@localhost:5432/interview_scheduler"
    langgraph_checkpoint_backend: str = "postgres"  # postgres | memory

    # ChromaDB — vector memory for Agents 1/4/6/7 (Postgres remains system of record)
    chroma_enabled: bool = True
    chroma_persist_dir: str = "storage/chroma"
    chroma_seed_on_startup: bool = True

    # Redis — interview speed cache (questions, TTS, eval queue). Empty = in-memory fallback.
    redis_url: str = ""
    redis_max_connections: int = 32
    # When true, live turns advance without waiting for Agent 6; eval runs in background.
    interview_async_eval: bool = True
    # Embedded Redis eval consumer inside FastAPI lifespan (one per process).
    interview_eval_worker_enabled: bool = True
    # Parallel Agent 6 jobs inside the single consumer loop (not extra consumers).
    interview_eval_concurrency: int = 2
    interview_eval_max_job_retries: int = 2

    # Azure capacity gates (per process). Tune to deployment TPM/RPM; do not raise blindly.
    azure_llm_max_concurrent: int = 8
    azure_stt_max_concurrent: int = 6
    azure_tts_max_concurrent: int = 6
    azure_llm_acquire_timeout_seconds: float = 45.0
    azure_stt_acquire_timeout_seconds: float = 60.0
    azure_tts_acquire_timeout_seconds: float = 45.0
    # Extra attempts after the first failure (2 → 3 total). Hard-capped in azure_retry.
    azure_retry_max_attempts: int = 2
    azure_http_max_connections: int = 32

    # STT: bounded worker pool (Azure Speech REST is blocking).
    stt_worker_threads: int = 4
    stt_timeout_seconds: float = 90.0
    # LLM resume correction: deferred (off hot path, before Agent 6) | inline | off
    # STT_RESUME_CORRECTION remains the master enable switch (env).
    stt_llm_correction_mode: str = "deferred"
    # Save answers during live interview; run Agent 6 scoring after COMPLETED.
    # Env: INTERVIEW_DEFER_EVAL_UNTIL_END
    interview_defer_eval_until_end: bool = True
    # Mid-interview adaptive LLM follow-ups (off = use prep-time planned follow-ups only).
    # Env: INTERVIEW_LIVE_ADAPTIVE_FOLLOWUPS
    interview_live_adaptive_followups: bool = False
    # batch = existing Azure REST multipart; streaming = WebSocket + Speech SDK continuous.
    # Env alias: INTERVIEW_STT_MODE
    interview_stt_mode: str = "batch"
    # Azure continuous recognition segmentation silence (100–5000 ms).
    stt_stream_segmentation_silence_ms: int = 800
    stt_stream_initial_silence_ms: int = 10000
    # Browser end-of-answer silence before stop (env: INTERVIEW_STT_END_SILENCE_MS).
    interview_stt_end_silence_ms: int = 2000
    # Wait for Azure final events after push-stream close (env: INTERVIEW_STT_FINALIZATION_TIMEOUT_MS).
    interview_stt_finalization_timeout_ms: int = 5000

    # TTS Phase 3: combine turn ack + next question into one utterance (default on).
    interview_tts_combine_ack: bool = True
    # Stream Azure TTS MP3 chunks (SDK AudioDataStream); fall back to /ai/speak blob.
    interview_tts_stream: bool = True

    # JWT authentication
    jwt_secret_key: str = "change-me-in-production-use-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()


def public_frontend_url() -> str:
    """Candidate-facing origin for scheduling and join links in emails."""
    return get_settings().frontend_url.rstrip("/")
