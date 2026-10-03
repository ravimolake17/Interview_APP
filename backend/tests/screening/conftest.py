"""Shared screening test defaults."""

import pytest

from agents.screening_agent.config import settings


@pytest.fixture(autouse=True)
def disable_semantic_matching_in_legacy_tests(monkeypatch):
    """Keep existing rule-based tests stable unless a test opts into semantic."""
    monkeypatch.setattr(settings, "ATS_SEMANTIC_MATCHING_ENABLED", False)
