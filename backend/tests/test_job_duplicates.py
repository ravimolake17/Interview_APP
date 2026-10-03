from services.job_posting_service import JobDuplicateError, resolve_job_title


def test_resolve_job_title_prefers_content_over_filename():
    title = resolve_job_title(
        parsed_jd={"job_title": "Python Developer"},
        title_override="python_developer.pdf",
        jd_original_filename="python_developer.pdf",
    )
    assert title == "Python Developer"


def test_resolve_job_title_keeps_explicit_override():
    title = resolve_job_title(
        parsed_jd={"job_title": "Python Developer"},
        title_override="Backend Engineer",
        jd_original_filename="python_developer.pdf",
    )
    assert title == "Backend Engineer"


def test_duplicate_error_message_mentions_replace_or_rename():
    job = type("Job", (), {"title": "Python Developer"})()
    err = JobDuplicateError(job, "title")
    assert "Python Developer" in str(err)
    assert "Replace" in str(err) or "replace" in str(err).lower()
