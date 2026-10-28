from services.interview_speed_cache import max_interview_followups


def test_followup_budget_bands():
    assert max_interview_followups(0) == 0
    assert max_interview_followups(4) == 0
    assert max_interview_followups(5) == 1
    assert max_interview_followups(9) == 1
    assert max_interview_followups(10) == 2
    assert max_interview_followups(11) == 2
    assert max_interview_followups(12) == 2
    assert max_interview_followups(14) == 3
    assert max_interview_followups(15) == 3
    assert max_interview_followups(20) == 4
