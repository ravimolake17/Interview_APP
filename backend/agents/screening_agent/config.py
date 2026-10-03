from __future__ import annotations

import logging
from functools import cached_property

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application and ATS configuration loaded from environment variables."""

    APP_NAME: str = "Resume Screening ATS API"
    APP_VERSION: str = "2.1.0"
    LOG_LEVEL: str = "INFO"

    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_TEMPERATURE: float = Field(default=0.0, ge=0, le=1)
    GROQ_MAX_TOKENS: int = Field(default=8192, ge=256, le=8192)
    SCREENING_PROMPT_STYLE: str = "detailed_analysis"
    GROQ_TIMEOUT_SECONDS: float = Field(default=45.0, ge=1, le=300)
    GROQ_MAX_RETRIES: int = Field(default=1, ge=0, le=5)
    USE_LLM_FOR_JD_PARSING: bool = True
    USE_LLM_FOR_RESUME_PARSING: bool = True

    LLM_PROVIDER: str = "groq"
    AZURE_OPENAI_API_KEY: str | None = None
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_DEPLOYMENT: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-10-21"
    STT_PROVIDER: str = "groq"
    TTS_PROVIDER: str = "edge"
    AZURE_SPEECH_KEY: str | None = None
    AZURE_SPEECH_REGION: str = "eastus2"
    AZURE_SPEECH_STT_ENDPOINT: str = ""
    AZURE_SPEECH_TTS_ENDPOINT: str = ""

    MAX_UPLOAD_SIZE_MB: int = Field(default=15, ge=1, le=100)
    MAX_DOCX_UNCOMPRESSED_MB: int = Field(default=150, ge=10, le=1000)
    MAX_JD_TEXT_CHARS: int = Field(default=100_000, ge=1_000, le=1_000_000)

    # auto: Use embedded PDF text first, then OCR only when necessary.
    # always: Always use OCR.
    # never: Never use OCR.
    PDF_OCR_MODE: str = "auto"
    OCR_DOWNLOAD_ENABLED: bool = True

    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"

    # Allows frontend development servers on any localhost port.
    CORS_ORIGIN_REGEX: str | None = (
        r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
        r"|^https://[a-z0-9-]+\.(trycloudflare\.com|loca\.lt|ngrok-free\.app|ngrok\.io)$"
    )

    ATS_REQUIRED_SKILLS_WEIGHT: float = Field(default=45.0, ge=0)
    ATS_PREFERRED_SKILLS_WEIGHT: float = Field(default=15.0, ge=0)
    ATS_EXPERIENCE_WEIGHT: float = Field(default=20.0, ge=0)
    ATS_EDUCATION_CERTIFICATION_WEIGHT: float = Field(default=10.0, ge=0)
    ATS_KEYWORD_WEIGHT: float = Field(default=10.0, ge=0)

    ATS_SHORTLIST_THRESHOLD: float = Field(default=75.0, ge=0, le=100)
    ATS_REVIEW_THRESHOLD: float = Field(default=55.0, ge=0, le=100)

    ATS_MIN_REQUIRED_RATIO_FOR_SHORTLIST: float = Field(
        default=0.60,
        ge=0,
        le=1,
    )

    # Hybrid semantic skill matching (BGE-M3) — complements rule-based ATS
    ATS_SEMANTIC_MATCHING_ENABLED: bool = True
    ATS_SEMANTIC_MODEL: str = "BAAI/bge-m3"
    # Keep list-inclusion strict: raw BGE-M3 often ranks distractors above paraphrases.
    ATS_SEMANTIC_MIN_MATCH_THRESHOLD: float = Field(default=0.85, ge=0, le=1)
    ATS_SEMANTIC_PERFECT_THRESHOLD: float = Field(default=0.90, ge=0, le=1)
    ATS_SEMANTIC_STRONG_THRESHOLD: float = Field(default=0.85, ge=0, le=1)
    ATS_SEMANTIC_GOOD_THRESHOLD: float = Field(default=0.80, ge=0, le=1)
    ATS_SEMANTIC_PARTIAL_THRESHOLD: float = Field(default=0.75, ge=0, le=1)
    ATS_SEMANTIC_USE_FP16: bool = False
    ATS_SEMANTIC_EMBED_BATCH_SIZE: int = Field(default=32, ge=1, le=256)

    # Async screening queue (Agent 1 enterprise throughput)
    SCREENING_QUEUE_ENABLED: bool = True
    SCREENING_EMBED_WORKERS: bool = True
    MAX_CONCURRENT_SCREENING_JOBS: int = Field(default=20, ge=1, le=100)
    MAX_CONCURRENT_EXTRACT_JOBS: int = Field(default=1, ge=1, le=20)
    GROQ_RATE_LIMIT_WAIT_SECONDS: float = Field(default=480.0, ge=10, le=1800)
    SCREENING_WORKER_POLL_SECONDS: float = Field(default=1.0, ge=0.2, le=30.0)
    SCREENING_BATCH_MAX_SIZE: int = Field(default=100, ge=1, le=500)
    SCREENING_JOB_POLL_INTERVAL_MS: int = Field(default=2000, ge=500, le=30000)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator(
        "GROQ_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "AZURE_SPEECH_KEY",
        mode="before",
    )
    @classmethod
    def empty_api_key_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in logging.getLevelNamesMapping():
            raise ValueError(
                "LOG_LEVEL must be a standard Python logging level "
                "such as DEBUG, INFO, WARNING, ERROR, or CRITICAL."
            )
        return normalized

    @model_validator(mode="after")
    def validate_scoring_configuration(self) -> "Settings":
        total = (
            self.ATS_REQUIRED_SKILLS_WEIGHT
            + self.ATS_PREFERRED_SKILLS_WEIGHT
            + self.ATS_EXPERIENCE_WEIGHT
            + self.ATS_EDUCATION_CERTIFICATION_WEIGHT
            + self.ATS_KEYWORD_WEIGHT
        )

        if abs(total - 100.0) > 0.001:
            raise ValueError(f"ATS scoring weights must total 100; received {total}.")

        ocr_mode = self.PDF_OCR_MODE.strip().lower()

        if ocr_mode not in {"auto", "always", "never"}:
            raise ValueError("PDF_OCR_MODE must be one of: auto, always, never.")

        self.PDF_OCR_MODE = ocr_mode

        if self.ATS_SHORTLIST_THRESHOLD <= self.ATS_REVIEW_THRESHOLD:
            raise ValueError(
                "ATS_SHORTLIST_THRESHOLD must be greater than ATS_REVIEW_THRESHOLD."
            )

        return self

    @cached_property
    def cors_origin_list(self) -> list[str]:
        return [
            origin
            for origin in (value.strip() for value in self.CORS_ORIGINS.split(","))
            if origin
        ]


settings = Settings()
