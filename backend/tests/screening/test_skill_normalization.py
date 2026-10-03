from agents.screening_agent.utils.skill_normalizer import find_known_skills, normalize_skill, normalize_skills


def test_common_aliases_are_normalized():
    assert normalize_skill("python3") == "Python"
    assert normalize_skill("ReactJS") == "React"
    assert normalize_skill("NodeJS") == "Node.js"
    assert normalize_skill("Postgres") == "PostgreSQL"
    assert normalize_skill("GenAI") == "Generative AI"
    assert normalize_skill("REST API Development") == "REST API"


def test_duplicates_are_removed():
    assert normalize_skills(["Python", "python3", "PYTHON"]) == ["Python"]


def test_unrelated_skills_do_not_collide():
    skills = {item["normalized"] for item in find_known_skills("Java and JavaScript with C++")}
    assert "Java" in skills
    assert "JavaScript" in skills
    assert "C++" in skills
    assert "C" not in skills


def test_generic_words_do_not_create_framework_skills():
    skills = {item["normalized"] for item in find_known_skills("Able to express ideas clearly and work on a node in a graph.")}
    assert "Express.js" not in skills
    assert "Node.js" not in skills
