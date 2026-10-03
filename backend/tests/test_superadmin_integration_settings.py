from services.application_settings_service import is_secret_unchanged
from services.email_service import SmtpRuntime


def test_secret_keep_when_masked_or_blank():
    assert is_secret_unchanged(None)
    assert is_secret_unchanged("")
    assert is_secret_unchanged("   ")
    assert is_secret_unchanged("Not configured")
    assert is_secret_unchanged("••••••••FE3i")
    assert not is_secret_unchanged("gsk_live_new_key")
    assert not is_secret_unchanged("new-smtp-password")


def test_smtp_runtime_configured():
    missing = SmtpRuntime(
        host="",
        port=587,
        username="user",
        password="secret",
        from_email="hr@example.com",
        from_name="HR",
    )
    assert not missing.configured()
    ok = SmtpRuntime(
        host="smtp.office365.com",
        port=587,
        username="user",
        password="secret",
        from_email="hr@example.com",
        from_name="RR Parkon HR Team",
    )
    assert ok.configured()
