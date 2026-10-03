from agents.screening_agent.schemas.resume import ParsedResume
from agents.screening_agent.services.resume_parser import parse_resume


def test_existing_rule_based_resume_contract_is_preserved():
    parsed = parse_resume("Asha Patil\nasha@example.com\n\nSKILLS\nPython\nFastAPI")
    validated = ParsedResume.model_validate(parsed)
    assert validated.sections
    assert validated.extraction_method == "rule_based_fallback"


def test_role_and_company_lines_are_not_misclassified_as_sections():
    from agents.screening_agent.services.section_detector import detect_sections

    text = (
        "Sahil Bhor\nsahil@example.com\nSoftware Engineer\nABC Technologies\n"
        "Jan 2023 - Present\nBuilt APIs\nTECHNICAL SKILLS\nPython, FastAPI"
    )
    sections = detect_sections(text)
    assert [section["heading"] for section in sections] == [
        "Header",
        "TECHNICAL SKILLS",
    ]
    assert "ABC Technologies" in sections[0]["body"]


def test_image_placeholder_is_not_used_as_candidate_name():
    from agents.screening_agent.services.resume_profile_service import build_candidate_profile

    parsed = {
        "sections": [
            {
                "section_id": "contact_information",
                "heading": "Contact Information",
                "heading_source": "inferred",
                "order": 0,
                "content_type": "text",
                "items": [],
                "raw_text": "<!-- image -->\nRavi Molake\nravi@example.com",
            }
        ]
    }

    profile = build_candidate_profile(parsed)
    assert profile.candidate_details.name == "Ravi Molake"


def test_source_reconciliation_preserves_text_omitted_by_ai():
    from agents.screening_agent.services.ai_parser import _reconcile_with_source

    source = "Ravi Molake\nravi@example.com\n\nSKILLS\nPython\nFastAPI"
    ai = {
        "sections": [
            {
                "heading": "Contact Information",
                "raw_text": "Ravi Molake\nravi@example.com",
                "items": [],
                "content_type": "text",
            }
        ]
    }

    reconciled = _reconcile_with_source(ai, source)
    assert reconciled["source_text"] == source
    assert any("Python" in section["raw_text"] for section in reconciled["sections"])


def test_docling_collapsed_markdown_table_recovers_section_boundaries():
    source = (
        "# Ravi Molake\n\n"
        "ravi.molake@example.com | +91 98765 43210 | Pune, India\n\n"
        "| SKILLS  Python FastAPI PostgreSQL Docker  CERTIFICATIONS  AWS Cloud Practitioner   "
        "| PROFESSIONAL EXPERIENCE  Python Developer &#124; Acme Systems &#124; Jan 2023 - Present  "
        "• Built FastAPI services. • Improved PostgreSQL query performance.  "
        "PROJECTS  Resume Screening ATS — Python, FastAPI, NLP  "
        "EDUCATION  BBA Computer Applications, SPPU, 2022   |\n"
        "|----------------|----------------|"
    )

    parsed = parse_resume(source)
    headings = [section["heading"] for section in parsed["sections"]]

    assert headings == [
        "Contact Information",
        "SKILLS",
        "CERTIFICATIONS",
        "PROFESSIONAL EXPERIENCE",
        "PROJECTS",
        "EDUCATION",
    ]
    experience = next(
        section
        for section in parsed["sections"]
        if section["heading"] == "PROFESSIONAL EXPERIENCE"
    )
    assert (
        "Python Developer | Acme Systems | Jan 2023 - Present" in experience["raw_text"]
    )
    assert "• Built FastAPI services." in experience["raw_text"]


def test_short_uppercase_skill_acronyms_are_not_section_headings():
    from agents.screening_agent.services.section_detector import detect_sections

    sections = detect_sections(
        "Anita Sharma\nanita@example.com\nSKILLS\nPython\nSQL\nAWS\nNLP\n"
        "EXPERIENCE\nBackend Developer\n2021 - 2024"
    )

    assert [section["heading"] for section in sections] == [
        "Header",
        "SKILLS",
        "EXPERIENCE",
    ]
    skills = next(section for section in sections if section["heading"] == "SKILLS")
    assert "SQL" in skills["body"]
    assert "AWS" in skills["body"]
    assert "NLP" in skills["body"]


def test_profile_section_heading_is_not_used_as_candidate_name():
    from agents.screening_agent.services.resume_profile_service import build_candidate_profile

    parsed = {
        "source_text": "Suraj Sharma\nsuraj@example.com\n\nSKILLS\nPython\nSQL",
        "sections": [
            {
                "section_id": "skills",
                "heading": "PROFILE",
                "heading_source": "original",
                "order": 0,
                "content_type": "list",
                "items": ["Python", "FastAPI"],
                "raw_text": "Python\nFastAPI",
            }
        ],
    }
    profile = build_candidate_profile(parsed)
    assert profile.candidate_details.name == "Suraj Sharma"
    assert profile.candidate_details.emails == ["suraj@example.com"]


def test_skills_section_heading_is_not_used_as_candidate_name():
    from agents.screening_agent.services.resume_profile_service import build_candidate_profile

    parsed = {
        "source_text": "Anita Sharma\nanita@example.com\nSKILLS\nPython",
        "sections": [
            {
                "section_id": "skills",
                "heading": "SKILLS",
                "heading_source": "original",
                "order": 0,
                "content_type": "list",
                "items": ["Python"],
                "raw_text": "Python",
            }
        ],
    }
    profile = build_candidate_profile(parsed)
    assert profile.candidate_details.name == "Anita Sharma"
    assert profile.candidate_details.emails == ["anita@example.com"]


def test_email_is_found_outside_contact_section():
    from agents.screening_agent.services.resume_profile_service import build_candidate_profile

    parsed = {
        "source_text": "Ravi Molake\nravi@example.com\n\nSKILLS\nPython",
        "sections": [
            {
                "section_id": "skills",
                "heading": "SKILLS",
                "heading_source": "original",
                "order": 0,
                "content_type": "list",
                "items": ["Python"],
                "raw_text": "Python",
            }
        ],
    }
    profile = build_candidate_profile(parsed)
    assert profile.candidate_details.emails == ["ravi@example.com"]


def test_key_value_contact_section_extracts_name_and_email():
    from agents.screening_agent.services.resume_profile_service import build_candidate_profile

    parsed = {
        "sections": [
            {
                "section_id": "contact_information",
                "heading": "Contact Information",
                "heading_source": "inferred",
                "order": 0,
                "content_type": "key_value",
                "items": ["Name: Asha Patil", "Email: asha@example.com"],
                "raw_text": "Name: Asha Patil\nEmail: asha@example.com",
            }
        ]
    }
    profile = build_candidate_profile(parsed)
    assert profile.candidate_details.name == "Asha Patil"
    assert profile.candidate_details.emails == ["asha@example.com"]


def test_role_line_before_name_still_extracts_candidate_name():
    from agents.screening_agent.services.resume_profile_service import build_candidate_profile

    parsed = {
        "source_text": (
            "Software Engineer\nSahil Bhor\nsahil@example.com\nTECHNICAL SKILLS\nPython"
        ),
        "sections": [
            {
                "section_id": "contact_information",
                "heading": "Contact Information",
                "heading_source": "inferred",
                "order": 0,
                "content_type": "text",
                "items": [],
                "raw_text": "Software Engineer\nSahil Bhor\nsahil@example.com",
            }
        ],
    }
    profile = build_candidate_profile(parsed)
    assert profile.candidate_details.name == "Sahil Bhor"
    assert profile.candidate_details.emails == ["sahil@example.com"]


def test_detected_contacts_fallback_when_header_text_is_sparse():
    from agents.screening_agent.services.resume_profile_service import build_candidate_profile

    parsed = {
        "sections": [
            {
                "section_id": "contact_information",
                "heading": "Contact Information",
                "heading_source": "inferred",
                "order": 0,
                "content_type": "text",
                "items": [],
                "raw_text": "Ravi Molake",
                "detected_contacts": {
                    "emails": ["ravi@example.com"],
                    "phones": ["+91 98765 43210"],
                    "links": ["linkedin.com/in/ravi"],
                },
            }
        ]
    }
    profile = build_candidate_profile(parsed)
    assert profile.candidate_details.name == "Ravi Molake"
    assert profile.candidate_details.emails == ["ravi@example.com"]


def test_spaced_letter_name_is_normalized_for_suraj_sharma_resume():
    from agents.screening_agent.services.resume_profile_service import build_candidate_profile

    parsed = {
        "source_text": (
            "## S U R A J   S H A R M A\n\n"
            "BUSINESS SOLUTION ANALYST | DATA ANALYTICS\n\n"
            "## CONTACT\n\n"
            "+91- 9307288839 / 8554058726\n"
            "surajsharmacp94@gmail.com / surajsharmacp2411@gmail.com\n"
        ),
        "sections": [
            {
                "section_id": "contact_information",
                "heading": "Contact Information",
                "heading_source": "inferred",
                "order": 0,
                "content_type": "key_value",
                "items": [
                    {"key": "Phone", "value": "+91- 9307288839 / 8554058726"},
                    {
                        "key": "Email",
                        "value": "surajsharmacp94@gmail.com / surajsharmacp2411@gmail.com",
                    },
                    {"key": "Location", "value": "Pune, Maharashtra"},
                ],
                "raw_text": (
                    "## S U R A J   S H A R M A\n"
                    "BUSINESS SOLUTION ANALYST | DATA ANALYTICS | REPORTING"
                ),
                "detected_contacts": {
                    "emails": [
                        "surajsharmacp94@gmail.com",
                        "surajsharmacp2411@gmail.com",
                    ],
                    "phones": ["+91- 9307288839", "8554058726"],
                    "links": [],
                },
            }
        ],
    }
    profile = build_candidate_profile(parsed)
    assert profile.candidate_details.name == "Suraj Sharma"
    assert "surajsharmacp94@gmail.com" in profile.candidate_details.emails
    assert "surajsharmacp2411@gmail.com" in profile.candidate_details.emails


def test_spaced_letter_name_is_normalized_for_suraj_sharma_resume():
    from agents.screening_agent.services.resume_profile_service import build_candidate_profile

    parsed = {
        "source_text": (
            "## S U R A J   S H A R M A\n\n"
            "BUSINESS SOLUTION ANALYST | DATA ANALYTICS\n\n"
            "## CONTACT\n\n"
            "+91- 9307288839 / 8554058726\n"
            "surajsharmacp94@gmail.com / surajsharmacp2411@gmail.com\n"
        ),
        "sections": [
            {
                "section_id": "contact_information",
                "heading": "Contact Information",
                "heading_source": "inferred",
                "order": 0,
                "content_type": "key_value",
                "items": [
                    {"key": "Phone", "value": "+91- 9307288839 / 8554058726"},
                    {
                        "key": "Email",
                        "value": "surajsharmacp94@gmail.com / surajsharmacp2411@gmail.com",
                    },
                    {"key": "Location", "value": "Pune, Maharashtra"},
                ],
                "raw_text": (
                    "## S U R A J   S H A R M A\n"
                    "BUSINESS SOLUTION ANALYST | DATA ANALYTICS | REPORTING"
                ),
                "detected_contacts": {
                    "emails": [
                        "surajsharmacp94@gmail.com",
                        "surajsharmacp2411@gmail.com",
                    ],
                    "phones": ["+91- 9307288839", "8554058726"],
                    "links": [],
                },
            }
        ],
    }
    profile = build_candidate_profile(parsed)
    assert profile.candidate_details.name == "Suraj Sharma"
    assert "surajsharmacp94@gmail.com" in profile.candidate_details.emails
    assert "surajsharmacp2411@gmail.com" in profile.candidate_details.emails


def test_spaced_letter_name_is_normalized_for_suraj_sharma_resume():
    from agents.screening_agent.services.resume_profile_service import build_candidate_profile

    parsed = {
        "source_text": (
            "## S U R A J   S H A R M A\n\n"
            "BUSINESS SOLUTION ANALYST | DATA ANALYTICS\n\n"
            "## CONTACT\n\n"
            "+91- 9307288839 / 8554058726\n"
            "surajsharmacp94@gmail.com / surajsharmacp2411@gmail.com\n"
        ),
        "sections": [
            {
                "section_id": "contact_information",
                "heading": "Contact Information",
                "heading_source": "inferred",
                "order": 0,
                "content_type": "key_value",
                "items": [
                    {"key": "Phone", "value": "+91- 9307288839 / 8554058726"},
                    {
                        "key": "Email",
                        "value": "surajsharmacp94@gmail.com / surajsharmacp2411@gmail.com",
                    },
                    {"key": "Location", "value": "Pune, Maharashtra"},
                ],
                "raw_text": (
                    "## S U R A J   S H A R M A\n"
                    "BUSINESS SOLUTION ANALYST | DATA ANALYTICS | REPORTING"
                ),
                "detected_contacts": {
                    "emails": [
                        "surajsharmacp94@gmail.com",
                        "surajsharmacp2411@gmail.com",
                    ],
                    "phones": ["+91- 9307288839", "8554058726"],
                    "links": [],
                },
            }
        ],
    }
    profile = build_candidate_profile(parsed)
    assert profile.candidate_details.name == "Suraj Sharma"
    assert "surajsharmacp94@gmail.com" in profile.candidate_details.emails
    assert "surajsharmacp2411@gmail.com" in profile.candidate_details.emails
