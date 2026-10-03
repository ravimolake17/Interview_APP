"""Safe minimal blueprint when primary Agent 3 generation fails."""

from __future__ import annotations

from typing import Any

from agents.blueprint_agent.generator import CATEGORY_IDS, CATEGORY_NAMES
from agents.blueprint_agent.schemas import (
    Agent4Metadata,
    CategoryBreakdown,
    DifficultyDistribution,
    FlowStep,
    HumanReadableReport,
    InputSummary,
    InterviewBlueprintRequest,
    InterviewBlueprintResponse,
    TimeAllocation,
)
from schemas.settings import InterviewAvailabilitySettings


def build_fallback_blueprint(
    payload: InterviewBlueprintRequest,
    *,
    error: str | None = None,
    candidate_level: str | None = None,
    total_duration_minutes: int | None = None,
) -> InterviewBlueprintResponse:
    """
    Guaranteed-valid interview blueprint used when the primary planner raises.

    Keeps Agent 4 unblocked with a conservative Entry-level plan.
    """
    level = candidate_level or payload.candidate_level or "Entry-level"
    duration = int(
        total_duration_minutes
        or payload.total_duration_minutes
        or InterviewAvailabilitySettings().slot_minutes
    )
    duration = max(10, min(120, int(5 * round(duration / 5))))
    buffer = 2 if duration <= 12 else 3 if duration <= 25 else 4 if duration <= 40 else 5
    usable = max(4, duration - buffer)

    if duration <= 12:
        counts = {
            "introductory_questions": 1,
            "skills_jd_keyword_questions": 2,
            "project_related_questions": 1,
            "education_courses_questions": 1,
        }
    elif duration <= 20:
        counts = {
            "introductory_questions": 1,
            "skills_jd_keyword_questions": 3,
            "project_related_questions": 2,
            "education_courses_questions": 1,
        }
    else:
        counts = {
            "introductory_questions": 2,
            "skills_jd_keyword_questions": 4,
            "project_related_questions": 2,
            "education_courses_questions": 2,
        }
    total_questions = sum(counts.values())
    minutes = {
        "introductory_questions": max(1, int(round(usable * 0.15))),
        "skills_jd_keyword_questions": max(1, int(round(usable * 0.45))),
        "project_related_questions": max(1, int(round(usable * 0.25))),
        "education_courses_questions": max(1, int(round(usable * 0.15))),
    }
    # Fix rounding so minutes sum exactly to usable without dropping a category below 1.
    drift = usable - sum(minutes.values())
    minutes["skills_jd_keyword_questions"] += drift
    if minutes["skills_jd_keyword_questions"] < 1:
        donor = max(
            (key for key in minutes if key != "skills_jd_keyword_questions"),
            key=lambda key: minutes[key],
        )
        take = 1 - minutes["skills_jd_keyword_questions"]
        minutes[donor] -= take
        minutes["skills_jd_keyword_questions"] = 1

    ats = payload.ats_match_result
    jd = payload.jd_json or {}
    job_title = str(jd.get("job_title") or "").strip() or "Open Role"

    categories: list[CategoryBreakdown] = []
    for order, category_id in enumerate(CATEGORY_IDS, start=1):
        q = counts[category_id]
        easy = max(1, q // 2)
        hard = 1 if q >= 3 else 0
        medium = q - easy - hard
        if medium < 0:
            easy = q
            medium = 0
            hard = 0
        categories.append(
            CategoryBreakdown(
                order=order,
                category_id=category_id,  # type: ignore[arg-type]
                category_name=CATEGORY_NAMES[category_id],
                question_count=q,
                difficulty_mix={"easy": easy, "medium": medium, "hard": hard},
                estimated_minutes=minutes[category_id],
                time_percentage=round((minutes[category_id] / max(usable, 1)) * 100, 1),
                question_type_focus=["fallback_coverage"],
                purpose=f"Fallback coverage for {CATEGORY_NAMES[category_id]}.",
                selection_reason=(
                    "Primary blueprint generation failed; using safe default allocation."
                ),
                candidate_resume_signals=["fallback"],
                jd_signals=[job_title],
                cross_reference_basis=["fallback_plan"],
                agent4_generation_instruction=(
                    f"Generate practical {CATEGORY_NAMES[category_id]} grounded in resume and JD."
                ),
            )
        )

    flow = [
        FlowStep(
            step_order=order,
            stage_name=CATEGORY_NAMES[category_id],
            category_ids=[category_id],  # type: ignore[list-item]
            question_count=counts[category_id],
            estimated_minutes=minutes[category_id],
            interviewer_action=f"Cover {CATEGORY_NAMES[category_id]} with resume/JD grounding.",
        )
        for order, category_id in enumerate(CATEGORY_IDS, start=1)
    ]

    easy_total = sum(item.difficulty_mix.get("easy", 0) for item in categories)
    medium_total = sum(item.difficulty_mix.get("medium", 0) for item in categories)
    hard_total = sum(item.difficulty_mix.get("hard", 0) for item in categories)

    reason_suffix = f" Original error: {error}" if error else ""
    return InterviewBlueprintResponse(
        generation_source="agent3_langgraph_fallback",
        candidate_level=level,  # type: ignore[arg-type]
        input_summary=InputSummary(
            job_title=job_title,
            ats_score=float(ats.overall_score),
            ats_status=str(ats.status or "Unknown"),
            resume_word_count=len(str(payload.resume_json.get("source_text") or "").split()),
            resume_depth_label="fallback",
            jd_word_count=len((payload.jd_text or "").split()),
            jd_complexity_label="fallback",
            matched_skills_count=len(ats.matched_skills or []),
            missing_skills_count=len(ats.missing_skills or []),
            jd_required_skills_count=len(jd.get("required_skills") or [])
            if isinstance(jd.get("required_skills"), list)
            else 0,
            jd_preferred_skills_count=len(jd.get("preferred_skills") or [])
            if isinstance(jd.get("preferred_skills"), list)
            else 0,
            project_evidence_count=0,
            education_course_evidence_count=0,
        ),
        total_questions=total_questions,
        difficulty_distribution=DifficultyDistribution(
            easy=easy_total,
            medium=medium_total,
            hard=hard_total,
            reasoning=(
                "Fallback difficulty mix keeps the interview runnable after planner failure."
                + reason_suffix
            ),
        ),
        category_breakdown=categories,
        time_allocation=TimeAllocation(
            total_duration_minutes=duration,
            buffer_minutes=buffer,
            category_minutes=minutes,
            category_percentages={
                key: round((value / max(usable, 1)) * 100, 1) for key, value in minutes.items()
            },
            time_distribution_basis=[
                "Fallback plan activated after primary Agent 3 generation failure.",
            ],
            reasoning=(
                f"Fallback interview length is {duration} minutes with {buffer} minutes buffer."
                + reason_suffix
            ),
        ),
        skill_focus_plan=[],
        interview_flow=flow,
        decision_factors=[],
        agent4_metadata=Agent4Metadata(
            guardrails=[
                "This blueprint was produced by Agent 3 LangGraph fallback.",
                "Prefer regenerating a full blueprint when screening data is complete.",
            ]
        ),
        human_readable_report=HumanReadableReport(
            summary=(
                f"Fallback {duration}-minute {level} interview blueprint with "
                f"{total_questions} questions. Primary planner failed; safe defaults applied."
            ),
            recommended_flow=[CATEGORY_NAMES[c] for c in CATEGORY_IDS],
            interviewer_notes=[
                "Use this plan only as a recovery path.",
                "Regenerate after fixing screening/JD inputs if possible.",
            ],
            risk_flags=["fallback_blueprint"],
        ),
    )
