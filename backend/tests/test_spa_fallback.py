"""SPA catch-all must serve React routes like /candidates/:id on hard refresh."""

from core.spa_fallback import spa_path_is_api_or_static


def test_candidates_spa_routes_are_not_skipped():
    assert spa_path_is_api_or_static("candidates") is False
    assert spa_path_is_api_or_static("candidates/CAND-C55FA0F9") is False
    assert spa_path_is_api_or_static("jobs") is False
    assert spa_path_is_api_or_static("reports") is False
    assert spa_path_is_api_or_static("login") is False
    assert spa_path_is_api_or_static("settings") is False
    assert spa_path_is_api_or_static("interview/abc-token") is False


def test_api_and_agent5_roots_are_skipped():
    assert spa_path_is_api_or_static("api/hr/candidates/x") is True
    assert spa_path_is_api_or_static("candidate/register") is True
    assert spa_path_is_api_or_static("health") is True
    assert spa_path_is_api_or_static("health/live") is True
    assert spa_path_is_api_or_static("docs") is True
    assert spa_path_is_api_or_static("extract") is True
    assert spa_path_is_api_or_static("proctoring/") is True
