"""Business logic for persistent UI settings and runtime AI configuration."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from agents.screening_agent.config import settings as screening_settings
from core.config import get_settings
from repositories.application_setting_repository import ApplicationSettingRepository
from repositories.company_repository import CompanyRepository
from schemas.settings import (
    AIModelSettings,
    AppearanceSettings,
    CompanySettings,
    IntegrationStatus,
    IntegrationUpdate,
    InterviewAvailabilitySettings,
    NotificationSettings,
    PreferenceSettings,
    ScreeningPolicySettings,
    SmtpAccountSettings,
    SmtpAccountUpdate,
)
from services.email_service import SmtpRuntime


def _masked_key(value: str | None) -> str:
    if not value:
        return "Not configured"
    suffix = value[-4:] if len(value) >= 4 else "••••"
    return f"••••••••{suffix}"


def is_secret_unchanged(value: str | None) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    lowered = text.casefold()
    if lowered in {"not configured", "unchanged"}:
        return True
    return text.startswith("••••")


class ApplicationSettingsService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = ApplicationSettingRepository(db)

    async def _company_row(self, namespace: str, company_id: int | None):
        if company_id is not None:
            row = await self.repo.get(f"company:{company_id}", namespace)
            if row:
                return row
        return await self.repo.get("global", namespace)

    async def get_company(self, company_id: int | None = None) -> CompanySettings:
        extras = {}
        row = await self._company_row("company", company_id)
        if row:
            extras = dict(row.data or {})
        if company_id is not None:
            company = await CompanyRepository(self.repo.db).get_by_id(company_id)
            if company:
                extras["company_name"] = company.name
        return CompanySettings.model_validate(extras)

    async def save_company(
        self,
        payload: CompanySettings,
        actor_id: int,
        *,
        company_id: int | None = None,
    ) -> CompanySettings:
        scope = f"company:{company_id}" if company_id is not None else "global"
        await self.repo.upsert(scope, "company", payload.model_dump(mode="json"), actor_id)
        if company_id is not None:
            company = await CompanyRepository(self.repo.db).get_by_id(company_id)
            if company:
                company.name = payload.company_name
                await self.repo.db.flush()
        return payload

    async def get_preferences(self, user_id: int) -> PreferenceSettings:
        row = await self.repo.get(f"user:{user_id}", "preferences")
        return PreferenceSettings.model_validate(row.data if row else {})

    async def save_preferences(
        self, user_id: int, payload: PreferenceSettings
    ) -> PreferenceSettings:
        await self.repo.upsert(
            f"user:{user_id}",
            "preferences",
            payload.model_dump(mode="json"),
            user_id,
        )
        return payload

    async def _secrets(self) -> dict:
        row = await self.repo.get("global", "ai_secrets")
        return dict(row.data or {}) if row else {}

    async def get_ai_model(self) -> AIModelSettings:
        row = await self.repo.get("global", "ai_model")
        fallback = {
            "provider": getattr(screening_settings, "LLM_PROVIDER", "groq") or "groq",
            "model_id": screening_settings.GROQ_MODEL,
            "temperature": screening_settings.GROQ_TEMPERATURE,
            "max_tokens": screening_settings.GROQ_MAX_TOKENS,
            "prompt_style": screening_settings.SCREENING_PROMPT_STYLE,
            "azure_openai_endpoint": getattr(screening_settings, "AZURE_OPENAI_ENDPOINT", "") or "",
            "azure_openai_deployment": getattr(screening_settings, "AZURE_OPENAI_DEPLOYMENT", "") or "",
            "azure_openai_api_version": getattr(
                screening_settings, "AZURE_OPENAI_API_VERSION", "2024-10-21"
            )
            or "2024-10-21",
            "stt_provider": getattr(screening_settings, "STT_PROVIDER", "groq") or "groq",
            "tts_provider": getattr(screening_settings, "TTS_PROVIDER", "edge") or "edge",
            "azure_speech_region": getattr(screening_settings, "AZURE_SPEECH_REGION", "eastus2")
            or "eastus2",
            "azure_speech_stt_endpoint": getattr(
                screening_settings, "AZURE_SPEECH_STT_ENDPOINT", ""
            )
            or "",
            "azure_speech_tts_endpoint": getattr(
                screening_settings, "AZURE_SPEECH_TTS_ENDPOINT", ""
            )
            or "",
        }
        data = dict(fallback)
        if row and row.data:
            data.update(row.data)
        return AIModelSettings.model_validate(data)

    async def save_ai_model(
        self, payload: AIModelSettings, actor_id: int
    ) -> AIModelSettings:
        current = (await self.get_ai_model()).model_dump()
        current.update(payload.model_dump(exclude_unset=True))
        saved = AIModelSettings.model_validate(current)
        await self.repo.upsert(
            "global",
            "ai_model",
            saved.model_dump(mode="json"),
            actor_id,
        )
        secrets = await self._secrets()
        self.apply_ai_runtime(saved, secrets)
        return saved

    @staticmethod
    def apply_ai_runtime(
        payload: AIModelSettings,
        secrets: dict | None = None,
    ) -> None:
        from agents.shared.llama_client import resolve_groq_model

        screening_settings.LLM_PROVIDER = payload.provider
        screening_settings.GROQ_MODEL = (
            resolve_groq_model(payload.model_id)
            if payload.provider == "groq"
            else payload.model_id
        )
        screening_settings.GROQ_TEMPERATURE = payload.temperature
        screening_settings.GROQ_MAX_TOKENS = payload.max_tokens
        screening_settings.SCREENING_PROMPT_STYLE = payload.prompt_style
        screening_settings.AZURE_OPENAI_ENDPOINT = payload.azure_openai_endpoint
        screening_settings.AZURE_OPENAI_DEPLOYMENT = (
            payload.azure_openai_deployment or payload.model_id
        )
        screening_settings.AZURE_OPENAI_API_VERSION = (
            payload.azure_openai_api_version or "2024-10-21"
        )
        screening_settings.STT_PROVIDER = payload.stt_provider
        screening_settings.TTS_PROVIDER = payload.tts_provider
        screening_settings.AZURE_SPEECH_REGION = payload.azure_speech_region or "eastus2"
        screening_settings.AZURE_SPEECH_STT_ENDPOINT = payload.azure_speech_stt_endpoint
        screening_settings.AZURE_SPEECH_TTS_ENDPOINT = payload.azure_speech_tts_endpoint
        ApplicationSettingsService._apply_secrets(secrets or {})

    @staticmethod
    def _apply_secrets(secrets: dict) -> None:
        groq_key = secrets.get("groq_api_key")
        if groq_key:
            screening_settings.GROQ_API_KEY = groq_key
        azure_key = secrets.get("azure_openai_api_key")
        if azure_key:
            screening_settings.AZURE_OPENAI_API_KEY = azure_key
        speech_key = secrets.get("azure_speech_key")
        if speech_key:
            screening_settings.AZURE_SPEECH_KEY = speech_key
        app = get_settings()
        frontend_url = str(secrets.get("frontend_url") or "").strip()
        if frontend_url:
            app.frontend_url = frontend_url
        agent5_url = str(secrets.get("agent5_public_url") or "").strip()
        if agent5_url:
            app.agent5_public_url = agent5_url

    async def get_integration_status(self) -> IntegrationStatus:
        secrets = await self._secrets()
        ai = await self.get_ai_model()
        groq_key = secrets.get("groq_api_key") or screening_settings.GROQ_API_KEY
        azure_key = secrets.get("azure_openai_api_key") or getattr(
            screening_settings, "AZURE_OPENAI_API_KEY", None
        )
        speech_key = secrets.get("azure_speech_key") or getattr(
            screening_settings, "AZURE_SPEECH_KEY", None
        )
        app = get_settings()
        groq_ok = bool(groq_key)
        azure_ok = bool(azure_key)
        provider = ai.provider
        if provider == "azure":
            ready = bool(
                azure_ok and ai.azure_openai_endpoint and (ai.azure_openai_deployment or ai.model_id)
            )
            message = (
                "Azure OpenAI chat is configured."
                if ready
                else "Set Azure OpenAI key, endpoint, and deployment name."
            )
        else:
            ready = groq_ok
            message = (
                "Backend and Groq are configured."
                if ready
                else "Backend is connected; configure the Groq API key."
            )
        groq_masked = _masked_key(groq_key)
        return IntegrationStatus(
            api_key_configured=ready,
            api_key_masked=groq_masked if provider == "groq" else _masked_key(azure_key),
            provider=provider,
            groq_api_key_configured=groq_ok,
            groq_api_key_masked=groq_masked,
            azure_openai_api_key_configured=azure_ok,
            azure_openai_api_key_masked=_masked_key(azure_key),
            azure_speech_key_configured=bool(speech_key),
            azure_speech_key_masked=_masked_key(speech_key),
            frontend_url=str(secrets.get("frontend_url") or app.frontend_url or ""),
            agent5_public_url=str(
                secrets.get("agent5_public_url") or app.agent5_public_url or ""
            ),
            stt_provider=ai.stt_provider,
            tts_provider=ai.tts_provider,
            message=message,
        )

    async def save_integration(
        self, payload: IntegrationUpdate, actor_id: int
    ) -> IntegrationStatus:
        patch: dict = {}
        if not is_secret_unchanged(payload.groq_api_key):
            patch["groq_api_key"] = str(payload.groq_api_key).strip()
        if not is_secret_unchanged(payload.azure_openai_api_key):
            patch["azure_openai_api_key"] = str(payload.azure_openai_api_key).strip()
        if not is_secret_unchanged(payload.azure_speech_key):
            patch["azure_speech_key"] = str(payload.azure_speech_key).strip()
        if payload.frontend_url is not None and payload.frontend_url.strip():
            patch["frontend_url"] = payload.frontend_url.strip().rstrip("/")
        if payload.agent5_public_url is not None and payload.agent5_public_url.strip():
            patch["agent5_public_url"] = payload.agent5_public_url.strip().rstrip("/")
        if patch:
            await self.repo.merge("global", "ai_secrets", patch, actor_id)
        secrets = await self._secrets()
        self._apply_secrets(secrets)
        return await self.get_integration_status()

    def _env_smtp_fallback(self) -> dict:
        app = get_settings()
        return {
            "host": app.smtp_host or "",
            "port": app.smtp_port,
            "username": app.smtp_user or "",
            "password": app.smtp_password or "",
            "from_email": app.smtp_from_email or "",
            "from_name": app.smtp_from_name or "",
            "use_tls": app.smtp_use_tls,
            "use_ssl": app.smtp_use_ssl,
            "timeout_seconds": app.smtp_timeout_seconds,
        }

    async def get_smtp_account(self, company_id: int) -> SmtpAccountSettings:
        company = await CompanyRepository(self.repo.db).get_by_id(company_id)
        row = await self.repo.get(f"company:{company_id}", "smtp")
        stored = dict(row.data or {}) if row else {}
        fallback = self._env_smtp_fallback()
        using_fallback = not bool(stored.get("host") and stored.get("username"))
        source = stored if not using_fallback else fallback
        password = stored.get("password") or (
            fallback.get("password") if using_fallback else ""
        )
        return SmtpAccountSettings(
            company_id=company_id,
            company_name=company.name if company else "",
            company_code=company.code if company else "",
            host=str(source.get("host") or ""),
            port=int(source.get("port") or 587),
            username=str(source.get("username") or ""),
            from_email=str(source.get("from_email") or ""),
            from_name=str(source.get("from_name") or ""),
            use_tls=bool(source.get("use_tls", True)),
            use_ssl=bool(source.get("use_ssl", False)),
            timeout_seconds=int(source.get("timeout_seconds") or 30),
            password_configured=bool(password),
            password_masked=_masked_key(password if password else None),
            using_env_fallback=using_fallback,
        )

    async def list_smtp_accounts(self) -> list[SmtpAccountSettings]:
        companies = await CompanyRepository(self.repo.db).list_all()
        return [await self.get_smtp_account(company.id) for company in companies]

    async def save_smtp_account(
        self,
        company_id: int,
        payload: SmtpAccountUpdate,
        actor_id: int,
    ) -> SmtpAccountSettings:
        row = await self.repo.get(f"company:{company_id}", "smtp")
        stored = dict(row.data or {}) if row else {}
        stored["host"] = payload.host
        stored["port"] = payload.port
        stored["username"] = payload.username
        stored["from_email"] = payload.from_email
        stored["from_name"] = payload.from_name
        stored["use_tls"] = payload.use_tls
        stored["use_ssl"] = payload.use_ssl
        stored["timeout_seconds"] = payload.timeout_seconds
        if not is_secret_unchanged(payload.password):
            stored["password"] = str(payload.password).strip()
        await self.repo.upsert(f"company:{company_id}", "smtp", stored, actor_id)
        return await self.get_smtp_account(company_id)

    async def resolve_smtp(self, company_id: int | None) -> SmtpRuntime | None:
        fallback = self._env_smtp_fallback()
        stored: dict = {}
        if company_id is not None:
            row = await self.repo.get(f"company:{company_id}", "smtp")
            stored = dict(row.data or {}) if row else {}
        host = stored.get("host") or fallback.get("host")
        username = stored.get("username") or fallback.get("username")
        password = stored.get("password") or fallback.get("password")
        from_email = stored.get("from_email") or fallback.get("from_email")
        if not (host and username and password and from_email):
            return None
        return SmtpRuntime(
            host=str(host),
            port=int(stored.get("port") or fallback.get("port") or 587),
            username=str(username),
            password=str(password),
            from_email=str(from_email),
            from_name=str(stored.get("from_name") or fallback.get("from_name") or ""),
            use_tls=bool(stored.get("use_tls", fallback.get("use_tls", True))),
            use_ssl=bool(stored.get("use_ssl", fallback.get("use_ssl", False))),
            timeout_seconds=int(
                stored.get("timeout_seconds") or fallback.get("timeout_seconds") or 30
            ),
        )

    async def get_screening_policy(self, company_id: int | None = None) -> ScreeningPolicySettings:
        row = await self._company_row("screening_policy", company_id)
        fallback = {
            "shortlist_threshold": screening_settings.ATS_SHORTLIST_THRESHOLD,
            "review_threshold": screening_settings.ATS_REVIEW_THRESHOLD,
            "use_llm_for_jd_parsing": screening_settings.USE_LLM_FOR_JD_PARSING,
            "use_llm_for_resume_parsing": screening_settings.USE_LLM_FOR_RESUME_PARSING,
        }
        return ScreeningPolicySettings.model_validate(row.data if row else fallback)

    async def save_screening_policy(
        self, payload: ScreeningPolicySettings, actor_id: int, *, company_id: int | None = None
    ) -> ScreeningPolicySettings:
        scope = f"company:{company_id}" if company_id is not None else "global"
        await self.repo.upsert(
            scope, "screening_policy", payload.model_dump(mode="json"), actor_id
        )
        self.apply_screening_runtime(payload)
        return payload

    @staticmethod
    def apply_screening_runtime(payload: ScreeningPolicySettings) -> None:
        screening_settings.ATS_SHORTLIST_THRESHOLD = payload.shortlist_threshold
        screening_settings.ATS_REVIEW_THRESHOLD = payload.review_threshold
        screening_settings.USE_LLM_FOR_JD_PARSING = payload.use_llm_for_jd_parsing
        screening_settings.USE_LLM_FOR_RESUME_PARSING = payload.use_llm_for_resume_parsing

    async def get_default_interview_minutes(self, company_id: int | None = None) -> int:
        """Canonical default interview/slot length from Interview hours settings."""
        return int((await self.get_interview_availability(company_id)).slot_minutes)

    async def get_interview_availability(
        self, company_id: int | None = None
    ) -> InterviewAvailabilitySettings:
        row = await self._company_row("interview_availability", company_id)
        return InterviewAvailabilitySettings.model_validate(row.data if row else {})

    async def save_interview_availability(
        self,
        payload: InterviewAvailabilitySettings,
        actor_id: int,
        *,
        company_id: int | None = None,
    ) -> InterviewAvailabilitySettings:
        if company_id is None:
            raise ValueError("Interview hours are stored per company.")
        await self.repo.upsert(
            f"company:{company_id}",
            "interview_availability",
            payload.model_dump(mode="json"),
            actor_id,
        )
        return payload

    async def load_ai_runtime(self) -> None:
        secrets = await self._secrets()
        self.apply_ai_runtime(await self.get_ai_model(), secrets)
        self.apply_screening_runtime(await self.get_screening_policy())


DEFAULT_APPEARANCE = AppearanceSettings()
DEFAULT_NOTIFICATIONS = NotificationSettings()
