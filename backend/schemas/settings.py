"""Validated contracts for account and application settings."""

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from schemas.auth import UserResponse


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    job_title: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=32)


class CompanySettings(BaseModel):
    company_name: str = Field(default="RR Global Pvt Ltd", min_length=1, max_length=255)
    website: str = Field(default="https://rrglobal.in", max_length=512)
    industry: str = Field(default="Technology", max_length=120)
    company_size: str = Field(default="201-1000", max_length=64)
    headquarters: str = Field(default="Mumbai, India", max_length=255)
    timezone: Literal["Asia/Kolkata", "Asia/Dubai", "Europe/London"] = "Asia/Kolkata"


class AppearanceSettings(BaseModel):
    theme: Literal["light", "dark"] = "light"
    primary_color_id: Literal["orange", "blue", "purple", "green", "red"] = "orange"


class NotificationSettings(BaseModel):
    new_candidate_uploaded: bool = True
    ai_screening_complete: bool = True
    candidate_shortlisted: bool = True
    job_application_received: bool = True
    weekly_report: bool = True


class PreferenceSettings(BaseModel):
    appearance: AppearanceSettings = Field(default_factory=AppearanceSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)


class AIModelSettings(BaseModel):
    provider: Literal["groq", "azure"] = "groq"
    model_id: str = Field(default="openai/gpt-oss-120b", min_length=1, max_length=120)
    temperature: float = Field(default=0.0, ge=0, le=1)
    max_tokens: int = Field(default=8192, ge=256, le=32768)
    prompt_style: Literal[
        "detailed_analysis",
        "quick_summary",
        "technical_focus",
        "cultural_fit_focus",
    ] = "detailed_analysis"
    azure_openai_endpoint: str = Field(default="", max_length=512)
    azure_openai_deployment: str = Field(default="", max_length=120)
    azure_openai_api_version: str = Field(default="2024-10-21", max_length=32)
    stt_provider: Literal["groq", "azure"] = "groq"
    tts_provider: Literal["edge", "azure"] = "edge"
    azure_speech_region: str = Field(default="eastus2", max_length=64)
    azure_speech_stt_endpoint: str = Field(default="", max_length=512)
    azure_speech_tts_endpoint: str = Field(default="", max_length=512)

    @field_validator(
        "azure_openai_endpoint",
        "azure_openai_deployment",
        "azure_openai_api_version",
        "azure_speech_region",
        "azure_speech_stt_endpoint",
        "azure_speech_tts_endpoint",
    )
    @classmethod
    def strip_optional_text(cls, value: str) -> str:
        return str(value or "").strip()


class CalendarHoliday(BaseModel):
    date: date
    name: str = Field(default="Holiday", min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip() or "Holiday"
        return cleaned[:120]


class InterviewAvailabilitySettings(BaseModel):
    """Working days and hours used to generate candidate booking slots."""

    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5])
    start_time: time = time(9, 0)
    end_time: time = time(19, 0)
    slot_minutes: int = Field(default=30, ge=15, le=120)
    weeks_ahead: int = Field(default=4, ge=1, le=8)
    holidays: list[CalendarHoliday] = Field(default_factory=list)

    @field_validator("weekdays")
    @classmethod
    def valid_weekdays(cls, value: list[int]) -> list[int]:
        unique = sorted({int(day) for day in value})
        if not unique:
            raise ValueError("Select at least one working day.")
        if any(day < 0 or day > 6 for day in unique):
            raise ValueError("Weekdays must be between Monday (0) and Sunday (6).")
        return unique

    @field_validator("holidays")
    @classmethod
    def unique_holidays(cls, value: list[CalendarHoliday]) -> list[CalendarHoliday]:
        by_date: dict[date, CalendarHoliday] = {}
        for item in value:
            by_date[item.date] = item
        return sorted(by_date.values(), key=lambda item: item.date)

    @model_validator(mode="after")
    def end_after_start(self) -> "InterviewAvailabilitySettings":
        start_minutes = self.start_time.hour * 60 + self.start_time.minute
        end_minutes = self.end_time.hour * 60 + self.end_time.minute
        if end_minutes <= start_minutes:
            raise ValueError("End time must be after start time.")
        if end_minutes - start_minutes < self.slot_minutes:
            raise ValueError("The working window must fit at least one interview slot.")
        return self

    def holiday_dates(self) -> set[date]:
        return {item.date for item in self.holidays}


class ScreeningPolicySettings(BaseModel):
    shortlist_threshold: float = Field(default=75.0, ge=0, le=100)
    review_threshold: float = Field(default=55.0, ge=0, le=100)
    use_llm_for_jd_parsing: bool = True
    use_llm_for_resume_parsing: bool = True

    @model_validator(mode="after")
    def shortlist_above_review(self) -> "ScreeningPolicySettings":
        if self.shortlist_threshold <= self.review_threshold:
            raise ValueError("Shortlist threshold must be greater than review threshold.")
        return self


class IntegrationStatus(BaseModel):
    backend_endpoint: str = "/api"
    backend_connected: bool = True
    provider: str = "groq"
    api_key_configured: bool = False
    api_key_masked: str = "Not configured"
    groq_api_key_configured: bool = False
    groq_api_key_masked: str = "Not configured"
    azure_openai_api_key_configured: bool = False
    azure_openai_api_key_masked: str = "Not configured"
    azure_speech_key_configured: bool = False
    azure_speech_key_masked: str = "Not configured"
    frontend_url: str = ""
    agent5_public_url: str = ""
    stt_provider: str = "groq"
    tts_provider: str = "edge"
    message: str = "Backend connection is healthy."


class IntegrationUpdate(BaseModel):
    groq_api_key: str | None = Field(default=None, max_length=512)
    azure_openai_api_key: str | None = Field(default=None, max_length=512)
    azure_speech_key: str | None = Field(default=None, max_length=512)
    frontend_url: str | None = Field(default=None, max_length=512)
    agent5_public_url: str | None = Field(default=None, max_length=512)


class SmtpAccountSettings(BaseModel):
    company_id: int
    company_name: str = ""
    company_code: str = ""
    host: str = Field(default="", max_length=255)
    port: int = Field(default=587, ge=1, le=65535)
    username: str = Field(default="", max_length=255)
    from_email: str = Field(default="", max_length=255)
    from_name: str = Field(default="", max_length=255)
    use_tls: bool = True
    use_ssl: bool = False
    timeout_seconds: int = Field(default=30, ge=5, le=120)
    password_configured: bool = False
    password_masked: str = "Not configured"
    using_env_fallback: bool = False


class SmtpAccountUpdate(BaseModel):
    host: str = Field(default="", max_length=255)
    port: int = Field(default=587, ge=1, le=65535)
    username: str = Field(default="", max_length=255)
    password: str | None = Field(default=None, max_length=512)
    from_email: str = Field(default="", max_length=255)
    from_name: str = Field(default="", max_length=255)
    use_tls: bool = True
    use_ssl: bool = False
    timeout_seconds: int = Field(default=30, ge=5, le=120)

    @field_validator("host", "username", "from_email", "from_name")
    @classmethod
    def strip_smtp_text(cls, value: str) -> str:
        return str(value or "").strip()


class ConnectionTestResponse(BaseModel):
    ok: bool
    status: str
    version: str
    provider_configured: bool
    message: str


class SettingsBundle(BaseModel):
    profile: UserResponse
    company: CompanySettings
    preferences: PreferenceSettings
    integration: IntegrationStatus
    ai_model: AIModelSettings
    interview_availability: InterviewAvailabilitySettings = Field(
        default_factory=InterviewAvailabilitySettings
    )
    smtp_accounts: list[SmtpAccountSettings] = Field(default_factory=list)
