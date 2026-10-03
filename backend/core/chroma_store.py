"""Chroma collections used as interview memory (not the source of truth).

Collections
-----------
evaluation_examples  Agent 6 — sample strong/weak answers used as a scoring yardstick
interview_questions  Agent 4 — past questions that worked for a role/skill
resume_profiles      Agent 1 — embedded resume summaries for similar-candidate search
hr_outcomes          Agent 7 — past shortlist/reject/hire-shaped cases
"""

from __future__ import annotations

import hashlib
import logging
import threading
from typing import Any, Callable

from core.chroma_runtime import chroma_enabled, get_chroma_client

logger = logging.getLogger(__name__)

COLLECTION_EVALUATION = "evaluation_examples"
COLLECTION_QUESTIONS = "interview_questions"
COLLECTION_RESUMES = "resume_profiles"
COLLECTION_OUTCOMES = "hr_outcomes"

EmbedFn = Callable[[list[str]], list[list[float]]]

_lock = threading.Lock()
_embed_fn: EmbedFn | None = None
_seeded = False

# Starter memory so Agents 4/6 have yardsticks before live interviews exist.
_SEED_EVALUATION_EXAMPLES: list[dict[str, Any]] = [
    {
        "id": "eval-seed-api-strong",
        "quality": "strong",
        "score": 88,
        "skill": "FastAPI",
        "role": "Python Backend Engineer",
        "text": (
            "Question: How have you used FastAPI in production?\n"
            "Answer: I designed a FastAPI service with Redis caching and cut p95 "
            "latency from 800ms to 120ms. I owned the rollout, added timeouts, and "
            "watched error rates in Grafana."
        ),
    },
    {
        "id": "eval-seed-api-weak",
        "quality": "weak",
        "score": 28,
        "skill": "FastAPI",
        "role": "Python Backend Engineer",
        "text": (
            "Question: How have you used FastAPI in production?\n"
            "Answer: I have worked on APIs and I know FastAPI is a Python framework."
        ),
    },
    {
        "id": "eval-seed-sql-strong",
        "quality": "strong",
        "score": 84,
        "skill": "PostgreSQL",
        "role": "Python Backend Engineer",
        "text": (
            "Question: Tell me about a database problem you solved.\n"
            "Answer: A reporting query scanned 12 million rows. I added a composite "
            "index, rewrote the join, and dropped the job from 9 minutes to 40 seconds."
        ),
    },
    {
        "id": "eval-seed-sql-weak",
        "quality": "weak",
        "score": 30,
        "skill": "PostgreSQL",
        "role": "Python Backend Engineer",
        "text": (
            "Question: Tell me about a database problem you solved.\n"
            "Answer: I used SQL in my project and I can write select queries."
        ),
    },
    {
        "id": "eval-seed-ownership-strong",
        "quality": "strong",
        "score": 86,
        "skill": "ownership",
        "role": "Software Engineer",
        "text": (
            "Question: Tell me about work you personally owned.\n"
            "Answer: I owned an onboarding flow end to end. I scoped it, shipped in "
            "three sprints, and conversion rose from 41% to 63%. When a vendor outage "
            "hit, I added a fallback so sign-up still worked."
        ),
    },
    {
        "id": "eval-seed-ownership-weak",
        "quality": "weak",
        "score": 32,
        "skill": "ownership",
        "role": "Software Engineer",
        "text": (
            "Question: Tell me about work you personally owned.\n"
            "Answer: I was part of a team and we completed the project on time."
        ),
    },
]

_SEED_HR_OUTCOMES: list[dict[str, Any]] = [
    {
        "id": "hr-seed-hire-backend",
        "decision": "HIRE",
        "score": 86,
        "role": "Python Backend Engineer",
        "source": "seed",
        "summary": (
            "Strong production FastAPI and PostgreSQL examples with owned metrics. "
            "Interview answers cited latency, ownership, and rollout. Hired."
        ),
    },
    {
        "id": "hr-seed-consider-backend",
        "decision": "CONSIDER",
        "score": 68,
        "role": "Python Backend Engineer",
        "source": "seed",
        "summary": (
            "Solid resume match but interview answers were high-level. "
            "Some skill gaps. Consider with a focused follow-up round."
        ),
    },
    {
        "id": "hr-seed-reject-shallow",
        "decision": "REJECT",
        "score": 41,
        "role": "Software Engineer",
        "source": "seed",
        "summary": (
            "Fluent speaking but no concrete examples, metrics, or ownership. "
            "Similar past cases were rejected for shallow answers."
        ),
    },
]


_SEED_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "q-seed-intro",
        "category": "introductory_questions",
        "skill": "",
        "role": "Software Engineer",
        "difficulty": "easy",
        "text": "To start, walk me through your background and what you are working on right now?",
    },
    {
        "id": "q-seed-fastapi",
        "category": "skills_jd_keyword_questions",
        "skill": "FastAPI",
        "role": "Python Backend Engineer",
        "difficulty": "medium",
        "text": "Give me a concrete example of using FastAPI to solve a production problem?",
    },
    {
        "id": "q-seed-postgres",
        "category": "skills_jd_keyword_questions",
        "skill": "PostgreSQL",
        "role": "Python Backend Engineer",
        "difficulty": "medium",
        "text": "Walk me through a PostgreSQL issue you diagnosed in production and what you changed?",
    },
    {
        "id": "q-seed-experience",
        "category": "experience_questions",
        "skill": "",
        "role": "Software Engineer",
        "difficulty": "medium",
        "text": "Pick one result you delivered recently. What was the problem, what did you do, and what changed?",
    },
    {
        "id": "q-seed-project",
        "category": "project_related_questions",
        "skill": "system design",
        "role": "Software Engineer",
        "difficulty": "medium",
        "text": "On that project, what trade-off did you make, and why did you choose that path?",
    },
]


def set_embed_fn(fn: EmbedFn | None) -> None:
    """Tests can inject a fake embedder so BGE-M3 is not loaded."""
    global _embed_fn, _seeded
    with _lock:
        _embed_fn = fn
        _seeded = False


def reset_chroma_store_for_tests() -> None:
    global _seeded
    with _lock:
        _seeded = False


def embeddings_available() -> bool:
    try:
        vectors = _embed(["chroma availability probe"], allow_load=True)
        return bool(vectors and vectors[0])
    except Exception:
        return False


def embeddings_warm() -> bool:
    """True when the embedding model is already loaded. Never starts a load."""
    try:
        from agents.screening_agent.services.embedding_service import get_embedding_service

        return get_embedding_service().is_loaded()
    except Exception:
        return False


def _default_embed(texts: list[str], *, allow_load: bool = True) -> list[list[float]]:
    from agents.screening_agent.services.embedding_service import get_embedding_service

    service = get_embedding_service()
    if not service.is_available():
        raise RuntimeError("Embedding model is not available")
    if not allow_load and not service.is_loaded():
        raise RuntimeError("Embedding model is not warm")
    cleaned = [" ".join(str(text).split()).strip() for text in texts]
    mapping = service.embed_texts(cleaned)
    out: list[list[float]] = []
    for text in cleaned:
        vector = mapping.get(text)
        if vector is None:
            raise RuntimeError(f"No embedding returned for text: {text[:80]}")
        out.append([float(x) for x in vector.tolist()])
    return out


def _embed(texts: list[str], *, allow_load: bool = True) -> list[list[float]]:
    fn = _embed_fn
    if fn is not None:
        return fn(texts)
    return _default_embed(texts, allow_load=allow_load)


def _doc_id(prefix: str, *parts: str) -> str:
    raw = "|".join(str(part or "").strip() for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}-{digest}"


def _meta(**values: Any) -> dict[str, str | int | float | bool]:
    out: dict[str, str | int | float | bool] = {}
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, bool):
            out[key] = value
        elif isinstance(value, (int, float)):
            out[key] = value
        else:
            text = str(value).strip()
            if text:
                out[key] = text[:500]
    return out


def _get_collection(name: str) -> Any | None:
    client = get_chroma_client()
    if client is None:
        return None
    try:
        return client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception:
        logger.warning("Chroma collection %s unavailable", name, exc_info=True)
        return None


def _upsert(
    collection_name: str,
    *,
    ids: list[str],
    documents: list[str],
    metadatas: list[dict[str, str | int | float | bool]],
    allow_load: bool = True,
) -> bool:
    if not chroma_enabled() or not ids:
        return False
    collection = _get_collection(collection_name)
    if collection is None:
        return False
    try:
        embeddings = _embed(documents, allow_load=allow_load)
        with _lock:
            collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings,
            )
        return True
    except Exception:
        logger.debug("Chroma upsert into %s skipped", collection_name, exc_info=True)
        return False


def _query(
    collection_name: str,
    query_text: str,
    *,
    n_results: int = 4,
    where: dict[str, Any] | None = None,
    allow_load: bool = False,
) -> list[dict[str, Any]]:
    text = " ".join((query_text or "").split()).strip()
    if not chroma_enabled() or not text:
        return []
    collection = _get_collection(collection_name)
    if collection is None:
        return []
    try:
        embedding = _embed([text], allow_load=allow_load)[0]
        kwargs: dict[str, Any] = {
            "query_embeddings": [embedding],
            "n_results": max(1, min(n_results, 12)),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        with _lock:
            raw = collection.query(**kwargs)
    except Exception:
        logger.debug("Chroma query on %s skipped", collection_name, exc_info=True)
        return []

    ids = (raw.get("ids") or [[]])[0]
    docs = (raw.get("documents") or [[]])[0]
    metas = (raw.get("metadatas") or [[]])[0]
    distances = (raw.get("distances") or [[]])[0]
    hits: list[dict[str, Any]] = []
    for index, item_id in enumerate(ids):
        hits.append(
            {
                "id": item_id,
                "document": docs[index] if index < len(docs) else "",
                "metadata": metas[index] if index < len(metas) else {},
                "distance": distances[index] if index < len(distances) else None,
            }
        )
    return hits


def seed_chroma_memory() -> None:
    """Idempotent starter examples for scoring and questions."""
    global _seeded
    if _seeded or not chroma_enabled():
        return
    if not embeddings_available():
        logger.info("Chroma seed deferred until embeddings are available")
        return
    eval_ok = _upsert(
        COLLECTION_EVALUATION,
        ids=[item["id"] for item in _SEED_EVALUATION_EXAMPLES],
        documents=[item["text"] for item in _SEED_EVALUATION_EXAMPLES],
        metadatas=[
            _meta(
                kind="seed",
                quality=item["quality"],
                score=item["score"],
                skill=item["skill"],
                role=item["role"],
            )
            for item in _SEED_EVALUATION_EXAMPLES
        ],
    )
    q_ok = _upsert(
        COLLECTION_QUESTIONS,
        ids=[item["id"] for item in _SEED_QUESTIONS],
        documents=[item["text"] for item in _SEED_QUESTIONS],
        metadatas=[
            _meta(
                kind="seed",
                category=item["category"],
                skill=item["skill"],
                role=item["role"],
                difficulty=item["difficulty"],
            )
            for item in _SEED_QUESTIONS
        ],
    )
    hr_ok = _upsert(
        COLLECTION_OUTCOMES,
        ids=[item["id"] for item in _SEED_HR_OUTCOMES],
        documents=[item["summary"] for item in _SEED_HR_OUTCOMES],
        metadatas=[
            _meta(
                kind="seed",
                decision=item["decision"],
                score=item["score"],
                role=item["role"],
                source=item["source"],
            )
            for item in _SEED_HR_OUTCOMES
        ],
    )
    if eval_ok or q_ok or hr_ok:
        _seeded = True
        logger.info("Chroma starter memory seeded")


def retrieve_evaluation_examples(
    *,
    question_text: str,
    candidate_answer: str,
    role: str = "",
    skills: list[str] | None = None,
    n_results: int = 4,
) -> list[dict[str, Any]]:
    """Closest past answers to use as an Agent 6 scoring yardstick."""
    skill_text = ", ".join(s for s in (skills or []) if s)
    query = (
        f"Role: {role or 'n/a'}\n"
        f"Skills: {skill_text or 'n/a'}\n"
        f"Question: {question_text}\n"
        f"Answer: {candidate_answer}"
    )
    return _query(COLLECTION_EVALUATION, query, n_results=n_results)


def format_evaluation_examples(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return ""
    lines: list[str] = []
    for hit in hits[:4]:
        meta = hit.get("metadata") or {}
        quality = str(meta.get("quality") or "example").upper()
        score = meta.get("score")
        score_bit = f" score {score}" if score is not None else ""
        body = str(hit.get("document") or "").strip()
        if body:
            lines.append(f"- {quality}{score_bit}: {body}")
    return "\n".join(lines)


def index_evaluation_example(
    *,
    question_text: str,
    answer_text: str,
    score: float,
    verdict: str,
    role: str = "",
    skills: list[str] | None = None,
) -> bool:
    answer = (answer_text or "").strip()
    if len(answer.split()) < 12:
        return False
    quality = "strong" if float(score) >= 75 else "weak" if float(score) < 55 else "adequate"
    document = f"Question: {question_text}\nAnswer: {answer}"
    skill_text = ", ".join(s for s in (skills or []) if s)
    return _upsert(
        COLLECTION_EVALUATION,
        ids=[_doc_id("eval", role, question_text, answer)],
        documents=[document],
        metadatas=[
            _meta(
                kind="live",
                quality=quality,
                score=round(float(score), 1),
                verdict=verdict,
                skill=skill_text,
                role=role,
            )
        ],
        allow_load=False,
    )


def retrieve_interview_questions(
    *,
    role: str = "",
    skill: str = "",
    category: str = "",
    n_results: int = 3,
) -> list[dict[str, Any]]:
    query = f"Role: {role or 'n/a'}. Category: {category or 'n/a'}. Skill: {skill or 'n/a'}."
    where = {"category": category} if category else None
    hits = _query(COLLECTION_QUESTIONS, query, n_results=max(n_results, 6), where=where)
    if category and not hits:
        hits = _query(COLLECTION_QUESTIONS, query, n_results=max(n_results, 6))
    if not category:
        return hits[:n_results]
    filtered: list[dict[str, Any]] = []
    for hit in hits:
        meta = hit.get("metadata") if isinstance(hit.get("metadata"), dict) else {}
        hit_cat = str(meta.get("category") or "").strip()
        if hit_cat and hit_cat != category:
            continue
        filtered.append(hit)
        if len(filtered) >= n_results:
            break
    return filtered


def index_interview_question(
    *,
    question_text: str,
    role: str = "",
    skill: str = "",
    category: str = "",
    difficulty: str = "",
) -> bool:
    text = (question_text or "").strip()
    if len(text) < 20:
        return False
    return _upsert(
        COLLECTION_QUESTIONS,
        ids=[_doc_id("q", role, category, skill, text)],
        documents=[text],
        metadatas=[
            _meta(
                kind="live",
                role=role,
                skill=skill,
                category=category,
                difficulty=difficulty,
            )
        ],
    )


def retrieve_similar_resumes(
    *,
    jd_text: str,
    role: str = "",
    n_results: int = 5,
) -> list[dict[str, Any]]:
    query = f"Job: {role or 'n/a'}\n{jd_text}"
    return _query(COLLECTION_RESUMES, query, n_results=n_results)


def index_resume_profile(
    *,
    candidate_id: str,
    role: str,
    skills: list[str] | None,
    summary: str,
    score: float,
    decision: str,
    jd_text: str = "",
) -> bool:
    skill_text = ", ".join((skills or [])[:25])
    document = (
        f"Candidate {candidate_id} for {role or 'open role'}. "
        f"Decision: {decision}. Score: {score:.0f}. "
        f"Skills: {skill_text or 'n/a'}. "
        f"Summary: {(summary or '')[:1200]}. "
        f"JD: {(jd_text or '')[:800]}"
    )
    return _upsert(
        COLLECTION_RESUMES,
        ids=[_doc_id("resume", candidate_id, role)],
        documents=[document],
        metadatas=[
            _meta(
                candidate_id=candidate_id,
                role=role,
                decision=decision,
                score=round(float(score), 1),
                skills=skill_text,
            )
        ],
    )


def retrieve_hr_outcomes(
    *,
    query_text: str,
    role: str = "",
    n_results: int = 5,
) -> list[dict[str, Any]]:
    query = f"Role: {role or 'n/a'}\n{query_text}"
    return _query(COLLECTION_OUTCOMES, query, n_results=n_results)


def index_hr_outcome(
    *,
    candidate_id: str,
    role: str,
    decision: str,
    score: float,
    summary: str,
    source: str = "screening",
) -> bool:
    document = (
        f"Candidate {candidate_id}, role {role or 'open'}, "
        f"decision {decision}, score {score:.0f}. {summary[:1500]}"
    )
    return _upsert(
        COLLECTION_OUTCOMES,
        ids=[_doc_id("hr", candidate_id, decision, source)],
        documents=[document],
        metadatas=[
            _meta(
                candidate_id=candidate_id,
                role=role,
                decision=decision,
                score=round(float(score), 1),
                source=source,
            )
        ],
    )


def summarize_similar_hits(hits: list[dict[str, Any]], *, exclude_id: str = "") -> list[dict[str, Any]]:
    """Flatten Chroma hits into JSON-safe similar-case cards."""
    cards: list[dict[str, Any]] = []
    for hit in hits:
        meta = dict(hit.get("metadata") or {})
        candidate_id = str(meta.get("candidate_id") or "")
        if exclude_id and candidate_id == exclude_id:
            continue
        distance = hit.get("distance")
        similarity = None
        if isinstance(distance, (int, float)):
            similarity = round(max(0.0, min(1.0, 1.0 - float(distance))), 3)
        cards.append(
            {
                "candidate_id": candidate_id or None,
                "decision": meta.get("decision"),
                "score": meta.get("score"),
                "role": meta.get("role"),
                "quality": meta.get("quality"),
                "similarity": similarity,
                "excerpt": str(hit.get("document") or "")[:280],
            }
        )
        if len(cards) >= 5:
            break
    return cards
