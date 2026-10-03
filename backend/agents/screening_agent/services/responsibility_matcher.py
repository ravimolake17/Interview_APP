"""Evidence-based JD responsibility matching (action + object + domain)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from agents.screening_agent.schemas.ats import CandidateProfile, ParsedJD, ResponsibilityMatch
from agents.screening_agent.utils.skill_normalizer import find_known_skills, normalize_skills
from agents.screening_agent.utils.text_utils import dedupe_preserve


ResponsibilityStatus = str  # STRONG_MATCH | PARTIAL_MATCH | WEAK_MATCH | UNSUPPORTED
ResponsibilityPriority = str  # CORE | IMPORTANT | SUPPORTING

_GENERIC = {
    "a", "an", "and", "the", "with", "for", "from", "into", "using", "use",
    "role", "work", "working", "experience", "years", "year", "team",
    "company", "strong", "knowledge", "required", "preferred", "including",
    "such", "other", "related", "ability", "solutions", "solution",
    "applications", "application", "systems", "system", "services", "service",
    "powered", "across", "within", "various", "multiple", "etc", "well",
    "new", "high", "quality", "based", "environment", "environments", "field",
    "duties", "job", "position", "ensure", "able", "highly", "complete",
    "scalable", "end", "end-to-end",
}

# Language-level action families. Not industry-specific technologies.
_BUILD = frozenset({
    "build", "built", "develop", "developed", "implement", "implemented",
    "create", "created", "design", "designed", "engineer", "engineered",
    "write", "wrote", "construct", "constructed",
})
_MAINTAIN = frozenset({
    "maintain", "maintained", "operate", "operated", "support", "supported",
})
_DEPLOY = frozenset({
    "deploy", "deployed", "release", "released", "host", "hosted", "ship", "shipped",
})
_MONITOR = frozenset({
    "monitor", "monitored", "observe", "observability", "track", "tracked",
})
_ANALYZE = frozenset({
    "analyze", "analyse", "analyzed", "analysed", "analytics", "report", "reporting",
})
_MANAGE = frozenset({
    "manage", "managed", "lead", "led", "coordinate", "coordinated",
    "administer", "administered", "handle", "handled",
})
_COLLECT = frozenset({
    "collect", "collected", "gather", "gathered", "ingest", "ingested",
    "extract", "extracted",
})
_TRANSFORM = frozenset({
    "clean", "cleaned", "transform", "transformed", "prepare", "prepared",
    "normalize", "normalization", "preprocess", "preprocessing",
    "validate", "validation", "etl",
})
_INTEGRATE = frozenset({"integrate", "integrated", "integration"})
_TRAIN = frozenset({"train", "trained", "onboard", "onboarding"})
_RECRUIT = frozenset({"recruit", "recruited", "hiring", "hire"})
_AUDIT = frozenset({"audit", "audited", "compliance", "comply"})
_NEGOTIATE = frozenset({"negotiate", "negotiated"})
_FINETUNE = frozenset({"fine-tune", "finetune", "finetuned", "fine-tuned"})
_OPTIMIZE = frozenset({
    "optimize", "optimise", "optimized", "optimised", "optimization", "optimisation",
})

_ACTION_FAMILIES: tuple[frozenset[str], ...] = (
    _BUILD, _MAINTAIN, _DEPLOY, _MONITOR, _ANALYZE, _MANAGE, _COLLECT,
    _TRANSFORM, _INTEGRATE, _TRAIN, _RECRUIT, _AUDIT, _NEGOTIATE, _FINETUNE,
    _OPTIMIZE,
)

# Distinctive actions that must appear (or a close synonym) — related work is not enough.
_DISTINCTIVE_ACTIONS = frozenset({
    "fine-tune", "finetune", "fine-tuned", "finetuned",
    "monitor", "monitored", "monitoring",
    "audit", "audited",
    "negotiate", "negotiated",
})

_MULTIWORD_ACTIONS: tuple[tuple[re.Pattern[str], frozenset[str], frozenset[str]], ...] = (
    (
        re.compile(r"\bfine[\s-]*tun", re.I),
        _FINETUNE,
        frozenset({"fine-tune", "finetune", "fine-tuned", "finetuned"}),
    ),
)

# Meaning families for objects/domains. These are paraphrases, not required tech.
_CHAT_OBJECTS = frozenset({
    "chatbot", "chatbots", "assistant", "assistants", "conversational",
    "bot", "bots", "agent", "agents",
})
_PIPELINE_OBJECTS = frozenset({
    "pipeline", "pipelines", "etl", "ingestion", "ingest",
    "preprocessing", "normalization", "validation", "ocr",
    "processing", "dataset", "datasets",
})
_API_OBJECTS = frozenset({
    "api", "apis", "backend", "microservice", "microservices",
    "endpoint", "endpoints", "gateway",
})
_MODEL_OBJECTS = frozenset({
    "model", "models", "prediction", "classification", "recommendation",
    "forecast", "forecasting", "clustering", "anomaly", "optimisation",
    "optimization",
})
_DEPLOY_OBJECTS = frozenset({
    "deployment", "production", "cloud", "container", "containers",
})
_ONBOARD_OBJECTS = frozenset({"onboard", "onboarding", "orientation"})
_RECRUIT_OBJECTS = frozenset({"recruitment", "recruiting", "hiring", "talent"})
_POLICY_OBJECTS = frozenset({
    "policy", "policies", "procedure", "procedures", "guideline", "guidelines",
})
_WORKFLOW_OBJECTS = frozenset({"workflow", "workflows"})
_DATA_PROCESS_OBJECTS = frozenset({"data"}) | _PIPELINE_OBJECTS
_OBJECT_MODIFIERS = {
    "intelligent", "virtual", "automated", "advanced", "custom",
    "enterprise", "internal", "external", "modern", "robust",
    "ai-powered", "ai", "ml", "end-to-end", "data",
}

_OBJECT_FAMILIES: tuple[frozenset[str], ...] = (
    _CHAT_OBJECTS,
    _PIPELINE_OBJECTS,
    _API_OBJECTS,
    _MODEL_OBJECTS,
    _DEPLOY_OBJECTS,
    _ONBOARD_OBJECTS,
    _RECRUIT_OBJECTS,
    _POLICY_OBJECTS,
    _WORKFLOW_OBJECTS,
)

_SUPPORTING_RE = re.compile(
    r"\b(participate|participating|attend|attending|assist with|help with|"
    r"contribute to|nice to have|as needed|ad hoc|user adoption|"
    r"documentation only)\b",
    re.I,
)

_CREDIT = {
    "STRONG_MATCH": 1.0,
    "PARTIAL_MATCH": 0.7,
    "WEAK_MATCH": 0.3,
    "UNSUPPORTED": 0.0,
}
_PRIORITY_WEIGHT = {
    "CORE": 1.0,
    "IMPORTANT": 0.75,
    "SUPPORTING": 0.4,
}
_STATUS_RANK = {
    "UNSUPPORTED": 0,
    "WEAK_MATCH": 1,
    "PARTIAL_MATCH": 2,
    "STRONG_MATCH": 3,
}


@dataclass
class ParsedResponsibility:
    text: str
    actions: set[str]
    objects: set[str]
    surface_objects: set[str]
    distinctive_actions: set[str]
    catalog_skills: set[str]


def _tokens(text: str) -> set[str]:
    found = re.findall(r"[a-z0-9+#]+(?:[./-][a-z0-9+#]+)*", (text or "").casefold())
    tokens: set[str] = set()
    for raw in found:
        token = raw.strip(".-/")
        if len(token) < 2 or token in _GENERIC:
            continue
        tokens.add(token)
        for part in re.split(r"[./-]", token):
            if len(part) >= 2 and part not in _GENERIC:
                tokens.add(part)
    return tokens


def _family_for(token: str, families: tuple[frozenset[str], ...]) -> frozenset[str] | None:
    key = token.casefold()
    for family in families:
        if key in family:
            return family
    return None


def _expand(tokens: set[str], families: tuple[frozenset[str], ...]) -> set[str]:
    expanded = set(tokens)
    for token in list(tokens):
        family = _family_for(token, families)
        if family:
            expanded.update(family)
    return expanded


def _shared_family_count(left: set[str], right: set[str], families: tuple[frozenset[str], ...]) -> int:
    return sum(1 for family in families if left & family and right & family)


def parse_responsibility(text: str) -> ParsedResponsibility:
    tokens = _tokens(text)
    actions: set[str] = set()
    distinctive: set[str] = set()
    for token in tokens:
        family = _family_for(token, _ACTION_FAMILIES)
        if family:
            actions.update(family)
            if token in _DISTINCTIVE_ACTIONS or family & _DISTINCTIVE_ACTIONS:
                distinctive.update(family & _DISTINCTIVE_ACTIONS)
    for pattern, action_family, distinctive_extra in _MULTIWORD_ACTIONS:
        if pattern.search(text or ""):
            actions.update(action_family)
            distinctive.update(distinctive_extra)

    surface_objects = {token for token in tokens if token not in actions}
    objects = _expand(surface_objects, _OBJECT_FAMILIES)
    dataish = bool(surface_objects & ({"data", "dataset", "datasets"} | _PIPELINE_OBJECTS))
    if dataish and actions & (_COLLECT | _TRANSFORM):
        objects.update(_DATA_PROCESS_OBJECTS)
    catalog = {str(match["normalized"]) for match in find_known_skills(text)}
    return ParsedResponsibility(
        text=text,
        actions=actions,
        objects=objects,
        surface_objects=surface_objects,
        distinctive_actions=distinctive,
        catalog_skills=catalog,
    )


def _snippets(text: str) -> list[str]:
    parts = re.split(r"[\n•|;]+|(?<=[.!?])\s+", text or "")
    snippets = []
    for part in parts:
        cleaned = re.sub(r"\s+", " ", part).strip(" \t-–—*")
        if len(cleaned) >= 8:
            snippets.append(cleaned)
    return snippets


def _priority(
    item: str,
    *,
    index: int,
    total: int,
    required_skills: list[str],
    job_title: str,
) -> str:
    if _SUPPORTING_RE.search(item) and not any(
        skill.casefold() in item.casefold() for skill in required_skills if len(skill) > 2
    ):
        return "SUPPORTING"
    required_hits = sum(1 for skill in required_skills if skill and skill.casefold() in item.casefold())
    title_tokens = _tokens(job_title)
    item_tokens = _tokens(item)
    if required_hits >= 1 or len(title_tokens & item_tokens) >= 2:
        return "CORE"
    if total <= 3 or index < max(2, int(total * 0.45)):
        return "CORE"
    return "IMPORTANT"


def _classify_snippet(
    parsed: ParsedResponsibility,
    snippet: str,
) -> tuple[str, float, list[str]]:
    raw_tokens = _tokens(snippet)
    snippet_tokens = _expand(raw_tokens, _OBJECT_FAMILIES + _ACTION_FAMILIES)
    snippet_skills = {str(match["normalized"]) for match in find_known_skills(snippet)}
    action_hit = bool(parsed.actions & snippet_tokens)
    object_hits = parsed.objects & snippet_tokens
    family_hits = _shared_family_count(parsed.objects, raw_tokens, _OBJECT_FAMILIES)
    skill_hits = parsed.catalog_skills & snippet_skills
    distinctive_hit = bool(parsed.distinctive_actions & snippet_tokens)
    for pattern, _action_family, distinctive_extra in _MULTIWORD_ACTIONS:
        if distinctive_extra & parsed.distinctive_actions and pattern.search(snippet or ""):
            distinctive_hit = True

    evidence_bits = dedupe_preserve(
        [snippet] if (object_hits or skill_hits or action_hit or family_hits) else []
    )

    if parsed.distinctive_actions and not distinctive_hit:
        return "UNSUPPORTED", 0.0, []

    object_signal = max(len(object_hits), family_hits)
    score = 0.0
    if action_hit:
        score += 0.4
    score += min(0.45, 0.2 * object_signal + (0.15 if skill_hits else 0.0))
    if distinctive_hit:
        score += 0.2

    # Specific JD objects (CRM, payroll, etc.) must appear; a generic related
    # action such as "build APIs" must not satisfy an unrelated enterprise object.
    specific_surface = {
        token for token in parsed.surface_objects
        if token not in _GENERIC
        and token not in _OBJECT_MODIFIERS
        and not _family_for(token, _OBJECT_FAMILIES)
    }
    specific_hit = bool(specific_surface & snippet_tokens) or any(
        token in snippet.casefold() for token in specific_surface if len(token) >= 3
    )
    if specific_surface and not specific_hit and not skill_hits:
        if action_hit or object_hits or family_hits:
            return "WEAK_MATCH", min(0.35, score), evidence_bits
        return "UNSUPPORTED", 0.0, []

    if action_hit and (object_signal >= 1 or skill_hits):
        return "STRONG_MATCH", min(1.0, max(0.75, score)), evidence_bits
    if object_signal >= 2 or (object_signal and skill_hits):
        return "PARTIAL_MATCH", min(0.75, max(0.55, score)), evidence_bits
    if object_hits or skill_hits or family_hits:
        return "WEAK_MATCH", min(0.45, max(0.3, score)), evidence_bits
    if action_hit:
        return "WEAK_MATCH", 0.25, evidence_bits
    return "UNSUPPORTED", 0.0, []


def _reason(status: str, parsed: ParsedResponsibility, evidence: list[str]) -> str:
    if status == "UNSUPPORTED":
        if parsed.distinctive_actions:
            return (
                "No resume evidence found for the distinctive action required "
                "by this responsibility."
            )
        return "No resume evidence found for this responsibility."
    shown = evidence[0].rstrip(".") if evidence else ""
    suffix = f' Evidence: "{shown}."' if shown else ""
    if status == "STRONG_MATCH":
        return (
            "Resume demonstrates direct experience covering the action and "
            f"domain of this responsibility.{suffix}"
        )
    if status == "PARTIAL_MATCH":
        return (
            "Resume shows related domain evidence for this responsibility, "
            "but not every stated action/object is fully demonstrated."
            + suffix
        )
    return (
        "Resume contains only limited or indirect evidence for this "
        f"responsibility.{suffix}"
    )


def _is_category_heading(text: str) -> bool:
    """Skip JD section labels such as 'Application Development' that are not duties."""
    cleaned = re.sub(r"\s+", " ", text or "").strip(" -:•*")
    if len(cleaned) < 4:
        return True
    if len(cleaned) > 70 or "," in cleaned or ";" in cleaned:
        return False
    if len(cleaned.split()) > 6:
        return False
    parsed = parse_responsibility(cleaned)
    return not parsed.actions


def match_responsibilities(
    candidate: CandidateProfile,
    jd: ParsedJD,
) -> tuple[float, list[ResponsibilityMatch]]:
    responsibilities = [
        item.strip()
        for item in jd.responsibilities
        if str(item).strip() and not _is_category_heading(str(item))
    ]
    if not responsibilities:
        return 1.0, []

    required = normalize_skills(jd.required_skills.normalized)
    resume_text = "\n".join(
        [
            candidate.source_text or "",
            *(f"{entry.role}. {entry.text}" for entry in candidate.experience_entries),
        ]
    )
    snippets = _snippets(resume_text)
    results: list[ResponsibilityMatch] = []
    weighted = 0.0
    weight_total = 0.0

    for index, item in enumerate(responsibilities):
        parsed = parse_responsibility(item)
        priority = _priority(
            item,
            index=index,
            total=len(responsibilities),
            required_skills=required,
            job_title=jd.job_title or "",
        )
        best_status = "UNSUPPORTED"
        best_confidence = 0.0
        ranked_evidence: list[tuple[int, float, str]] = []
        for snippet in snippets:
            status, confidence, bits = _classify_snippet(parsed, snippet)
            rank = _STATUS_RANK[status]
            best_rank = _STATUS_RANK[best_status]
            if rank > best_rank or (rank == best_rank and confidence > best_confidence):
                best_status = status
                best_confidence = confidence
            if status != "UNSUPPORTED":
                for bit in bits:
                    ranked_evidence.append((rank, confidence, bit))

        # Cross-snippet: action in one bullet, object in another.
        if best_status in {"WEAK_MATCH", "UNSUPPORTED"}:
            all_tokens = _expand(_tokens(resume_text), _OBJECT_FAMILIES + _ACTION_FAMILIES)
            all_skills = {str(match["normalized"]) for match in find_known_skills(resume_text)}
            action_hit = bool(parsed.actions & all_tokens)
            object_hits = parsed.objects & all_tokens
            family_hits = _shared_family_count(
                parsed.objects, _tokens(resume_text), _OBJECT_FAMILIES
            )
            skill_hits = parsed.catalog_skills & all_skills
            distinctive_hit = bool(parsed.distinctive_actions & all_tokens)
            for pattern, _action_family, distinctive_extra in _MULTIWORD_ACTIONS:
                if distinctive_extra & parsed.distinctive_actions and pattern.search(resume_text):
                    distinctive_hit = True
            if parsed.distinctive_actions and not distinctive_hit:
                best_status = "UNSUPPORTED"
                best_confidence = 0.0
                ranked_evidence = []
            elif action_hit and (len(object_hits) >= 1 or family_hits or skill_hits):
                best_status = "STRONG_MATCH"
                best_confidence = max(best_confidence, 0.82)
                if not ranked_evidence:
                    for snip in snippets:
                        if parsed.objects & _expand(_tokens(snip), _OBJECT_FAMILIES):
                            ranked_evidence.append((3, 0.82, snip))
            elif family_hits >= 1 or len(object_hits) >= 2:
                best_status = "PARTIAL_MATCH"
                best_confidence = max(best_confidence, 0.6)

        ranked_evidence.sort(key=lambda item: (item[0], item[1]), reverse=True)
        evidence = dedupe_preserve([bit for _, _, bit in ranked_evidence])[:3]
        if best_status == "UNSUPPORTED":
            evidence = []
            best_confidence = 0.0
        reason = _reason(best_status, parsed, evidence)
        results.append(
            ResponsibilityMatch(
                jd_responsibility=item,
                match_status=best_status,  # type: ignore[arg-type]
                priority=priority,  # type: ignore[arg-type]
                confidence=round(best_confidence, 3),
                evidence=evidence,
                reason=reason,
            )
        )
        weight = _PRIORITY_WEIGHT[priority]
        weighted += _CREDIT[best_status] * weight
        weight_total += weight

    ratio = round(weighted / weight_total, 4) if weight_total else 1.0
    return ratio, results
