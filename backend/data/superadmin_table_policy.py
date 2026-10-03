"""Server-side SuperAdmin table permissions. Frontend hiding is not sufficient."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from fastapi import HTTPException, status


class TableAccess(str, Enum):
    BLOCKED = "blocked"
    READ = "read"
    MANAGE = "manage"  # business Data Management only, not generic SQL writes


@dataclass(frozen=True)
class TablePolicy:
    schema: str
    name: str
    label: str
    access: TableAccess
    searchable: tuple[str, ...] = ()
    visible_columns: tuple[str, ...] | None = None  # None = all except hidden
    hidden_columns: tuple[str, ...] = ()
    notes: str = ""


# Columns that must never leave the API, even on allowlisted tables.
SECRET_COLUMNS = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "token_hash",
        "join_token_hash",
        "refresh_token",
        "api_key",
        "secret",
        "smtp_password",
        "jwt_secret",
        "groq_api_key",
        "azure_openai_api_key",
        "azure_speech_key",
    }
)

_POLICIES: dict[tuple[str, str], TablePolicy] = {}


def _register(policy: TablePolicy) -> TablePolicy:
    _POLICIES[(policy.schema, policy.name)] = policy
    return policy


# --- Data Management entities (ORM / existing APIs) ---
_register(TablePolicy("public", "companies", "Companies", TableAccess.MANAGE, searchable=("name", "code", "status"), notes="Edit in Company management. Console is read-only."))
_register(TablePolicy("public", "users", "Users", TableAccess.MANAGE, searchable=("email", "full_name", "role"), notes="Edit in Data Management. Console is read-only."))
_register(TablePolicy("public", "candidate", "Candidates", TableAccess.MANAGE, searchable=("full_name", "email", "job_position", "status", "candidate_id"), notes="Edit in Data Management. Console is read-only."))
_register(TablePolicy("public", "job_postings", "Jobs", TableAccess.MANAGE, searchable=("title", "department", "status", "location"), notes="Edit in Data Management. Console is read-only."))
_register(TablePolicy("public", "departments", "Departments", TableAccess.MANAGE, searchable=("name",), notes="Jobs store department by name; renaming does not rewrite historical job rows."))

# --- Database Console: read-only technical / historical ---
_register(
    TablePolicy(
        "public",
        "audit_logs",
        "Audit logs",
        TableAccess.READ,
        searchable=("action", "entity_type", "user_email", "message"),
        hidden_columns=("user_agent",),
        notes="Historical record. Snapshots are never rewritten.",
    )
)
_register(TablePolicy("public", "screening_jobs", "Screening jobs", TableAccess.READ, searchable=("status", "id")))
_register(TablePolicy("public", "interview", "Interviews", TableAccess.READ, searchable=("candidate_id", "status"), hidden_columns=("join_token_hash",)))
_register(TablePolicy("public", "interview_blueprint", "Interview blueprints", TableAccess.READ, searchable=("candidate_id",)))
_register(TablePolicy("public", "interview_evaluations", "Interview evaluations", TableAccess.READ))
_register(TablePolicy("public", "interview_question_sets", "Interview question sets", TableAccess.READ))
_register(TablePolicy("public", "hr_recommendation_reports", "HR recommendation reports", TableAccess.READ))
_register(TablePolicy("public", "available_slots", "Available slots", TableAccess.READ, searchable=("date", "booked_candidate")))

# Explicit blocks (also used as a deny list if information_schema returns extras).
_BLOCKED_NAMES = frozenset(
    {
        "alembic_version",
        "refresh_tokens",
        "schedule_token",
        "application_settings",
        "checkpoint",
        "checkpoints",
        "checkpoint_blobs",
        "checkpoint_writes",
        "checkpoint_migrations",
        "interview_question_audio",
        "admin_users",
    }
)

_BLOCKED_PREFIXES = ("checkpoint",)
_BLOCKED_SCHEMAS = frozenset({"agent5"})


def is_blocked(schema: str, table: str) -> bool:
    if schema in _BLOCKED_SCHEMAS:
        return True
    if table in _BLOCKED_NAMES:
        return True
    if any(table.startswith(prefix) for prefix in _BLOCKED_PREFIXES):
        return True
    return False


def get_policy(schema: str, table: str) -> TablePolicy | None:
    return _POLICIES.get((schema, table))


def require_policy(schema: str, table: str, *, write: bool = False) -> TablePolicy:
    if is_blocked(schema, table):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This table is blocked from the Database Console.",
        )
    policy = get_policy(schema, table)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This table is not on the SuperAdmin allowlist.",
        )
    if write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Generic table edits are not allowed. Use Data Management for business records.",
        )
    if policy.access == TableAccess.BLOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This table is blocked from the Database Console.",
        )
    return policy


def console_policies() -> list[TablePolicy]:
    return [
        policy
        for policy in _POLICIES.values()
        if policy.access in {TableAccess.READ, TableAccess.MANAGE}
    ]


def is_secret_column(name: str) -> bool:
    lowered = name.lower()
    if lowered in SECRET_COLUMNS:
        return True
    return any(token in lowered for token in ("password", "token_hash", "api_key", "secret"))


def sanitize_for_audit(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: sanitize_for_audit(item)
            for key, item in value.items()
            if not is_secret_column(str(key))
        }
    if isinstance(value, list):
        return [sanitize_for_audit(item) for item in value]
    return value
