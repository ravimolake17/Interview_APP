from agents.interview_agent.mcq import intro_message
from agents.shared.model_catalog import (
    hydrate_catalog,
    interviewer_display_name,
    merge_ai_model_payload,
    ordered_targets,
    set_runtime_catalog,
    should_fallback,
    uses_groq_primary_chat,
    voice_for_entry,
)
from schemas.settings import AICatalogEntry, AIModelSettings


def test_should_fallback_on_overload_and_server_errors():
    class Fake(Exception):
        def __init__(self, status_code=None, message=""):
            super().__init__(message)
            self.status_code = status_code

    assert should_fallback(Fake(429, "rate limit"))
    assert should_fallback(Fake(503, "unavailable"))
    assert should_fallback(Fake(None, "upstream connect error or disconnect/reset"))
    assert should_fallback(Fake(None, "no healthy upstream"))
    assert not should_fallback(Fake(400, "invalid json schema"))


def test_hydrate_builds_primary_and_fallback_catalog():
    settings = hydrate_catalog(
        AIModelSettings(
            provider="azure",
            model_id="gpt-4o",
            azure_openai_endpoint="https://example.openai.azure.com",
            azure_openai_deployment="gpt-4o",
            stt_provider="azure",
            tts_provider="azure",
        )
    )
    assert settings.chat_primary_id == "azure-gpt-4o"
    assert settings.chat_fallback_id == "groq-gpt-oss-120b"
    assert settings.stt_primary_id == "azure-speech-stt"
    assert settings.stt_fallback_id == "groq-whisper"
    assert settings.tts_primary_id == "azure-speech-tts"
    assert settings.tts_fallback_id == "edge-neural"
    assert {item.id for item in settings.chat_models} >= {
        "azure-gpt-4o",
        "azure-gpt-4o-mini",
        "groq-gpt-oss-120b",
    }


def test_hydrate_keeps_custom_chat_model():
    settings = hydrate_catalog(
        AIModelSettings(
            provider="azure",
            model_id="gpt-4o",
            chat_models=[
                AICatalogEntry(
                    id="azure-gpt-4o",
                    name="Azure GPT-4o",
                    kind="chat",
                    provider="azure",
                    model_id="gpt-4o",
                ),
                AICatalogEntry(
                    id="azure-gpt-5-mini",
                    name="Azure GPT-5 mini",
                    kind="chat",
                    provider="azure",
                    model_id="gpt-5-mini",
                    enabled=True,
                ),
                AICatalogEntry(
                    id="groq-gpt-oss-120b",
                    name="Groq GPT-OSS 120B",
                    kind="chat",
                    provider="groq",
                    model_id="openai/gpt-oss-120b",
                ),
            ],
            chat_primary_id="azure-gpt-4o",
            chat_fallback_id="groq-gpt-oss-120b",
        )
    )
    assert any(item.id == "azure-gpt-5-mini" for item in settings.chat_models)
    assert settings.chat_primary_id == "azure-gpt-4o"


def test_merge_keeps_custom_catalog_when_partial_patch_omits_models():
    current = hydrate_catalog(
        AIModelSettings(
            provider="azure",
            model_id="gpt-4o",
            chat_models=[
                AICatalogEntry(
                    id="azure-gpt-5-mini",
                    name="Azure GPT-5 mini",
                    kind="chat",
                    provider="azure",
                    model_id="gpt-5-mini",
                )
            ],
        )
    ).model_dump()
    partial = AIModelSettings(provider="azure", model_id="gpt-4o", temperature=0.2)
    merged = merge_ai_model_payload(current, partial)
    ids = {
        item["id"] if isinstance(item, dict) else item.id
        for item in merged["chat_models"]
    }
    assert "azure-gpt-5-mini" in ids


def test_hydrate_does_not_restore_deleted_builtin_model():
    kept = [
        AICatalogEntry(
            id="azure-gpt-4o",
            name="Azure GPT-4o",
            kind="chat",
            provider="azure",
            model_id="gpt-4o",
        ),
        AICatalogEntry(
            id="azure-gpt-5-mini",
            name="Azure GPT-5 mini",
            kind="chat",
            provider="azure",
            model_id="gpt-5-mini",
        ),
        AICatalogEntry(
            id="groq-gpt-oss-120b",
            name="Groq GPT-OSS 120B",
            kind="chat",
            provider="groq",
            model_id="openai/gpt-oss-120b",
        ),
        AICatalogEntry(
            id="groq-gpt-oss-20b",
            name="Groq GPT-OSS 20B",
            kind="chat",
            provider="groq",
            model_id="openai/gpt-oss-20b",
        ),
    ]
    settings = hydrate_catalog(
        AIModelSettings(
            provider="azure",
            model_id="gpt-4o",
            chat_models=kept,
            chat_primary_id="azure-gpt-4o",
            chat_fallback_id="groq-gpt-oss-120b",
        )
    )
    ids = {item.id for item in settings.chat_models}
    assert "azure-gpt-4o-mini" not in ids
    assert "azure-gpt-5-mini" in ids


def test_merge_persists_deleted_builtin_model():
    current = hydrate_catalog(AIModelSettings(provider="azure", model_id="gpt-4o")).model_dump()
    remaining = [
        item
        for item in current["chat_models"]
        if (item["id"] if isinstance(item, dict) else item.id) != "azure-gpt-4o-mini"
    ]
    payload = AIModelSettings.model_validate({**current, "chat_models": remaining})
    merged = merge_ai_model_payload(current, payload)
    hydrated = hydrate_catalog(AIModelSettings.model_validate(merged))
    ids = {item.id for item in hydrated.chat_models}
    assert "azure-gpt-4o-mini" not in ids
    assert "azure-gpt-4o" in ids


def test_merge_saves_newly_added_catalog_row():
    current = hydrate_catalog(AIModelSettings(provider="azure", model_id="gpt-4o")).model_dump()
    extra = {
        "id": "azure-gpt-5-mini",
        "name": "Azure GPT-5 mini",
        "kind": "chat",
        "provider": "azure",
        "model_id": "gpt-5-mini",
        "enabled": True,
        "endpoint": "https://example.openai.azure.com",
        "api_version": "2024-10-21",
        "region": "",
        "notes": "",
    }
    payload = AIModelSettings.model_validate(
        {**current, "chat_models": list(current["chat_models"]) + [extra]}
    )
    merged = merge_ai_model_payload(current, payload)
    hydrated = hydrate_catalog(AIModelSettings.model_validate(merged))
    assert any(item.model_id == "gpt-5-mini" for item in hydrated.chat_models)


def test_ordered_targets_skips_disabled_and_prefers_primary():
    catalog = hydrate_catalog(AIModelSettings(provider="azure", model_id="gpt-4o"))
    catalog.chat_models = [
        AICatalogEntry(
            id="azure-gpt-4o",
            name="Azure GPT-4o",
            kind="chat",
            provider="azure",
            model_id="gpt-4o",
            enabled=False,
        ),
        AICatalogEntry(
            id="groq-gpt-oss-120b",
            name="Groq 120B",
            kind="chat",
            provider="groq",
            model_id="openai/gpt-oss-120b",
            enabled=True,
        ),
    ]
    catalog.chat_primary_id = "azure-gpt-4o"
    catalog.chat_fallback_id = "groq-gpt-oss-120b"
    set_runtime_catalog(catalog)
    targets = ordered_targets("chat")
    assert [item.id for item in targets] == ["groq-gpt-oss-120b"]
    assert uses_groq_primary_chat() is True


def test_ordered_targets_uses_remaining_enabled_as_extra_backups():
    catalog = hydrate_catalog(AIModelSettings(provider="azure", model_id="gpt-4o"))
    catalog.chat_models = [
        AICatalogEntry(
            id="azure-gpt-4o",
            name="Azure GPT-4o",
            kind="chat",
            provider="azure",
            model_id="gpt-4o",
            enabled=True,
        ),
        AICatalogEntry(
            id="groq-gpt-oss-120b",
            name="Groq 120B",
            kind="chat",
            provider="groq",
            model_id="openai/gpt-oss-120b",
            enabled=True,
        ),
        AICatalogEntry(
            id="groq-gpt-oss-20b",
            name="Groq 20B",
            kind="chat",
            provider="groq",
            model_id="openai/gpt-oss-20b",
            enabled=True,
        ),
        AICatalogEntry(
            id="azure-gpt-5-mini",
            name="Azure GPT-5 mini",
            kind="chat",
            provider="azure",
            model_id="gpt-5-mini",
            enabled=True,
        ),
        AICatalogEntry(
            id="off-model",
            name="Off",
            kind="chat",
            provider="groq",
            model_id="openai/gpt-oss-20b",
            enabled=False,
        ),
    ]
    catalog.chat_primary_id = "azure-gpt-4o"
    catalog.chat_fallback_id = "azure-gpt-5-mini"
    set_runtime_catalog(catalog)
    assert [item.id for item in ordered_targets("chat")] == [
        "azure-gpt-4o",
        "azure-gpt-5-mini",
        "groq-gpt-oss-120b",
        "groq-gpt-oss-20b",
    ]


def test_call_llama_falls_back_after_primary_server_error(monkeypatch):
    from agents.shared import llama_client

    catalog = hydrate_catalog(AIModelSettings(provider="azure", model_id="gpt-4o"))
    set_runtime_catalog(catalog)
    calls = []

    def fake_invoke(entry, system_prompt, user_prompt, **kwargs):
        calls.append(entry.id if entry else None)
        if entry and entry.provider == "azure":
            error = RuntimeError("upstream connect error or disconnect/reset before headers")
            error.status_code = 503
            raise error
        return '{"ok": true}'

    monkeypatch.setattr(llama_client, "_invoke_chat_target", fake_invoke)
    result = llama_client.call_llama("sys", "user", json_mode=True)
    assert result == '{"ok": true}'
    assert calls[0] == "azure-gpt-4o"
    assert "groq-gpt-oss-120b" in calls


def test_tts_display_name_becomes_interviewer_persona():
    reena = AICatalogEntry(
        id="tts-reena",
        name="Reena",
        kind="tts",
        provider="azure",
        model_id="en-IN-NeerjaNeural",
        voice="female",
    )
    anuj = AICatalogEntry(
        id="tts-anuj",
        name="Anuj",
        kind="tts",
        provider="edge",
        model_id="en-IN-PrabhatNeural",
        voice="male",
    )
    generic = AICatalogEntry(
        id="azure-speech-tts",
        name="Azure Speech TTS",
        kind="tts",
        provider="azure",
        model_id="en-IN-NeerjaNeural",
    )
    assert interviewer_display_name(reena) == "Reena"
    assert interviewer_display_name(anuj) == "Anuj"
    assert interviewer_display_name(generic) == ""
    assert voice_for_entry(anuj) == "male"
    assert "I'm Reena, your AI interviewer" in intro_message(
        first_name="Arjun",
        company_name="RR Kabel",
        role="Engineer",
        interviewer_name="Reena",
    )


def test_azure_stt_locale_rejects_bare_en():
    from agents.interview_agent.stt_service import _azure_locale

    assert _azure_locale("en") == "en-IN"
    assert _azure_locale("en-IN") == "en-IN"


def test_foundry_project_endpoint_maps_to_openai_host():
    from agents.shared.model_catalog import normalize_azure_openai_endpoint

    assert (
        normalize_azure_openai_endpoint(
            "https://interview-openai-foundr-resource.services.ai.azure.com/api/projects/interview-openai-foundry-project"
        )
        == "https://interview-openai-foundr-resource.openai.azure.com"
    )
    assert (
        normalize_azure_openai_endpoint("https://interview-openai-foundr-resource.openai.azure.com/")
        == "https://interview-openai-foundr-resource.openai.azure.com"
    )


def test_catalog_needs_refresh_after_ttl(monkeypatch):
    from agents.shared import model_catalog

    catalog = hydrate_catalog(AIModelSettings(provider="azure", model_id="gpt-4o"))
    set_runtime_catalog(catalog)
    assert model_catalog.catalog_needs_refresh(ttl_seconds=60) is False
    monkeypatch.setattr(model_catalog, "_runtime_loaded_at", model_catalog._runtime_loaded_at - 5)
    assert model_catalog.catalog_needs_refresh(ttl_seconds=2) is True


def test_gpt5_family_uses_completion_tokens_not_max_tokens():
    from agents.shared.llama_client import _is_gpt5_family

    assert _is_gpt5_family("gpt-5-mini") is True
    assert _is_gpt5_family("gpt-4o") is False
