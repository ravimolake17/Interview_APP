from services.job_position import resolve_job_position_from_jd


def test_job_title_comes_from_parsed_jd_not_filename():
    title = resolve_job_position_from_jd(
        jd_text="Job Title: Python Backend Developer\nRequired Skills: Python",
        jd_original_filename="JD_v3_final.pdf",
        parsed_job_title="Python Backend Developer",
    )
    assert title == "Python Backend Developer"


def test_job_title_comes_from_jd_text_when_parser_title_missing():
    title = resolve_job_position_from_jd(
        jd_text="Position: AI/ML Engineer\nResponsibilities:\n- Train models",
        jd_original_filename="uploaded_jd.docx",
    )
    assert title == "AI/ML Engineer"


def test_generic_filename_is_not_used_as_job_title():
    title = resolve_job_position_from_jd(
        jd_original_filename="JD.pdf",
    )
    assert title == "Open Position"


def test_stored_filename_title_is_ignored_when_jd_has_a_role():
    title = resolve_job_position_from_jd(
        jd_text="Job Title: Data Scientist\nSkills: Python",
        jd_original_filename="JD_v3_final.pdf",
        stored_job_position="JD v3 final",
    )
    assert title == "Data Scientist"


def test_filename_is_last_resort_when_it_looks_like_a_role():
    title = resolve_job_position_from_jd(
        jd_original_filename="Python_Backend_Developer_v2.pdf",
    )
    assert title == "Python Backend Developer"


def test_job_save_title_comes_from_jd_content_not_filename():
    from services.job_position import apply_jd_content_title, is_filename_as_title, job_title_from_jd_content

    parsed = {"job_title": ""}
    title = apply_jd_content_title(
        parsed,
        "Job Title: Senior Data Scientist\nRequired Skills:\n- Python",
    )
    assert title == "Senior Data Scientist"
    assert parsed["job_title"] == "Senior Data Scientist"
    assert job_title_from_jd_content(
        jd_text="Role: Platform Engineer\nAbout the role",
        parsed_job_title="",
    ) == "Platform Engineer"
    assert is_filename_as_title("JD_v3_final", "JD_v3_final.pdf")
