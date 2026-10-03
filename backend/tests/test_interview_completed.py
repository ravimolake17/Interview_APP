from services.interview_completion_service import (
    agent5_session_id_from_snapshot,
    snapshot_shows_completed,
)


def test_snapshot_detects_completed_runtime():
    assert snapshot_shows_completed(
        {"agent5": {"interview_runtime": {"state": "COMPLETED"}}}
    )
    assert snapshot_shows_completed({"interview_runtime": {"state": "COMPLETED"}})
    assert snapshot_shows_completed(
        {"agent5": {"interview_runtime": {"state": "ENDED"}}}
    )


def test_snapshot_ignores_active_runtime():
    assert not snapshot_shows_completed(
        {"agent5": {"interview_runtime": {"state": "AI_INTERVIEW_ACTIVE"}}}
    )
    assert not snapshot_shows_completed(None)
    assert not snapshot_shows_completed({})


def test_agent5_session_id_falls_back_to_runtime():
    assert agent5_session_id_from_snapshot(
        {"agent5": {"session_id": "abc"}}
    ) == "abc"
    assert agent5_session_id_from_snapshot(
        {"agent5": {"interview_runtime": {"agent5_session_id": "from-runtime"}}}
    ) == "from-runtime"
