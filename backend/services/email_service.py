"""SMTP email service for interview notifications."""

import base64
import logging
import smtplib
import uuid
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.config import Settings, get_settings

logger = logging.getLogger(__name__)
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"
ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "assets"
PARKON_LOGO = ASSETS_DIR / "Parkon_logo.png"
KABEL_LOGO = ASSETS_DIR / "RR-Kabel-logo.png"


@dataclass(frozen=True)
class SmtpRuntime:
    host: str
    port: int
    username: str
    password: str
    from_email: str
    from_name: str
    use_tls: bool = True
    use_ssl: bool = False
    timeout_seconds: int = 30

    def configured(self) -> bool:
        return bool(self.host and self.username and self.password and self.from_email)


def _is_kabel(company_code: str | None = None, company_name: str | None = None) -> bool:
    code = str(company_code or "").strip().upper()
    name = str(company_name or "").strip().lower()
    return code in {"RRKABEL", "KABEL"} or "kabel" in name


def resolve_email_brand(
    company_code: str | None = None,
    company_name: str | None = None,
) -> dict[str, str]:
    if _is_kabel(company_code, company_name):
        return {
            "company_name": company_name or "RR Kabel",
            "subject_prefix": "RR Kabel",
            "from_name": "RR Kabel HR Team",
            "logo_path": str(KABEL_LOGO),
        }
    return {
        "company_name": company_name or "RR Parkon",
        "subject_prefix": "RR Parkon",
        "from_name": "RR Parkon HR Team",
        "logo_path": str(PARKON_LOGO),
    }


class EmailService:
    """Send interview emails via SMTP (TLS/SSL)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def _runtime(self, smtp: SmtpRuntime | None) -> SmtpRuntime | None:
        if smtp and smtp.configured():
            return smtp
        if self._is_configured():
            return SmtpRuntime(
                host=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_user,
                password=self.settings.smtp_password,
                from_email=self.settings.smtp_from_email,
                from_name=self.settings.smtp_from_name,
                use_tls=self.settings.smtp_use_tls,
                use_ssl=self.settings.smtp_use_ssl,
                timeout_seconds=self.settings.smtp_timeout_seconds,
            )
        return None

    def _is_configured(self) -> bool:
        return bool(
            self.settings.smtp_host
            and self.settings.smtp_user
            and self.settings.smtp_password
            and self.settings.smtp_from_email
        )

    def _send_message(
        self,
        to: str,
        subject: str,
        html_body: str,
        *,
        from_name: str | None = None,
        smtp: SmtpRuntime | None = None,
    ) -> dict:
        runtime = self._runtime(smtp)
        if runtime is None:
            logger.warning(
                "SMTP not configured — email logged only. "
                "Set company SMTP in SuperAdmin or SMTP_* in .env"
            )
            logger.info("[DEV MODE] Email to=%s subject=%s\n%s", to, subject, html_body)
            return {"id": "dev-mode-message-id", "status": "logged"}

        sender_name = from_name or runtime.from_name
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = (
            f"{sender_name} <{runtime.from_email}>"
            if sender_name
            else runtime.from_email
        )
        message["To"] = to
        message.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            if runtime.use_ssl:
                with smtplib.SMTP_SSL(
                    runtime.host,
                    runtime.port,
                    timeout=runtime.timeout_seconds,
                ) as server:
                    server.ehlo()
                    server.login(runtime.username, runtime.password)
                    server.sendmail(runtime.from_email, [to], message.as_string())
            else:
                with smtplib.SMTP(
                    runtime.host,
                    runtime.port,
                    timeout=runtime.timeout_seconds,
                ) as server:
                    server.ehlo()
                    if runtime.use_tls:
                        server.starttls()
                        server.ehlo()
                    server.login(runtime.username, runtime.password)
                    server.sendmail(runtime.from_email, [to], message.as_string())

            message_id = str(uuid.uuid4())
            logger.info("Email sent via SMTP to=%s subject=%s", to, subject)
            return {"id": message_id, "status": "sent"}
        except (smtplib.SMTPException, OSError, TimeoutError) as exc:
            logger.exception("SMTP send failed for to=%s", to)
            raise RuntimeError(f"Failed to send email: {exc}") from exc

    def _get_logo_data_uri(self, logo_path: str | None = None) -> str:
        path = Path(logo_path) if logo_path else PARKON_LOGO
        if not path.exists():
            logger.warning("Logo not found at %s", path)
            return ""
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    def send_congratulations_email(
        self,
        candidate_name: str,
        candidate_email: str,
        scheduling_link: str,
        job_position: str = "",
        *,
        company_code: str | None = None,
        company_name: str | None = None,
        smtp: SmtpRuntime | None = None,
    ) -> dict:
        brand = resolve_email_brand(company_code, company_name)
        template = self._jinja_env.get_template("congratulations.html")
        html = template.render(
            candidate_name=candidate_name,
            scheduling_link=scheduling_link,
            job_position=job_position,
            company_name=brand["company_name"].upper(),
            logo_data_uri=self._get_logo_data_uri(brand["logo_path"]),
        )
        return self._send_message(
            to=candidate_email,
            subject=f"{brand['subject_prefix']} | Your Resume Has Been Shortlisted",
            html_body=html,
            from_name=smtp.from_name if smtp and smtp.from_name else brand["from_name"],
            smtp=smtp,
        )

    def send_confirmation_email(
        self,
        candidate_name: str,
        candidate_email: str,
        interview_date: str,
        interview_time: str,
        join_link: str,
        job_position: str = "",
        *,
        company_code: str | None = None,
        company_name: str | None = None,
        smtp: SmtpRuntime | None = None,
    ) -> dict:
        brand = resolve_email_brand(company_code, company_name)
        template = self._jinja_env.get_template("confirmation.html")
        html = template.render(
            candidate_name=candidate_name,
            interview_date=interview_date,
            interview_time=interview_time,
            join_link=join_link,
            job_position=job_position,
            company_name=brand["company_name"].upper(),
            logo_data_uri=self._get_logo_data_uri(brand["logo_path"]),
        )
        return self._send_message(
            to=candidate_email,
            subject=f"{brand['subject_prefix']} | Interview Scheduled Successfully",
            html_body=html,
            from_name=smtp.from_name if smtp and smtp.from_name else brand["from_name"],
            smtp=smtp,
        )
