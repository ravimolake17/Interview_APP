"""Shared Agent 5 session bootstrap for HR bridge and interview join gate."""

from __future__ import annotations

import logging
from typing import Any

from agents.proctoring_agent.integration import agent5_ready, startup_agent5
from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _agent5_links(session_id: str, token: str, *, role: str | None = None, company_code: str | None = None) -> tuple[str, str]:
    base = settings.agent5_public_url.rstrip("/")
    role_q = f"&role={role}" if role else ""
    code = str(company_code or "").strip()
    company_q = f"&company={code}" if code else ""
    proctoring = f"{base}/proctoring/?session_id={session_id}&token={token}{role_q}{company_q}"
    monitor = f"{base}/monitor/"
    return proctoring, monitor


def resolve_company_code(candidate_id: str, explicit: str | None = None) -> str | None:
    code = str(explicit or "").strip().upper()
    if code:
        return code
    try:
        from agents.proctoring_agent.db import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as db:
            row = db.execute(
                text(
                    "SELECT co.code FROM public.companies co "
                    "JOIN public.candidate c ON c.company_id = co.id "
                    "WHERE c.candidate_id = :cid"
                ),
                {"cid": candidate_id},
            ).first()
        if row and row[0]:
            return str(row[0]).strip().upper()
    except Exception:
        logger.debug("Could not resolve company code for %s", candidate_id, exc_info=True)
    return None


def issue_session_token(
    *,
    session_id: str,
    agent5_candidate_id: str,
    rr_candidate_id: str,
    participant_role: str = "candidate",
    company_code: str | None = None,
) -> str:
    """Mint a short-lived Agent5 bearer token for candidate or HR room entry."""
    from agents.proctoring_agent.config import get_settings as agent5_settings
    from agents.proctoring_agent.security import create_token

    a5_settings = agent5_settings()
    extra = {
        "session_id": session_id,
        "rr_candidate_id": rr_candidate_id,
        "participant_role": participant_role,
    }
    code = resolve_company_code(rr_candidate_id, company_code)
    if code:
        extra["company_code"] = code
    return create_token(
        agent5_candidate_id,
        "candidate",
        a5_settings.candidate_token_minutes,
        extra,
    )


def bootstrap_agent5_session(
    *,
    candidate_id: str,
    full_name: str,
    email: str,
    existing_snapshot: dict[str, Any] | None = None,
    participant_role: str = "candidate",
    company_code: str | None = None,
) -> dict[str, Any]:
    """Create or reuse an Agent5 proctoring session for an RR candidate."""
    startup = startup_agent5()
    if not startup.get("ok"):
        raise RuntimeError(str(startup.get("error") or "Agent5 is not configured"))

    role = "hr" if str(participant_role).lower() == "hr" else "candidate"
    company_code = resolve_company_code(candidate_id, company_code)
    meta = dict(existing_snapshot or {})
    if meta.get("session_id") and meta.get("token"):
        # Always re-issue token so HR/candidate role claims stay correct and tokens stay fresh.
        from agents.proctoring_agent.db import SessionLocal
        from agents.proctoring_agent.models import InterviewSession as Agent5Session

        session_id = str(meta["session_id"])
        with SessionLocal() as agent_db:
            a5_session = agent_db.get(Agent5Session, session_id)
            if a5_session is None:
                raise RuntimeError("Stored Agent5 session is missing; re-bootstrap required.")
            token = issue_session_token(
                session_id=session_id,
                agent5_candidate_id=a5_session.candidate_id,
                rr_candidate_id=candidate_id,
                participant_role=role,
                company_code=company_code,
            )
        proctoring_url, monitor_url = _agent5_links(
            session_id, token, role=role if role == "hr" else None, company_code=company_code
        )
        return {
            "candidate_id": candidate_id,
            "agent5_session_id": session_id,
            "agent5_token": token,
            "proctoring_url": proctoring_url,
            "monitor_url": monitor_url,
            "ready": agent5_ready(),
            "reused": True,
            "participant_role": role,
        }

    from agents.proctoring_agent.db import SessionLocal
    from agents.proctoring_agent.models import Candidate as Agent5Candidate
    from agents.proctoring_agent.models import InterviewSession as Agent5Session
    from agents.proctoring_agent.services.audit import audit

    with SessionLocal() as agent_db:
        a5_candidate = Agent5Candidate(
            full_name=full_name,
            email=email.lower(),
        )
        a5_session = Agent5Session(candidate=a5_candidate)
        agent_db.add_all([a5_candidate, a5_session])
        agent_db.flush()
        token = issue_session_token(
            session_id=a5_session.id,
            agent5_candidate_id=a5_candidate.id,
            rr_candidate_id=candidate_id,
            participant_role=role,
            company_code=company_code,
        )
        audit(
            agent_db,
            "system",
            "candidate_registered_from_rr",
            actor_id=candidate_id,
            target_type="session",
            target_id=a5_session.id,
        )
        agent_db.commit()

        proctoring_url, monitor_url = _agent5_links(
            a5_session.id, token, role=role if role == "hr" else None, company_code=company_code
        )
        return {
            "candidate_id": candidate_id,
            "agent5_session_id": a5_session.id,
            "agent5_token": token,
            "proctoring_url": proctoring_url,
            "monitor_url": monitor_url,
            "ready": agent5_ready(),
            "reused": False,
            "participant_role": role,
        }


def snapshot_payload_from_bootstrap(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": payload["agent5_session_id"],
        "token": payload["agent5_token"],
        "proctoring_url": payload["proctoring_url"],
        "monitor_url": payload["monitor_url"],
    }
