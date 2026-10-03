from types import SimpleNamespace

from services.audit_service import (
    _message_with_actor,
    pick_session_login,
    resolve_audit_company_id,
)


def _event(action, user_id, name="Admin"):
    return SimpleNamespace(action=action, user_id=user_id, user_name=name)


def test_pick_session_login_uses_signed_in_admin():
    picked = pick_session_login([_event("USER_LOGIN", 1, "Admin")])
    assert picked is not None
    assert picked.user_id == 1
    assert picked.user_name == "Admin"


def test_pick_session_login_skips_user_who_already_logged_out():
    events = [
        _event("USER_LOGOUT", 2, "HR"),
        _event("USER_LOGIN", 2, "HR"),
        _event("USER_LOGIN", 1, "Admin"),
    ]
    picked = pick_session_login(events)
    assert picked is not None
    assert picked.user_id == 1


def test_message_replaces_system_actor():
    assert _message_with_actor(
        "System evaluated resume for Asha (score 80, Shortlisted).",
        "Admin",
        "Asha",
    ) == "Admin evaluated resume for Asha (score 80, Shortlisted)."
    assert _message_with_actor(
        "AI screening completed for Asha (score 80, SHORTLISTED).",
        "Admin",
        "Asha",
    ) == "Admin evaluated resume for Asha (score 80, SHORTLISTED)."


def test_resolve_audit_company_prefers_explicit_then_working_company():
    superadmin = SimpleNamespace(company_id=None)
    hr = SimpleNamespace(company_id=7)
    request = SimpleNamespace(
        headers={"x-company-id": "3"},
        query_params={},
    )
    assert resolve_audit_company_id(company_id=5, user=superadmin, request=request) == 5
    assert resolve_audit_company_id(user=superadmin, request=request) == 3
    assert resolve_audit_company_id(user=hr, request=None) == 7
    assert resolve_audit_company_id(user=superadmin, request=None) is None
    assert resolve_audit_company_id(
        user=superadmin,
        context={"company_id": 4},
    ) == 4
