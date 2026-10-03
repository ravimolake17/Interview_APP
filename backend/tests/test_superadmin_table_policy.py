from fastapi import HTTPException

from data.superadmin_table_policy import (
    is_blocked,
    is_secret_column,
    require_policy,
    sanitize_for_audit,
)
from services.superadmin_database_service import map_db_error


def test_blocks_credential_and_framework_tables():
    assert is_blocked("public", "alembic_version")
    assert is_blocked("public", "refresh_tokens")
    assert is_blocked("public", "schedule_token")
    assert is_blocked("public", "application_settings")
    assert is_blocked("public", "checkpoint_blobs")
    assert is_blocked("public", "checkpoint_writes")
    assert is_blocked("agent5", "sessions")
    assert is_blocked("agent5", "admin_users")


def test_allowlisted_business_tables_are_readable_not_generically_writable():
    policy = require_policy("public", "users", write=False)
    assert policy.name == "users"
    try:
        require_policy("public", "users", write=True)
        assert False, "generic writes must be rejected"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "Data Management" in exc.detail


def test_audit_logs_are_read_only():
    policy = require_policy("public", "audit_logs", write=False)
    assert policy.access.value == "read"
    try:
        require_policy("public", "audit_logs", write=True)
        assert False, "audit history must not be writable"
    except HTTPException as exc:
        assert exc.status_code == 403


def test_unknown_tables_are_denied_even_if_not_named_in_block_list():
    try:
        require_policy("public", "totally_new_table", write=False)
        assert False, "unknown tables must be denied"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "allowlist" in exc.detail.lower()


def test_secret_columns_are_redacted_from_audit_payloads():
    assert is_secret_column("password_hash")
    assert is_secret_column("join_token_hash")
    payload = sanitize_for_audit(
        {
            "email": "old@email.com",
            "password": "secret",
            "password_hash": "hash",
            "nested": {"api_key": "k", "status": "SHORTLISTED"},
        }
    )
    assert payload["email"] == "old@email.com"
    assert "password" not in payload
    assert "password_hash" not in payload
    assert "api_key" not in payload["nested"]
    assert payload["nested"]["status"] == "SHORTLISTED"


def test_integrity_errors_are_mapped_without_raw_sql():
    class FakeIntegrity:
        orig = 'insert or update on table "users" violates foreign key constraint "users_department_id_fkey"'

    error = map_db_error(FakeIntegrity())
    assert error.status_code == 409
    assert "postgres" not in error.detail.lower()
    assert "fkey" not in error.detail.lower()
    assert "related records" in error.detail.lower()


def test_generic_console_writes_return_403_even_for_superadmin():
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.deps import get_current_superadmin
    from api.routes.superadmin import router
    from models.user import UserRole

    app = FastAPI()
    app.include_router(router)

    async def fake_superadmin():
        return SimpleNamespace(id=1, email="sa@test.com", full_name="SA", role=UserRole.SUPERADMIN)

    app.dependency_overrides[get_current_superadmin] = fake_superadmin
    client = TestClient(app)

    audit = client.patch(
        "/superadmin/database/tables/public/audit_logs/rows/1",
        json={"values": {"action": "tamper"}},
    )
    assert audit.status_code == 403

    alembic = client.delete("/superadmin/database/tables/public/alembic_version/rows/1")
    assert alembic.status_code == 403
    assert "blocked" in alembic.json()["detail"].lower()

    users = client.patch(
        "/superadmin/database/tables/public/users/rows/1",
        json={"values": {"email": "x@test.com"}},
    )
    assert users.status_code == 403
    assert "data management" in users.json()["detail"].lower()


def test_all_data_and_console_routes_require_superadmin():
    from api.deps import get_current_superadmin
    from api.routes.superadmin import router as console_router
    from api.routes.superadmin_data import router as data_router

    def uses_superadmin(route) -> bool:
        stack = list(route.dependant.dependencies)
        while stack:
            dep = stack.pop()
            if dep.call is get_current_superadmin:
                return True
            stack.extend(dep.dependencies)
        return False

    routes = [
        route
        for route in [*console_router.routes, *data_router.routes]
        if getattr(route, "dependant", None)
    ]
    assert routes
    missing = [getattr(route, "path", "") for route in routes if not uses_superadmin(route)]
    assert not missing, f"Routes missing SuperAdmin guard: {missing}"
