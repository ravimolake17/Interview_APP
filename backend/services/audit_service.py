"""Record auditable HR and screening actions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from fastapi import Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import (
    get_client_ip,
    get_request_id,
    get_session_id,
    get_user_agent,
    resolve_location_label,
)
from core.tenancy import TenantDenied, parse_company_id
from models.audit_log import AuditLog
from models.user import User
from repositories.audit_log_repository import AuditLogRepository


def audit_context_from_request(user: User | None, request: Request | None) -> dict[str, Any]:
    """Snapshot of who triggered an action, for background jobs that have no HTTP user."""
    context: dict[str, Any] = {}
    if user is not None:
        context["user_id"] = user.id
        context["user_email"] = user.email
        context["user_name"] = user.full_name
        role = user.role.value if hasattr(user.role, "value") else str(user.role)
        context["user_role"] = role
        if getattr(user, "company_id", None) is not None:
            context["company_id"] = user.company_id
    if request is not None:
        context["ip_address"] = get_client_ip(request)
        context["user_agent"] = get_user_agent(request)
        context["session_id"] = get_session_id(request)
        context["request_id"] = get_request_id(request)
        context["location"] = resolve_location_label(context.get("ip_address"))
        requested = company_id_from_request(request)
        if requested is not None:
            context["company_id"] = requested
    return {key: value for key, value in context.items() if value is not None}


def company_id_from_request(request: Request | None) -> int | None:
    """Working company SuperAdmin selected (X-Company-Id), if present."""
    if request is None:
        return None
    header = request.headers.get("x-company-id")
    query = request.query_params.get("company_id") if hasattr(request, "query_params") else None
    raw = header if header not in (None, "") else query
    try:
        return parse_company_id(raw)
    except TenantDenied:
        return None


def resolve_audit_company_id(
    *,
    company_id: int | None = None,
    user: User | None = None,
    request: Request | None = None,
    context: dict[str, Any] | None = None,
) -> int | None:
    """Company the actor was working in. SuperAdmin has no user.company_id."""
    if company_id is not None:
        try:
            parsed = int(company_id)
        except (TypeError, ValueError):
            parsed = None
        if parsed:
            return parsed
    context = context or {}
    raw_context = context.get("company_id")
    if raw_context not in (None, ""):
        try:
            parsed = int(raw_context)
            if parsed:
                return parsed
        except (TypeError, ValueError):
            pass
    requested = company_id_from_request(request)
    if requested is not None:
        return requested
    if user is not None and getattr(user, "company_id", None):
        return int(user.company_id)
    return None


def snapshot_from_user(user: User | None) -> dict[str, Any]:
    if user is None:
        return {}
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    return {
        "user_id": user.id,
        "user_email": user.email,
        "user_name": user.full_name,
        "user_role": role,
    }


def _coerce_user_id(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def pick_session_login(events: Iterable[AuditLog]) -> AuditLog | None:
    """Newest USER_LOGIN that is still in session (no later logout for that user)."""
    seen: set[int] = set()
    for entry in events:
        uid = entry.user_id
        if uid is None or uid in seen:
            continue
        seen.add(uid)
        if entry.action == "USER_LOGIN":
            return entry
    return None


def _message_with_actor(message: str | None, actor_name: str, candidate_name: str) -> str:
    if not message:
        return f"{actor_name} evaluated resume for {candidate_name}."
    if message.startswith("AI screening completed for "):
        return f"{actor_name} evaluated resume for {message[len('AI screening completed for '):]}"
    if message.startswith("System "):
        return f"{actor_name} {message[len('System '):]}"
    return message


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = AuditLogRepository(db)

    async def log(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        user: User | None = None,
        details: dict[str, Any] | None = None,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: str | None = None,
        request_id: str | None = None,
        status: str = "SUCCESS",
        location: str | None = None,
        message: str | None = None,
        request: Request | None = None,
        context: dict[str, Any] | None = None,
        company_id: int | None = None,
    ) -> None:
        context = dict(context or {})
        if request is not None:
            ip_address = ip_address or get_client_ip(request)
            user_agent = user_agent or get_user_agent(request)
            session_id = session_id or get_session_id(request)
            request_id = request_id or get_request_id(request)
            if location is None:
                location = resolve_location_label(ip_address)
        else:
            ip_address = ip_address or context.get("ip_address")
            user_agent = user_agent or context.get("user_agent")
            session_id = session_id or context.get("session_id")
            request_id = request_id or context.get("request_id")
            if location is None:
                location = context.get("location") or resolve_location_label(ip_address)

        role = None
        if user is not None:
            role = user.role.value if hasattr(user.role, "value") else str(user.role)
        else:
            role = context.get("user_role")

        await self.repo.create(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            company_id=resolve_audit_company_id(
                company_id=company_id,
                user=user,
                request=request,
                context=context,
            ),
            user_id=_coerce_user_id(user.id if user else context.get("user_id")),
            user_email=user.email if user else context.get("user_email"),
            user_name=user.full_name if user else context.get("user_name"),
            user_role=role,
            details=details,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            request_id=request_id,
            status=status,
            location=location,
            message=message,
        )

    async def log_resume_evaluated(
        self,
        *,
        candidate: Any,
        shortlist_status: str,
        user: User | None = None,
        request: Request | None = None,
        context: dict[str, Any] | None = None,
        invite_sent: bool = False,
    ) -> None:
        context = dict(context or {})
        if user is None and not context.get("user_id"):
            snapshot = await self.actor_snapshot_at()
            for key, value in snapshot.items():
                context.setdefault(key, value)
            user = await self.resolve_actor_user(context)
        actor_name = (
            user.full_name
            if user is not None
            else str(context.get("user_name") or "System")
        )
        job_position = getattr(candidate, "job_position", None)
        score = float(getattr(candidate, "resume_score", 0) or 0)
        name = getattr(candidate, "full_name", "candidate")
        candidate_id = getattr(candidate, "candidate_id", None)
        await self.log(
            action="RESUME_EVALUATED",
            entity_type="candidate",
            entity_id=str(candidate_id) if candidate_id else None,
            user=user,
            request=request,
            context=context,
            details={
                "candidate_name": name,
                "job_position": job_position,
                "resume_score": score,
                "shortlist_status": shortlist_status,
            },
            message=(
                f"{actor_name} evaluated resume for {name} "
                f"(score {score:.0f}, {shortlist_status})."
            ),
            company_id=getattr(candidate, "company_id", None),
        )
        if not invite_sent:
            return
        await self.log(
            action="INTERVIEW_INVITE_SENT",
            entity_type="candidate",
            entity_id=str(candidate_id) if candidate_id else None,
            user=user,
            request=request,
            context=context,
            details={
                "candidate_name": name,
                "candidate_email": getattr(candidate, "email", None),
                "job_position": job_position,
                "source": "auto_shortlist_screening",
                "resume_score": score,
            },
            message=(
                f"{actor_name} auto-shortlisted {name} "
                f"(score {score:.0f}) and sent interview invite"
                + (f" for {job_position}" if job_position else "")
                + "."
            ),
            company_id=getattr(candidate, "company_id", None),
        )

    async def actor_snapshot_at(self, when: datetime | None = None) -> dict[str, Any]:
        """Staff user who was signed in at `when` (from login/logout audit)."""
        when = when or datetime.now(timezone.utc)
        result = await self.repo.db.execute(
            select(AuditLog)
            .where(
                AuditLog.action.in_(("USER_LOGIN", "USER_LOGOUT")),
                AuditLog.status == "SUCCESS",
                AuditLog.created_at <= when,
                AuditLog.user_id.is_not(None),
            )
            .order_by(AuditLog.created_at.desc())
        )
        login = pick_session_login(result.scalars().all())
        if login is not None:
            return {
                "user_id": login.user_id,
                "user_email": login.user_email,
                "user_name": login.user_name,
                "user_role": login.user_role,
                "ip_address": login.ip_address,
                "user_agent": login.user_agent,
                "session_id": login.session_id,
                "location": login.location,
            }

        users = list(
            (await self.repo.db.execute(select(User).where(User.is_active.is_(True)))).scalars()
        )
        if len(users) == 1:
            return snapshot_from_user(users[0])
        return {}

    async def resolve_actor_user(self, context: dict[str, Any] | None) -> User | None:
        user_id = _coerce_user_id((context or {}).get("user_id"))
        if user_id is None:
            return None
        from repositories.user_repository import UserRepository

        return await UserRepository(self.repo.db).get_by_id(user_id)

    def _apply_actor(self, entry: AuditLog, actor: dict[str, Any], candidate_name: str) -> None:
        actor_name = str(actor.get("user_name") or "System")
        entry.user_id = _coerce_user_id(actor.get("user_id"))
        entry.user_email = actor.get("user_email") or entry.user_email
        entry.user_name = actor_name
        entry.user_role = actor.get("user_role") or entry.user_role
        entry.ip_address = entry.ip_address or actor.get("ip_address")
        entry.user_agent = entry.user_agent or actor.get("user_agent")
        entry.session_id = entry.session_id or actor.get("session_id")
        entry.location = entry.location or actor.get("location")
        entry.message = _message_with_actor(entry.message, actor_name, candidate_name)

    async def backfill_missing_screening_audits(self) -> int:
        """Create RESUME_EVALUATED rows for candidates that were screened before queue logging existed."""
        from models.candidate import Candidate

        existing = await self.repo.entity_ids_for_action("RESUME_EVALUATED")
        result = await self.repo.db.execute(select(Candidate))
        created = 0
        for candidate in result.scalars():
            cid = str(candidate.candidate_id)
            if cid in existing:
                continue
            score = float(candidate.resume_score or 0)
            status = (
                candidate.status.value
                if hasattr(candidate.status, "value")
                else str(candidate.status)
            )
            actor = await self.actor_snapshot_at(candidate.created_at)
            actor_name = str(actor.get("user_name") or "System")
            entry = AuditLog(
                action="RESUME_EVALUATED",
                entity_type="candidate",
                entity_id=cid,
                company_id=candidate.company_id,
                user_id=_coerce_user_id(actor.get("user_id")),
                user_email=actor.get("user_email"),
                user_name=actor_name,
                user_role=actor.get("user_role"),
                ip_address=actor.get("ip_address"),
                user_agent=actor.get("user_agent"),
                session_id=actor.get("session_id"),
                location=actor.get("location"),
                details={
                    "candidate_name": candidate.full_name,
                    "job_position": candidate.job_position,
                    "resume_score": score,
                    "shortlist_status": status,
                    "source": "backfill",
                },
                status="SUCCESS",
                created_at=candidate.created_at,
                message=(
                    f"{actor_name} evaluated resume for {candidate.full_name} "
                    f"(score {score:.0f}, {status})."
                ),
            )
            self.repo.db.add(entry)
            created += 1
        if created:
            await self.repo.db.flush()
        return created

    async def repair_unattributed_screening_audits(self) -> int:
        """Fill HR/Admin identity on screening rows that were stored as System."""
        result = await self.repo.db.execute(
            select(AuditLog).where(
                AuditLog.action.in_(("RESUME_EVALUATED", "INTERVIEW_INVITE_SENT")),
                or_(
                    AuditLog.user_id.is_(None),
                    AuditLog.user_name.is_(None),
                    AuditLog.user_name == "System",
                ),
            )
        )
        repaired = 0
        for entry in result.scalars():
            actor = await self.actor_snapshot_at(entry.created_at)
            if not actor.get("user_id") and not actor.get("user_name"):
                continue
            if actor.get("user_name") in (None, "", "System") and not actor.get("user_id"):
                continue
            candidate_name = (entry.details or {}).get("candidate_name") or "candidate"
            self._apply_actor(entry, actor, candidate_name)
            repaired += 1
        if repaired:
            await self.repo.db.flush()
        return repaired

    async def repair_missing_audit_company_ids(self) -> int:
        """Fill company_id on SuperAdmin rows from the candidate/job/department they touched."""
        from models.candidate import Candidate
        from models.department import Department
        from models.job_posting import JobPosting

        result = await self.repo.db.execute(
            select(AuditLog).where(
                AuditLog.company_id.is_(None),
                AuditLog.entity_id.is_not(None),
                AuditLog.entity_type.in_(("candidate", "job", "department")),
            )
        )
        entries = list(result.scalars())
        if not entries:
            return 0

        candidate_ids = {
            str(entry.entity_id) for entry in entries if entry.entity_type == "candidate"
        }
        job_ids = {
            int(entry.entity_id)
            for entry in entries
            if entry.entity_type == "job" and str(entry.entity_id).isdigit()
        }
        dept_ids = {
            int(entry.entity_id)
            for entry in entries
            if entry.entity_type == "department" and str(entry.entity_id).isdigit()
        }

        candidate_companies: dict[str, int] = {}
        if candidate_ids:
            rows = await self.repo.db.execute(
                select(Candidate.candidate_id, Candidate.company_id).where(
                    Candidate.candidate_id.in_(candidate_ids)
                )
            )
            candidate_companies = {str(cid): int(cid_company) for cid, cid_company in rows.all()}

        job_companies: dict[str, int] = {}
        if job_ids:
            rows = await self.repo.db.execute(
                select(JobPosting.id, JobPosting.company_id).where(JobPosting.id.in_(job_ids))
            )
            job_companies = {str(job_id): int(cid_company) for job_id, cid_company in rows.all()}

        dept_companies: dict[str, int] = {}
        if dept_ids:
            rows = await self.repo.db.execute(
                select(Department.id, Department.company_id).where(Department.id.in_(dept_ids))
            )
            dept_companies = {str(dept_id): int(cid_company) for dept_id, cid_company in rows.all()}

        lookup = {
            "candidate": candidate_companies,
            "job": job_companies,
            "department": dept_companies,
        }
        repaired = 0
        for entry in entries:
            company_id = lookup.get(entry.entity_type, {}).get(str(entry.entity_id))
            if not company_id:
                continue
            entry.company_id = company_id
            repaired += 1
        if repaired:
            await self.repo.db.flush()
        return repaired

