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
    blueprint_auto_generate_on_shortlist: bool = True

    # LangGraph checkpoint (enterprise durable state for Agents 2/4/1)
    checkpoint_db_url: str = "postgresql://postgres:postgres@localhost:5432/interview_scheduler"
    langgraph_checkpoint_backend: str = "postgres"  # postgres | memory

    # ChromaDB — vector memory for Agents 1/4/6/7 (Postgres remains system of record)
    chroma_enabled: bool = True
    chroma_persist_dir: str = "storage/chroma"
    chroma_seed_on_startup: bool = True

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
