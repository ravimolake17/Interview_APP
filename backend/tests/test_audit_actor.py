from types import SimpleNamespace

from services.audit_service import (
    _message_with_actor,
    diff_values,
    pick_session_login,
    prepare_audit_payload,
    resolve_audit_company_id,
    summarize_changes,
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


def test_diff_values_reports_nested_and_catalog_changes():
    old = {
        "provider": "groq",
        "temperature": 0.7,
        "api_key": "secret",
        "chat_models": [{"id": "llama", "name": "Llama", "model_id": "llama-3.3"}],
    }
    new = {
        "provider": "azure",
        "temperature": 0.7,
        "api_key": "secret",
        "chat_models": [{"id": "llama", "name": "Llama", "model_id": "gpt-4o"}],
    }
    changes = {item["field"]: item for item in diff_values(old, new)}
    assert changes["provider"]["from"] == "groq"
    assert changes["provider"]["to"] == "azure"
    assert changes["chat_models[llama].model_id"]["from"] == "llama-3.3"
    assert changes["chat_models[llama].model_id"]["to"] == "gpt-4o"
    assert "temperature" not in changes
    assert "api_key" not in changes


def test_prepare_audit_payload_stores_old_new_and_clear_message():
    old_value, new_value, details, message = prepare_audit_payload(
        old_value={"model_id": "gpt-4o", "temperature": 0.5, "password": "secret"},
        new_value={"model_id": "gpt-4o-mini", "temperature": 0.75, "password": "secret"},
        message="Super Admin updated AI model settings.",
    )
    assert old_value == {"model_id": "gpt-4o", "temperature": 0.5}
    assert new_value == {"model_id": "gpt-4o-mini", "temperature": 0.75}
    assert details["changed_fields"] == ["model_id", "temperature"]
    assert "model id: gpt-4o → gpt-4o-mini" in message
    assert "password" not in (old_value or {})
    assert summarize_changes(details["changes"]).startswith("model id:")
