from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SkillDefinition:
    canonical: str
    category: str
    aliases: tuple[str, ...]


SKILL_DEFINITIONS: tuple[SkillDefinition, ...] = (
    SkillDefinition("Python", "programming_languages", ("python", "python3", "py")),
    SkillDefinition("Java", "programming_languages", ("java",)),
    SkillDefinition("JavaScript", "programming_languages", ("javascript", "java script", "js", "es6")),
    SkillDefinition("TypeScript", "programming_languages", ("typescript", "type script", "ts")),
    SkillDefinition("C", "programming_languages", ("c language", "ansi c")),
    SkillDefinition("C++", "programming_languages", ("c++", "cpp")),
    SkillDefinition("C#", "programming_languages", ("c#", "c sharp")),
    SkillDefinition("PHP", "programming_languages", ("php",)),
    SkillDefinition("Go", "programming_languages", ("golang", "go language")),
    SkillDefinition("R", "programming_languages", ("r programming", "r language")),
    SkillDefinition("Kotlin", "programming_languages", ("kotlin",)),
    SkillDefinition("Swift", "programming_languages", ("swift",)),
    SkillDefinition("SQL", "programming_languages", ("sql", "structured query language")),
    SkillDefinition("HTML", "web_technologies", ("html", "html5")),
    SkillDefinition("CSS", "web_technologies", ("css", "css3")),
    SkillDefinition("React", "frameworks_libraries", ("react", "react.js", "reactjs")),
    SkillDefinition("React Native", "frameworks_libraries", ("react native", "react-native")),
    SkillDefinition("Angular", "frameworks_libraries", ("angular", "angularjs", "angular.js")),
    SkillDefinition("Vue.js", "frameworks_libraries", ("vue", "vue.js", "vuejs")),
    SkillDefinition("Node.js", "frameworks_libraries", ("node.js", "nodejs", "node js")),
    SkillDefinition("Express.js", "frameworks_libraries", ("express.js", "expressjs", "express js")),
    SkillDefinition(
        "FastAPI",
        "frameworks_libraries",
        ("fastapi", "fast api", "asgi", "asgi framework"),
    ),
    SkillDefinition("Django", "frameworks_libraries", ("django",)),
    SkillDefinition("Flask", "frameworks_libraries", ("flask",)),
    SkillDefinition("Spring Boot", "frameworks_libraries", ("spring boot", "springboot")),
    SkillDefinition(".NET", "frameworks_libraries", (".net", "dotnet", "asp.net", "asp net")),
    SkillDefinition("Next.js", "frameworks_libraries", ("next.js", "nextjs", "next js")),
    SkillDefinition("Bootstrap", "frameworks_libraries", ("bootstrap",)),
    SkillDefinition("Tailwind CSS", "frameworks_libraries", ("tailwind", "tailwind css")),
    SkillDefinition(
        "PostgreSQL",
        "databases",
        (
            "postgresql",
            "postgres",
            "postgre sql",
            "relational database",
            "relational databases",
            "relational database management systems",
            "rdbms",
        ),
    ),
    SkillDefinition("MySQL", "databases", ("mysql", "my sql")),
    SkillDefinition("SQLite", "databases", ("sqlite",)),
    SkillDefinition("MongoDB", "databases", ("mongodb", "mongo db", "mongo")),
    SkillDefinition("Oracle Database", "databases", ("oracle database", "oracle db")),
    SkillDefinition("Microsoft SQL Server", "databases", ("sql server", "mssql", "microsoft sql server")),
    SkillDefinition("Redis", "databases", ("redis",)),
    SkillDefinition("Elasticsearch", "databases", ("elasticsearch", "elastic search")),
    SkillDefinition("AWS", "cloud_platforms", ("aws", "amazon web services")),
    SkillDefinition("Microsoft Azure", "cloud_platforms", ("azure", "microsoft azure")),
    SkillDefinition("Google Cloud Platform", "cloud_platforms", ("gcp", "google cloud", "google cloud platform")),
    SkillDefinition(
        "Docker",
        "devops_tools",
        ("docker", "containerization", "containers", "containerized"),
    ),
    SkillDefinition("Kubernetes", "devops_tools", ("kubernetes", "k8s")),
    SkillDefinition(
        "Git",
        "devops_tools",
        (
            "git",
            "version control",
            "version control systems",
            "version control system",
            "vcs",
        ),
    ),
    SkillDefinition("GitHub", "devops_tools", ("github",)),
    SkillDefinition("GitLab", "devops_tools", ("gitlab",)),
    SkillDefinition("Jenkins", "devops_tools", ("jenkins",)),
    SkillDefinition("Terraform", "devops_tools", ("terraform",)),
    SkillDefinition("Ansible", "devops_tools", ("ansible",)),
    SkillDefinition(
        "CI/CD",
        "devops_tools",
        ("ci/cd", "cicd", "continuous integration", "continuous deployment"),
    ),
    SkillDefinition("Linux", "operating_systems", ("linux", "ubuntu", "unix")),
    SkillDefinition("Windows", "operating_systems", ("windows",)),
    SkillDefinition(
        "JWT",
        "security",
        (
            "jwt",
            "jwt authentication",
            "bearer token",
            "bearer tokens",
            "json web token",
            "json web tokens",
            "token-based security",
            "token based security",
        ),
    ),
    SkillDefinition(
        "Async Programming",
        "domain_skills",
        (
            "async programming",
            "asynchronous programming",
            "async/await",
            "non-blocking",
            "non blocking",
            "event-driven programming",
            "event driven programming",
        ),
    ),
    SkillDefinition(
        "Dependency Injection",
        "domain_skills",
        ("dependency injection", "di pattern"),
    ),
    SkillDefinition(
        "API Documentation",
        "domain_skills",
        ("api documentation", "openapi", "swagger"),
    ),
    SkillDefinition("Pandas", "data_ai", ("pandas",)),
    SkillDefinition("NumPy", "data_ai", ("numpy", "num py")),
    SkillDefinition("SciPy", "data_ai", ("scipy",)),
    SkillDefinition("scikit-learn", "data_ai", ("scikit-learn", "sklearn", "scikit learn")),
    SkillDefinition("TensorFlow", "data_ai", ("tensorflow", "tensor flow")),
    SkillDefinition("PyTorch", "data_ai", ("pytorch",)),
    SkillDefinition("Keras", "data_ai", ("keras",)),
    SkillDefinition("OpenCV", "data_ai", ("opencv", "open cv")),
    SkillDefinition("Machine Learning", "data_ai", ("machine learning", "ml")),
    SkillDefinition("Deep Learning", "data_ai", ("deep learning", "dl")),
    SkillDefinition("Natural Language Processing", "data_ai", ("natural language processing", "nlp")),
    SkillDefinition("Computer Vision", "data_ai", ("computer vision",)),
    SkillDefinition(
        "Artificial Intelligence",
        "data_ai",
        ("artificial intelligence", "ai"),
    ),
    SkillDefinition("Generative AI", "data_ai", ("generative ai", "genai", "gen ai")),
    SkillDefinition(
        "RAG",
        "data_ai",
        (
            "rag",
            "retrieval augmented generation",
            "retrieval-augmented generation",
            "retrieval augmented generation (rag)",
        ),
    ),
    SkillDefinition(
        "Prompt Engineering",
        "data_ai",
        ("prompt engineering", "prompt-engineering"),
    ),
    SkillDefinition("Large Language Models", "data_ai", ("large language models", "large language model", "llm", "llms")),
    SkillDefinition("JSON", "web_technologies", ("json",)),
    SkillDefinition("XML", "web_technologies", ("xml",)),
    SkillDefinition(
        "Azure OpenAI",
        "cloud_platforms",
        ("azure openai", "azure open ai"),
    ),
    SkillDefinition("Data Science", "domain_skills", ("data science",)),
    SkillDefinition("Data Analysis", "domain_skills", ("data analysis", "data analytics")),
    SkillDefinition("Data Engineering", "domain_skills", ("data engineering",)),
    SkillDefinition("Business Intelligence", "domain_skills", ("business intelligence", "bi")),
    SkillDefinition("ETL", "domain_skills", ("etl", "extract transform load")),
    SkillDefinition(
        "REST API",
        "domain_skills",
        (
            "rest api",
            "rest apis",
            "restful api",
            "restful apis",
            "restful services",
            "rest services",
            "restful web services",
            "rest api development",
            "rest api design",
            "api development",
            "backend api",
            "backend apis",
            "http endpoints",
            "http services",
        ),
    ),
    SkillDefinition(
        "Microservices",
        "domain_skills",
        (
            "microservices",
            "microservice architecture",
            "service-oriented backend",
            "service oriented backend",
            "service-oriented",
        ),
    ),
    SkillDefinition(
        "Object-Oriented Programming",
        "domain_skills",
        (
            "object oriented programming",
            "object-oriented programming",
            "oop",
            "solid principles",
        ),
    ),
    SkillDefinition("Data Structures", "domain_skills", ("data structures", "dsa")),
    SkillDefinition("Algorithms", "domain_skills", ("algorithms",)),
    SkillDefinition("Agile", "project_management", ("agile", "agile methodology")),
    SkillDefinition("Scrum", "project_management", ("scrum",)),
    SkillDefinition("Jira", "project_management", ("jira",)),
    SkillDefinition("Project Management", "project_management", ("project management",)),
    SkillDefinition("Unit Testing", "testing", ("unit testing", "unit tests")),
    SkillDefinition("Pytest", "testing", ("pytest",)),
    SkillDefinition("Selenium", "testing", ("selenium",)),
    SkillDefinition("Postman", "testing", ("postman",)),
    SkillDefinition("API Testing", "testing", ("api testing",)),
    SkillDefinition("Software Testing", "testing", ("software testing",)),
    SkillDefinition("Power BI", "tools", ("power bi", "powerbi")),
    SkillDefinition("Tableau", "tools", ("tableau",)),
    SkillDefinition("Microsoft Excel", "tools", ("microsoft excel", "ms excel", "excel")),
    SkillDefinition("VS Code", "tools", ("visual studio code", "vs code", "vscode")),
    SkillDefinition("Figma", "tools", ("figma",)),
    # HR / people-ops (domain-agnostic screening)
    SkillDefinition(
        "HR Policies and Procedures",
        "human_resources",
        ("hr policies and procedures", "hr policies", "hr procedures", "hr policy"),
    ),
    SkillDefinition(
        "Employee Relations",
        "human_resources",
        ("employee relations", "employee-relations", "er matters"),
    ),
    SkillDefinition(
        "Orientation and Onboarding",
        "human_resources",
        (
            "orientation and onboarding",
            "employee orientation",
            "onboarding",
            "employee onboarding",
        ),
    ),
    SkillDefinition(
        "Recruitment Lifecycle Management",
        "human_resources",
        (
            "recruitment lifecycle management",
            "recruitment lifecycle",
            "talent acquisition",
            "recruitment support",
        ),
    ),
    SkillDefinition(
        "Performance Management",
        "human_resources",
        ("performance management", "performance-management"),
    ),
    SkillDefinition(
        "Training and Employee Development",
        "human_resources",
        (
            "training and employee development",
            "employee development",
            "learning and development",
            "l&d",
            "professional development",
        ),
    ),
    SkillDefinition(
        "Benefits Administration",
        "human_resources",
        ("benefits administration", "employee benefits", "compensation and benefits"),
    ),
    SkillDefinition(
        "HRIS Administration",
        "human_resources",
        (
            "hris administration",
            "hris",
            "hr information systems",
            "hr information system",
            "human resource information system",
        ),
    ),
    SkillDefinition(
        "HR Program and Project Management",
        "human_resources",
        (
            "hr program and project management",
            "hr programs",
            "hr project management",
            "hr projects",
        ),
    ),
    SkillDefinition(
        "Workforce Reporting and Analytics",
        "human_resources",
        (
            "workforce reporting and analytics",
            "workforce reporting",
            "hr reporting",
            "workforce analytics",
            "people analytics",
        ),
    ),
    SkillDefinition(
        "HR Operations",
        "human_resources",
        ("hr operations", "human resources operations", "hr ops"),
    ),
    SkillDefinition(
        "Change Management",
        "human_resources",
        ("change management", "change-management"),
    ),
    SkillDefinition(
        "Organisational Development",
        "human_resources",
        (
            "organisational development",
            "organizational development",
            "org development",
        ),
    ),
    SkillDefinition(
        "Stakeholder Management",
        "human_resources",
        ("stakeholder management", "stakeholder-management"),
    ),
    SkillDefinition(
        "Employee Engagement",
        "human_resources",
        ("employee engagement", "retention and engagement"),
    ),
    SkillDefinition(
        "Labour Compliance",
        "human_resources",
        (
            "labour compliance",
            "labor compliance",
            "employment regulations",
            "hr compliance",
        ),
    ),
    # Marketing / business
    SkillDefinition(
        "Digital Marketing",
        "marketing",
        ("digital marketing", "digital marketing strategy"),
    ),
    SkillDefinition(
        "Marketing Analytics",
        "marketing",
        ("marketing analytics", "marketing analysis"),
    ),
    SkillDefinition("Brand Management", "marketing", ("brand management", "branding")),
    SkillDefinition(
        "Campaign Management",
        "marketing",
        ("campaign management", "marketing campaigns"),
    ),
    SkillDefinition("SEO", "marketing", ("seo", "search engine optimization")),
    SkillDefinition("SEM", "marketing", ("sem", "search engine marketing")),
    SkillDefinition("Content Marketing", "marketing", ("content marketing",)),
    SkillDefinition("Social Media Marketing", "marketing", ("social media marketing", "smm")),
    SkillDefinition("Communication", "soft_skills", ("communication", "communication skills")),
    SkillDefinition("Leadership", "soft_skills", ("leadership",)),
    SkillDefinition("Teamwork", "soft_skills", ("teamwork", "team player", "collaboration")),
    SkillDefinition("Problem Solving", "soft_skills", ("problem solving", "problem-solving")),
    SkillDefinition("Time Management", "soft_skills", ("time management",)),
    SkillDefinition("Critical Thinking", "soft_skills", ("critical thinking",)),
    SkillDefinition("Adaptability", "soft_skills", ("adaptability", "adaptable")),
    SkillDefinition("AWS Certified", "certifications", ("aws certified",)),
    SkillDefinition("Microsoft Certified", "certifications", ("microsoft certified",)),
    SkillDefinition("Google Cloud Certified", "certifications", ("google cloud certified",)),
    SkillDefinition("PMP", "certifications", ("pmp", "project management professional")),
    SkillDefinition("Certified ScrumMaster", "certifications", ("certified scrummaster", "csm certification")),
)


def _key(value: str) -> str:
    value = value.casefold().strip()
    value = value.replace("&", " and ")
    value = re.sub(r"[\s_\-]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" .,:;()[]{}")


# Distinct technologies that must not be treated as interchangeable.
_EXCLUSIVE_FAMILIES: tuple[frozenset[str], ...] = (
    frozenset({"json", "xml"}),
    frozenset({"pandas", "numpy", "scipy", "scikit-learn"}),
    frozenset({"microsoft azure", "azure openai", "aws", "google cloud platform"}),
    frozenset({"fastapi", "flask", "django"}),
    frozenset({"python", "java", "javascript", "typescript", "c++", "c#", "go", "php", "kotlin", "swift"}),
    frozenset({"postgresql", "mysql", "sqlite", "mongodb", "oracle database", "microsoft sql server"}),
)

_PROTECTED_COMPOUNDS = {
    "ci/cd",
    "ci / cd",
    "c++",
    "c#",
    "asp.net",
    "node.js",
    "next.js",
    "vue.js",
    "express.js",
}

_MODIFIER_RE = re.compile(
    r"\s*[\(\[]\s*(?:"
    r"advanced|intermediate|beginner|basic|expert|proficient|"
    r"preferred|required|nice to have|mandatory|optional|plus"
    r")\s*[\)\]]\s*",
    re.I,
)

_COMPOUND_SPLIT_RE = re.compile(
    r"\s*(?:,|;|\||(?:\s/\s)|(?:\s*&\s+))\s*",
    re.I,
)


_ALIAS_TO_DEFINITION: dict[str, SkillDefinition] = {}
for definition in SKILL_DEFINITIONS:
    for alias in (*definition.aliases, definition.canonical):
        _ALIAS_TO_DEFINITION[_key(alias)] = definition


_CATEGORY_PREFIX_RE = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9+.#/& -]{1,40})\s*:\s+",
)


def strip_skill_category_prefix(skill: str) -> str:
    """Turn 'Cloud & DevOps: Containerization' into 'Containerization'."""
    cleaned = re.sub(r"\s+", " ", skill).strip(" \t\r\n,;|•-–—")
    if not cleaned:
        return ""
    stripped = _CATEGORY_PREFIX_RE.sub("", cleaned).strip()
    if stripped and stripped.casefold() != cleaned.casefold():
        return stripped
    if ":" in cleaned:
        tail = cleaned.rsplit(":", 1)[-1].strip()
        if tail:
            return tail
    return cleaned


def strip_skill_modifiers(skill: str) -> tuple[str, bool]:
    """Remove proficiency/priority markers such as (Advanced) or (Preferred)."""
    cleaned = re.sub(r"\s+", " ", skill).strip(" \t\r\n,;|•-–—")
    stripped, count = _MODIFIER_RE.subn(" ", cleaned)
    stripped = re.sub(r"\s+", " ", stripped).strip(" \t\r\n,;|•-–—")
    return stripped or cleaned, count > 0


def _is_protected_compound(skill: str) -> bool:
    return _key(skill) in {_key(item) for item in _PROTECTED_COMPOUNDS}


def _looks_atomic_skill_part(part: str) -> bool:
    cleaned = part.strip(" \t\r\n,;|•-–—")
    if not cleaned or len(cleaned) > 60:
        return False
    if re.search(r"\b(the|this|that|which|with|from|into)\b", cleaned, re.I) and len(cleaned.split()) > 4:
        return False
    return True


def expand_compound_skill(skill: str) -> list[str]:
    """Split 'FastAPI / Flask / Django' or 'Pandas, NumPy' into atomic skills."""
    cleaned, _had_modifier = strip_skill_modifiers(skill)
    cleaned = strip_skill_category_prefix(cleaned)
    if not cleaned:
        return []
    if _is_protected_compound(cleaned):
        return [cleaned]

    placeholder = "CI_CD_TOKEN"
    protected_text = re.sub(r"ci\s*/\s*cd", placeholder, cleaned, flags=re.I)
    parts: list[str] = []
    if _COMPOUND_SPLIT_RE.search(protected_text):
        parts = [part.strip(" .") for part in _COMPOUND_SPLIT_RE.split(protected_text) if part.strip(" .")]
    elif "/" in protected_text:
        slash_parts = [part.strip(" .") for part in re.split(r"/", protected_text) if part.strip(" .")]
        if len(slash_parts) >= 2 and all(_looks_atomic_skill_part(part) for part in slash_parts):
            parts = slash_parts
    else:
        and_parts = [part.strip(" .") for part in re.split(r"\s+and\s+", protected_text, flags=re.I) if part.strip(" .")]
        if len(and_parts) >= 2 and all(
            _ALIAS_TO_DEFINITION.get(_key(part.replace(placeholder, "CI/CD"))) for part in and_parts
        ):
            parts = and_parts

    parts = [part.replace(placeholder, "CI/CD") for part in parts]
    if len(parts) >= 2 and all(_looks_atomic_skill_part(part) for part in parts):
        return parts
    return [cleaned]


def _lookup_canonical(skill: str) -> str:
    cleaned = re.sub(r"\s+", " ", skill).strip(" \t\r\n,;|•-–—")
    if not cleaned:
        return ""
    stripped, _had_modifier = strip_skill_modifiers(cleaned)
    candidates = (
        stripped,
        cleaned,
        strip_skill_category_prefix(stripped),
        strip_skill_category_prefix(cleaned),
    )
    for candidate in candidates:
        if not candidate:
            continue
        definition = _ALIAS_TO_DEFINITION.get(_key(candidate))
        if definition:
            return definition.canonical
    return strip_skill_category_prefix(stripped) or stripped or cleaned


def normalize_skill(skill: str) -> str:
    cleaned = re.sub(r"\s+", " ", skill).strip(" \t\r\n,;|•-–—")
    if not cleaned:
        return ""
    return _lookup_canonical(cleaned)


def skill_had_proficiency_modifier(skill: str) -> bool:
    _stripped, had_modifier = strip_skill_modifiers(skill)
    return had_modifier


def skill_category(skill: str, fallback: str = "other") -> str:
    definition = _ALIAS_TO_DEFINITION.get(_key(normalize_skill(skill) or skill))
    return definition.category if definition else fallback


def skill_search_terms(skill: str) -> list[str]:
    """Canonical name plus aliases used for evidence search."""
    canonical = normalize_skill(skill) or skill
    terms = [canonical, skill]
    definition = _ALIAS_TO_DEFINITION.get(_key(canonical))
    if definition:
        terms.append(definition.canonical)
        terms.extend(definition.aliases)
    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        cleaned = re.sub(r"\s+", " ", str(term)).strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def exclusive_family_members(skill: str) -> frozenset[str] | None:
    key = _key(normalize_skill(skill) or skill)
    for family in _EXCLUSIVE_FAMILIES:
        if key in family:
            return family
    return None


def are_exclusive_distinct_skills(left: str, right: str) -> bool:
    """True when two named skills belong to the same exclusive family and are not aliases."""
    left_key = _key(normalize_skill(left) or left)
    right_key = _key(normalize_skill(right) or right)
    if not left_key or not right_key or left_key == right_key:
        return False
    family = exclusive_family_members(left)
    return bool(family and right_key in family)


def normalize_skills(skills: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for skill in skills:
        for part in expand_compound_skill(skill):
            canonical = normalize_skill(part)
            if canonical and canonical.casefold() not in seen:
                seen.add(canonical.casefold())
                result.append(canonical)
    return result


def _alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    escaped = escaped.replace(r"\ ", r"[\s._\-/]*")
    return re.compile(
        rf"(?<![A-Za-z0-9+#]){escaped}(?![A-Za-z0-9+#])",
        re.IGNORECASE,
    )


_SEARCH_ALIASES: list[tuple[str, SkillDefinition, re.Pattern[str]]] = []
for definition in SKILL_DEFINITIONS:
    aliases = sorted(set((*definition.aliases, definition.canonical)), key=len, reverse=True)
    for alias in aliases:
        # Single-letter / highly ambiguous tokens are only matched via longer aliases.
        if alias.casefold() in {"c", "r", "go", "js", "ts", "py", "bi"}:
            continue
        _SEARCH_ALIASES.append((alias, definition, _alias_pattern(alias)))
_SEARCH_ALIASES.sort(key=lambda item: len(item[0]), reverse=True)


def find_known_skills(text: str) -> list[dict[str, str | int]]:
    matches: list[dict[str, str | int]] = []
    occupied: list[tuple[int, int]] = []

    for _alias, definition, pattern in _SEARCH_ALIASES:
        for match in pattern.finditer(text):
            span = match.span()
            if any(span[0] < end and span[1] > start for start, end in occupied):
                continue
            occupied.append(span)
            matches.append(
                {
                    "raw": match.group(0),
                    "normalized": definition.canonical,
                    "category": definition.category,
                    "start": span[0],
                    "end": span[1],
                }
            )

    return sorted(matches, key=lambda item: int(item["start"]))


# Catalog relationships used for *strong dated skill evidence* only.
# The matching engine treats these as data, not role-specific rules:
# a listed child skill in an employment entry can support the parent skill.
_RELATED_PARENTS: dict[str, tuple[str, ...]] = {
    "FastAPI": ("Python", "REST API"),
    "Flask": ("Python", "REST API"),
    "Django": ("Python", "REST API"),
    "Pytest": ("Python",),
    "Pandas": ("Python",),
    "NumPy": ("Python",),
    "TensorFlow": ("Python", "Machine Learning", "Artificial Intelligence"),
    "PyTorch": ("Python", "Machine Learning", "Artificial Intelligence"),
    "Keras": ("Python", "Machine Learning"),
    "scikit-learn": ("Python", "Machine Learning"),
    "Spring Boot": ("Java",),
    "React": ("JavaScript",),
    "React Native": ("JavaScript",),
    "Angular": ("JavaScript",),
    "Vue.js": ("JavaScript",),
    "Node.js": ("JavaScript",),
    "Express.js": ("JavaScript", "REST API"),
    "Next.js": ("JavaScript", "TypeScript"),
    "Deep Learning": ("Machine Learning", "Artificial Intelligence"),
    "Natural Language Processing": ("Machine Learning", "Artificial Intelligence"),
    "Computer Vision": ("Machine Learning", "Artificial Intelligence"),
    "Generative AI": ("Artificial Intelligence", "Machine Learning"),
    "RAG": ("Generative AI", "Artificial Intelligence", "Natural Language Processing"),
    "Prompt Engineering": ("Generative AI", "Large Language Models"),
    "Large Language Models": ("Generative AI", "Artificial Intelligence"),
    "REST API": (),
    "Azure OpenAI": ("Microsoft Azure", "Generative AI"),
    "HRIS Administration": ("HR Operations",),
    "Employee Relations": ("HR Operations",),
    "Orientation and Onboarding": ("HR Operations",),
}


def _parent_index() -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for child, parents in _RELATED_PARENTS.items():
        child_canonical = normalize_skill(child) or child
        for parent in parents:
            parent_key = _key(normalize_skill(parent) or parent)
            index.setdefault(parent_key, set()).add(child_canonical)
    return index


_SKILLS_IMPLYING_PARENT = _parent_index()


def skills_implying(parent_skill: str) -> set[str]:
    """Catalog skills that provide strong (not exact) evidence of a parent skill."""
    parent = normalize_skill(parent_skill) or parent_skill
    return set(_SKILLS_IMPLYING_PARENT.get(_key(parent), set()))
