from types import SimpleNamespace

from core.tenancy import TenantDenied, build_scope, parse_company_id
from models.user import UserRole


def _user(role: UserRole, company_id: int | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=1, role=role, company_id=company_id, is_active=True)


def test_company_hr_is_locked_to_own_company():
    scope = build_scope(_user(UserRole.HR, 1))
    assert scope.filter_company_id == 1
    assert scope.allows(1)
    assert not scope.allows(2)


def test_company_admin_cannot_spoof_another_company():
    try:
        build_scope(_user(UserRole.COMPANY_ADMIN, 1), requested_company_id=2)
        assert False, "spoofed company_id must be rejected"
    except TenantDenied as exc:
        assert exc.status_code == 403
        assert "another company" in exc.message.lower()


def test_super_admin_can_see_all_or_one_company():
    all_scope = build_scope(_user(UserRole.SUPERADMIN, None))
    assert all_scope.filter_company_id is None
    assert all_scope.allows(1)
    assert all_scope.allows(2)

    one = build_scope(_user(UserRole.SUPERADMIN, None), requested_company_id=2)
    assert one.filter_company_id == 2
    assert one.allows(2)
    assert not one.allows(1)


def test_legacy_admin_role_is_company_admin():
    scope = build_scope(_user(UserRole.ADMIN, 1), requested_company_id=1)
    assert scope.filter_company_id == 1
    assert not scope.unrestricted


def test_parse_company_id_rejects_junk():
    assert parse_company_id(None) is None
    assert parse_company_id("3") == 3
    try:
        parse_company_id("abc")
        assert False
    except TenantDenied:
        pass
