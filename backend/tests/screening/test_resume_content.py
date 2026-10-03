from agents.screening_agent.utils.resume_content import (
    flatten_section_items,
    get_canonical_section_text,
    prepare_resume_for_ats,
)


def test_raw_text_is_not_combined_with_items():
    section = {
        "section_id": "key_skills",
        "heading": "KEY SKILLS",
        "content_type": "list",
        "items": [
            "Python",
            "FastAPI",
            "PyTorch",
        ],
        "raw_text": "- Python\n- FastAPI\n- PyTorch",
    }

    result = get_canonical_section_text(section)

    assert result.lower().count("python") == 1
    assert result.lower().count("fastapi") == 1
    assert result.lower().count("pytorch") == 1


def test_items_are_used_when_raw_text_is_empty():
    section = {
        "section_id": "key_skills",
        "heading": "KEY SKILLS",
        "content_type": "list",
        "items": [
            "Python",
            "FastAPI",
            "PyTorch",
        ],
        "raw_text": "",
    }

    result = get_canonical_section_text(section)

    assert result == "Python\nFastAPI\nPyTorch"


def test_processing_copy_does_not_modify_original_resume():
    parsed_resume = {
        "sections": [
            {
                "section_id": "key_skills",
                "heading": "KEY SKILLS",
                "content_type": "list",
                "items": [
                    "Python",
                    "FastAPI",
                ],
                "raw_text": "- Python\n- FastAPI",
            }
        ],
        "extraction_method": "rule_based_fallback",
    }

    processed_resume = prepare_resume_for_ats(parsed_resume)

    original_section = parsed_resume["sections"][0]
    processed_section = processed_resume["sections"][0]

    # Original extraction response remains unchanged.
    assert original_section["items"] == [
        "Python",
        "FastAPI",
    ]

    # Processing copy has only one content representation.
    assert processed_section["raw_text"] == "- Python\n- FastAPI"
    assert processed_section["items"] == []


def test_nested_table_items_are_converted_to_text():
    section = {
        "section_id": "education",
        "heading": "EDUCATION",
        "content_type": "table",
        "items": [
            [
                "MCA",
                "AIMIT, Mangalore",
            ],
            [
                "CGPA: 7.87",
                "2023-2025",
            ],
        ],
        "raw_text": "",
    }

    result = get_canonical_section_text(section)

    assert "MCA | AIMIT, Mangalore" in result
    assert "CGPA: 7.87 | 2023-2025" in result


def test_duplicate_items_are_removed():
    section = {
        "section_id": "key_skills",
        "heading": "KEY SKILLS",
        "content_type": "list",
        "items": [
            "Python",
            "python",
            " Python ",
            "FastAPI",
        ],
        "raw_text": "",
    }

    result = get_canonical_section_text(section)

    assert result.lower().count("python") == 1
    assert result.lower().count("fastapi") == 1


def test_dictionary_items_are_supported():
    section = {
        "section_id": "contact_information",
        "heading": "Contact Information",
        "content_type": "key_value",
        "items": {
            "Email": "candidate@example.com",
            "Phone": "+91 9876543210",
        },
        "raw_text": "",
    }

    result = get_canonical_section_text(section)

    assert "Email: candidate@example.com" in result
    assert "Phone: +91 9876543210" in result


def test_flatten_section_items_preserves_separate_list_entries():
    result = flatten_section_items(
        [
            "Python",
            "FastAPI",
            "PostgreSQL",
        ]
    )

    assert result == [
        "Python",
        "FastAPI",
        "PostgreSQL",
    ]