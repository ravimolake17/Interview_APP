from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog, SystemError


def audit(
    db: Session,
    actor_type: str,
    action: str,
    *,
    actor_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    record = AuditLog(
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
    )
    db.add(record)
    db.flush()
    return record


def record_error(db: Session, component: str, message: str, *, session_id: str | None = None, details: dict[str, Any] | None = None) -> SystemError:
    record = SystemError(session_id=session_id, component=component, message=message, details=details or {})
    db.add(record)
    db.flush()
    return record
