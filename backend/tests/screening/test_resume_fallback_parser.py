from agents.screening_agent.services.resume_parser import (
    extract_emails_from_text,
    guess_candidate_name,
    parse_resume,
)
from agents.screening_agent.services.resume_profile_service import build_candidate_profile


def test_fallback_skips_cv_title_and_finds_name():
    text = (
        "Curriculum Vitae\n"
        "Manav Shah\n"
        "Skills\nPython, FastAPI\n"
    )
    parsed = parse_resume(text)
    header = parsed["sections"][0]
    assert guess_candidate_name(text) == "Manav Shah"
    assert any(
        isinstance(item, dict) and item.get("value") == "Manav Shah"
        for item in header["items"]
    )


def test_fallback_finds_mailto_and_obfuscated_email():
    text = (
        "Priya Nair\n"
        "[email me](mailto:priya.nair@example.com)\n"
        "rahul [at] company [dot] com\n"
        "Experience\n"
        "Backend Engineer at Acme Jan 2022 - Present\n"
        "Built APIs.\n"
    )
    emails = extract_emails_from_text(text)
    assert "priya.nair@example.com" in emails
    assert "rahul@company.com" in emails

    parsed = parse_resume(text)
    contacts = parsed["sections"][0]["detected_contacts"]["emails"]
    assert "priya.nair@example.com" in contacts


def test_fallback_recovers_experience_without_heading():
    text = (
        "Anita Sharma\n"
        "anita.sharma@example.com\n"
        "Skills\nPython, PostgreSQL\n"
        "Backend Developer, Nimbus Labs\n"
        "Jan 2021 - Mar 2024\n"
        "Owned FastAPI services and reporting jobs.\n"
        "Education\nB.Tech Computer Science 2020\n"
    )
    parsed = parse_resume(text)
    headings = [section["heading"].casefold() for section in parsed["sections"]]
    assert any("experience" in heading for heading in headings)
    experience = next(
        section for section in parsed["sections"] if "experience" in section["heading"].casefold()
    )
    assert "Backend Developer" in experience["raw_text"]
    assert "Nimbus Labs" in experience["raw_text"]

    parsed["source_text"] = text
    profile = build_candidate_profile(parsed)
    assert profile.candidate_details.name == "Anita Sharma"
    assert "anita.sharma@example.com" in profile.candidate_details.emails
    assert profile.experience_entries
    joined = " ".join(
        f"{entry.role} {entry.company} {entry.text}" for entry in profile.experience_entries
    )
    assert "Backend Developer" in joined
    assert "Nimbus Labs" in joined


def test_section_headings_are_not_used_as_candidate_names():
    text = (
        "Key Competencies\n"
        "Python, FastAPI, Django\n"
        "Khushbu Kushvaha\n"
        "khushbu.kushvaha.work@gmail.com\n"
        "SUMMARY\n"
        "Backend developer with 4 years experience.\n"
    )
    parsed = parse_resume(text)
    parsed["source_text"] = text
    profile = build_candidate_profile(
        parsed, resume_filename="Khushbu-Kushvaha-updated (1).pdf"
    )
    assert profile.candidate_details.name == "Khushbu Kushvaha"
    assert "khushbu.kushvaha.work@gmail.com" in profile.candidate_details.emails


def test_summary_heading_is_not_the_candidate_name():
    text = (
        "SUMMARY\n"
        "Akshay Dubey\n"
        "akshaydubey1818@gmail.com\n"
        "Python developer.\n"
    )
    parsed = parse_resume(text)
    parsed["source_text"] = text
    profile = build_candidate_profile(parsed)
    assert profile.candidate_details.name == "Akshay Dubey"
    assert "akshaydubey1818@gmail.com" in profile.candidate_details.emails


def test_skill_word_is_not_used_as_candidate_name():
    text = (
        "Python\n"
        "Developer\n"
        "abhijit.dhondkar@gmail.com\n"
        "Abhijit Dhondkar\n"
        "Education\nB.E. Computer Engineering, Pune University\n"
    )
    parsed = parse_resume(text)
    parsed["source_text"] = text
    profile = build_candidate_profile(parsed)
    assert profile.candidate_details.name == "Abhijit Dhondkar"
    assert "abhijit.dhondkar@gmail.com" in profile.candidate_details.emails
    assert any("Computer Engineering" in line or "B.E" in line for line in profile.education)


def test_education_is_found_when_section_is_missing_from_parsed_rows():
    text = (
        "Priya Nair\n"
        "priya.nair@example.com\n"
        "Skills\nPython\n"
        "B.Tech in Computer Science\nAnna University\n"
    )
    parsed = parse_resume(text)
    parsed["source_text"] = text
    # Simulate a parser that dropped the education heading.
    parsed["sections"] = [
        section
        for section in parsed["sections"]
        if "education" not in str(section.get("heading", "")).casefold()
    ]
    profile = build_candidate_profile(parsed)
    assert profile.education
    assert any("B.Tech" in line or "Computer Science" in line for line in profile.education)


def test_spaced_email_is_recovered():
    text = "Manav Shah\nmanav.shah @ gmail.com\nSkills\nPython\n"
    parsed = parse_resume(text)
    parsed["source_text"] = text
    profile = build_candidate_profile(parsed)
    assert profile.candidate_details.name == "Manav Shah"
    assert "manav.shah@gmail.com" in profile.candidate_details.emails


def test_institution_header_is_not_used_as_candidate_name():
    text = (
        "State Technical University\n"
        "Name: Anita Desai\n"
        "Email: anita.desai@example.com\n"
        "Education\n"
        "B.E. Computer Engineering\n"
        "State Technical University\n"
        "CGPA: 8.21 / 10\n"
        "Skills\nPython\n"
    )
    parsed = parse_resume(text)
    parsed["source_text"] = text
    profile = build_candidate_profile(parsed)
    assert profile.candidate_details.name == "Anita Desai"
    assert "anita.desai@example.com" in profile.candidate_details.emails
    joined = " ".join(profile.education)
    assert "B.E." in joined or "Computer Engineering" in joined
    assert "State Technical University" in joined
    assert "8.21" in joined


def test_education_groups_course_score_and_board_percentage():
    text = (
        "Rahul Verma\n"
        "rahul.verma@example.com\n"
        "Education\n"
        "Bachelor of Science in Physics\n"
        "Northridge State University\n"
        "CGPA 8.4\n"
        "H.S.C.\n"
        "City Public College\n"
        "Percentage: 82.5%\n"
        "Skills\nPython\n"
    )
    parsed = parse_resume(text)
    parsed["source_text"] = text
    profile = build_candidate_profile(parsed)
    assert profile.candidate_details.name == "Rahul Verma"
    assert any("Physics" in line and "8.4" in line for line in profile.education)
    assert any(
        ("H.S.C" in line or "HSC" in line.upper() or "H.S.C." in line)
        and ("82.5" in line or "College" in line)
        for line in profile.education
    )


def test_dotted_degree_abbreviation_is_extracted_without_heading():
    text = (
        "Meera Iyer\n"
        "meera.iyer@example.com\n"
        "Skills\nPython, SQL\n"
        "B.E.\n"
        "Information Technology\n"
        "National Institute of Applied Sciences\n"
        "CGPA: 7.9\n"
    )
    parsed = parse_resume(text)
    parsed["source_text"] = text
    parsed["sections"] = [
        section
        for section in parsed["sections"]
        if "education" not in str(section.get("heading", "")).casefold()
    ]
    profile = build_candidate_profile(parsed)
    joined = " ".join(profile.education)
    assert "B.E." in joined
    assert "Information Technology" in joined
    assert "7.9" in joined


def test_section_title_is_not_used_as_candidate_name():
    text = (
        "Key Data Science Projects\n"
        "Aarav Kulkarni\n"
        "aarav.kulkarni@example.com\n"
        "Experience\n"
        "## AI Engineer\n"
        "Stewart Title, Navi Mumbai\n"
        "Sept 2025 - Present\n"
        "Building LLM document pipelines.\n"
        "Python Developer\n"
        "Bright Labs\n"
        "Mar 2021 - May 2023\n"
        "Built FastAPI services.\n"
        "Education\n"
        "Bachelor of Engineering | State Technical University | Jun '17 - May '20\n"
        "Diploma in Engineering | State Board | Jun '14 May '17\n"
    )
    parsed = parse_resume(text)
    parsed["source_text"] = text
    profile = build_candidate_profile(parsed)
    assert profile.candidate_details.name == "Aarav Kulkarni"
    assert any("Bachelor of Engineering" in line for line in profile.education)
    assert any("Diploma" in line for line in profile.education)
    roles = " ".join(f"{entry.role} {entry.company}" for entry in profile.experience_entries)
    assert "Stewart" in roles
    assert "Bright Labs" in roles
    assert not any(entry.role.startswith("#") for entry in profile.experience_entries)
    assert profile.total_experience_years and profile.total_experience_years >= 3


def test_education_under_degree_heading_with_dates_is_extracted():
    text = (
        "Aarav Kulkarni\n"
        "aarav.kulkarni@example.com\n"
        "Experience\n"
        "AI Engineer\nStewart Title\nSept 2025 - Present\n"
        "Education\n"
        "Bachelor of Engineering\n"
        "Jun '17 - May '20\n"
        "State Technical University\n"
        "Diploma in Engineering\n"
        "Jun '14 May '17\n"
        "State Board of Technical Education\n"
    )
    parsed = parse_resume(text)
    parsed["source_text"] = text
    profile = build_candidate_profile(parsed)
    joined = " ".join(profile.education)
    assert "Bachelor of Engineering" in joined
    assert "State Technical University" in joined
    assert "Diploma" in joined


def test_project_bullets_are_not_treated_as_education():
    text = (
        "Aarav Kulkarni\n"
        "aarav.kulkarni@example.com\n"
        "Education\n"
        "Bachelor of Engineering\n"
        "State Technical University\n"
        "Jun '17 - May '20\n"
        "Key Data Science Projects\n"
        "Developed an automated hospital bill classification system using fine-tuned "
        "BioMed-RoBERTa, achieving 96% accuracy in categorizing documents such as summary bills.\n"
        "Designed an NLP-based non-medical expense detection module using PhraseMatcher.\n"
        "Skills\nPython\n"
    )
    parsed = parse_resume(text)
    parsed["source_text"] = text
    profile = build_candidate_profile(parsed)
    joined = " ".join(profile.education)
    assert "Bachelor of Engineering" in joined
    assert "State Technical University" in joined
    assert "hospital bill" not in joined.casefold()
    assert "PhraseMatcher" not in joined
    assert "96%" not in joined

    headings = [section["heading"].casefold() for section in parsed["sections"]]
    assert any("project" in heading for heading in headings)


def test_collapsed_project_sentence_is_not_education():
    text = (
        "Meera Iyer\n"
        "meera.iyer@example.com\n"
        "Education\n"
        "Bachelor of Engineering | State Technical University | Jun '17 - May '20 | "
        "Developed an automated hospital bill classification system achieving 96% accuracy.\n"
        "Skills\nPython\n"
    )
    parsed = parse_resume(text)
    parsed["source_text"] = text
    profile = build_candidate_profile(parsed)
    joined = " ".join(profile.education)
    assert "Bachelor of Engineering" in joined
    assert "State Technical University" in joined
    assert "hospital bill" not in joined.casefold()
    assert "96%" not in joined


def test_two_column_education_is_taken_from_following_section_prefix():
    text = (
        "Candidate Name\n"
        "candidate@example.com\n"
        "SKILLS\n"
        "SUMMARY\nAI engineer.\n"
        "EDUCATION\n"
        "WORK EXPERIENCE\n"
        "Bachelor Of Computer Science (July 2020-june 2023)\n"
        "Example State University\n"
        "CGPA: 9.53\n"
        "Programming Languages: Python, SQL, FastAPI\n"
        "Machine Learning: Regression, Classification, SVM\n"
        "Sept 2025 - Present\n"
        "Engineered document pipelines.\n"
        "PROJECTS\n"
        "Developed an automated hospital bill classification system using fine-tuned "
        "models, achieving 96% accuracy.\n"
        "Designed an NLP module validating entities against expense master data.\n"
    )
    parsed = parse_resume(text)
    parsed["source_text"] = text
    profile = build_candidate_profile(parsed)
    joined = " ".join(profile.education)
    assert "Bachelor Of Computer Science" in joined
    assert "Example State University" in joined
    assert "9.53" in joined
    assert "Programming Languages" not in joined
    assert "hospital bill" not in joined.casefold()
    assert "master data" not in joined.casefold()
