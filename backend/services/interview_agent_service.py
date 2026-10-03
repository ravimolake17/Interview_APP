"""Agent 4 service — Meta Llama questions, Whisper STT, Edge/Parler TTS cache."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agents.evaluation_agent.evaluator import build_candidate_context
from agents.interview_agent.adaptive import generate_questions_with_llama
from agents.interview_agent.question_bank import (
    QuestionBankLockedError,
    delete_manual_question as remove_question_from_bank,
    insert_manual_question,
    question_edit_policy,
    update_manual_question,
)
from agents.interview_agent.followup_generator import (
    enrich_followups_with_llm,
    generate_followups,
)
from agents.interview_agent.schemas import (
    FollowUpResponse,
    InterviewQuestion,
    QuestionSetResponse,
)
from agents.interview_agent.tts_service import (
    resolve_engine,
    tts_available,
)
from agents.shared.llama_client import llama_available, llama_model_id
from core.chroma_runtime import chroma_status
from core.chroma_store import index_interview_question
from core.langgraph_runtime import get_checkpointer_backend
from repositories.blueprint_repository import BlueprintRepository
from repositories.candidate_repository import CandidateRepository
from repositories.interview_question_set_repository import InterviewQuestionSetRepository
from repositories.interview_repository import InterviewRepository
from services.application_settings_service import ApplicationSettingsService
from services.interview_room_service import plan_is_locked
from services.interview_tts_cache_service import InterviewTTSCacheService
from services.slot_service import company_now


class InterviewAgentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.questions_repo = InterviewQuestionSetRepository(db)
        self.blueprint_repo = BlueprintRepository(db)
        self.candidate_repo = CandidateRepository(db)
        self.interview_repo = InterviewRepository(db)
        self.tts_cache = InterviewTTSCacheService(db)

    async def default_duration_minutes(self) -> int:
        return await ApplicationSettingsService(self.db).get_default_interview_minutes()

    async def _to_response(self, row) -> QuestionSetResponse:
        questions = [InterviewQuestion.model_validate(q) for q in (row.questions_json or [])]
        tts = await self.tts_cache.tts_status(row.id, len(questions))
        ready_map = tts.get("audio_ready_by_question") or {}
        enriched = [
            q.model_copy(update={"audio_ready": bool(ready_map.get(q.id))})
            for q in questions
        ]
        status = row.status
        # Normalize legacy statuses for API consumers.
        if status not in {
            "READY",
            "QUESTIONS_GENERATED",
            "SPEAK_PREPARING",
            "SPEAK_PARTIAL",
            "SPEAK_READY",
            "IN_PROGRESS",
            "COMPLETED",
        }:
            status = "QUESTIONS_GENERATED"

        return QuestionSetResponse(
            id=row.id,
            candidate_id=row.candidate_id,
            blueprint_id=row.blueprint_id,
            status=status,  # type: ignore[arg-type]
            candidate_level=row.candidate_level,
            total_questions=row.total_questions,
            total_duration_minutes=row.total_duration_minutes,
            questions=enriched,
            tts_ready=bool(tts.get("tts_ready")),
            tts_ready_count=int(tts.get("tts_ready_count") or 0),
            tts_preparing=bool(tts.get("tts_preparing")),
            created_at=row.created_at,
            updated_at=row.updated_at,
            capabilities=[
                "whisper_stt",
                "edge_tts" if resolve_engine() == "edge" else "indic_parler_tts",
                "tts_audio_cache",
                "meta_llama_questions",
                "follow_up_questions",
                "agent6_parallel_eval",
            ],
        )

    async def get_status(self, candidate_id: str) -> dict[str, Any]:
        candidate = await self.candidate_repo.get_by_candidate_id(candidate_id)
        if not candidate:
            raise ValueError(f"Candidate not found: {candidate_id}")

        blueprint = await self.blueprint_repo.get_latest_for_candidate(candidate_id)
        question_set = await self.questions_repo.get_latest(candidate_id)
        qs_response = await self._to_response(question_set) if question_set else None
        question_edits = await self.get_question_edit_policy(candidate_id, candidate=candidate)

        return {
            "candidate_id": candidate_id,
            "blueprint_ready": blueprint is not None,
            "questions_ready": question_set is not None and bool(question_set.questions_json),
            "speak_ready": bool(qs_response and qs_response.tts_ready),
            "question_set": qs_response,
            "question_edits": question_edits,
            "capabilities": {
                "whisper_stt": llama_available(),
                "tts": tts_available(),
                "tts_engine": resolve_engine(),
                "tts_provider": (
                    "edge_tts_en_in" if resolve_engine() == "edge" else "indic_parler_tts"
                ),
                "tts_model": (
                    "en-IN-NeerjaNeural"
                    if resolve_engine() == "edge"
                    else "ai4bharat/indic-parler-tts"
                ),
                "tts_voice": "female",
                "tts_style": "indian_english_interviewer",
                "tts_cache": True,
                "tts_storage": "filesystem+postgres",
                "stt_provider": "groq_whisper",
                "stt_model": "whisper-large-v3",
                "stt_resume_correction": True,
                "meta_llama": llama_available(),
                "llama_model": llama_model_id(),
                "question_generation": True,
                "follow_up_questions": True,
                "agent6_parallel": True,
                "chroma_memory": bool(chroma_status().get("ready")),
                "langgraph": True,
                "live_websocket": False,
                "checkpointer": get_checkpointer_backend(),
            },
        }

    async def generate_questions(
        self,
        candidate_id: str,
        *,
        force: bool = False,
    ) -> QuestionSetResponse:
        candidate = await self.candidate_repo.get_by_candidate_id(candidate_id)
        if not candidate:
            raise ValueError(f"Candidate not found: {candidate_id}")

        existing = await self.questions_repo.get_latest(candidate_id)
        if not force:
            if existing and existing.questions_json:
                latest_blueprint = await self.blueprint_repo.get_latest_for_candidate(candidate_id)
                if not latest_blueprint or existing.blueprint_id == latest_blueprint.id:
                    return await self._to_response(existing)
        elif existing and existing.questions_json:
            # Regenerating an existing bank follows the 10-minute lock.
            # Creating the first question set after a late invite/booking must
            # still run even if the interview is already scheduled.
            await self.require_question_edits_allowed(candidate_id)

        blueprint_row = await self.blueprint_repo.get_latest_for_candidate(candidate_id)
        if not blueprint_row:
            raise ValueError(
                "No Agent 3 blueprint found. Generate the interview plan before Agent 4 questions."
            )

        blueprint = blueprint_row.blueprint_json or {}
        snap = candidate.evaluation_snapshot if isinstance(candidate.evaluation_snapshot, dict) else {}
        resume_context = build_candidate_context(
            jd_text=candidate.jd_text,
            evaluation_snapshot=snap,
            job_position=candidate.job_position or blueprint_row.job_title,
        )
        questions = generate_questions_with_llama(
            blueprint,
            job_title=blueprint_row.job_title or candidate.job_position,
            resume_context=resume_context,
        )
        if not questions:
            raise ValueError("Could not generate questions from the blueprint.")

        role = blueprint_row.job_title or candidate.job_position or ""
        for question in questions:
            skill = question.skill_tags[0] if question.skill_tags else ""
            index_interview_question(
                question_text=question.question_text,
                role=role,
                skill=skill,
                category=question.category_id,
                difficulty=question.difficulty,
            )

        duration = None
        time_alloc = blueprint.get("time_allocation") if isinstance(blueprint, dict) else None
        if isinstance(time_alloc, dict):
            duration = time_alloc.get("total_duration_minutes")
        if duration is None:
            duration = await self.default_duration_minutes()

        # Clear previous audio for this candidate when regenerating.
        await self.tts_cache.clear_for_candidate(candidate_id)

        row = await self.questions_repo.create(
            candidate_id=candidate_id,
            blueprint_id=blueprint_row.id,
            status="SPEAK_PREPARING",
            candidate_level=blueprint_row.candidate_level,
            total_questions=len(questions),
            total_duration_minutes=int(duration) if duration is not None else None,
            questions_json=[q.model_dump(mode="json") for q in questions],
            company_id=candidate.company_id,
        )
        return await self._to_response(row)

    async def get_question_edit_policy(
        self,
        candidate_id: str,
        *,
        candidate=None,
        live_started: bool | None = None,
        include_session: bool = False,
    ) -> dict[str, Any]:
        person = candidate or await self.candidate_repo.get_by_candidate_id(candidate_id)
        interview = await self.interview_repo.get_by_candidate_id(candidate_id)
        tz_name = "Asia/Kolkata"
        if person is not None:
            try:
                company = await ApplicationSettingsService(self.db).get_company(person.company_id)
                tz_name = company.timezone or tz_name
            except Exception:
                tz_name = "Asia/Kolkata"
        now = company_now(tz_name)
        start_at: datetime | None = None
        status = None
        if interview is not None and interview.scheduled_date and interview.scheduled_time:
            start_at = datetime.combine(
                interview.scheduled_date,
                interview.scheduled_time,
                tzinfo=now.tzinfo,
            )
            status = interview.status.value if hasattr(interview.status, "value") else str(interview.status)
        if live_started is None:
            session_status = None
            if include_session:
                session_status = await self._langgraph_status(candidate_id)
            live_started = plan_is_locked(person, session_status)
        policy = question_edit_policy(
            now=now,
            start_at=start_at,
            interview_status=status,
            live_started=bool(live_started),
        )
        return {
            **policy,
            "lock_at": policy["lock_at"].isoformat() if policy.get("lock_at") else None,
            "interview_start_at": (
                policy["interview_start_at"].isoformat() if policy.get("interview_start_at") else None
            ),
        }

    async def require_question_edits_allowed(self, candidate_id: str) -> dict[str, Any]:
        policy = await self.get_question_edit_policy(candidate_id, include_session=True)
        if not policy.get("allowed", True):
            raise QuestionBankLockedError(
                str(policy.get("reason") or "Questions cannot be changed now."),
                policy=policy,
            )
        return policy

    async def _langgraph_status(self, candidate_id: str) -> str | None:
        try:
            from agents.interview_agent.graph import InterviewLangGraphAgent

            state = await InterviewLangGraphAgent(self.db).get_session_state(candidate_id)
            return str((state or {}).get("Status") or "") or None
        except Exception:
            return None

    async def save_manual_question(
        self,
        candidate_id: str,
        *,
        question_text: str,
        insert_at: int | None = None,
        question_id: str | None = None,
        category_id: str | None = None,
        category_name: str | None = None,
        difficulty: str = "medium",
        skill_tags: list[str] | None = None,
        estimated_seconds: int = 120,
    ) -> QuestionSetResponse:
        candidate = await self.candidate_repo.get_by_candidate_id(candidate_id)
        if not candidate:
            raise ValueError(f"Candidate not found: {candidate_id}")

        await self.require_question_edits_allowed(candidate_id)

        existing = await self.questions_repo.get_latest(candidate_id)
        current = list(existing.questions_json or []) if existing else []
        if question_id:
            questions = update_manual_question(
                current,
                question_id,
                question_text=question_text,
                insert_at=insert_at,
                category_id=category_id,
                category_name=category_name,
                difficulty=difficulty,
                skill_tags=skill_tags,
                estimated_seconds=estimated_seconds,
            )
        else:
            questions = insert_manual_question(
                current,
                question_text=question_text,
                insert_at=insert_at,
                category_id=category_id,
                category_name=category_name,
                difficulty=difficulty,
                skill_tags=skill_tags,
                estimated_seconds=estimated_seconds,
            )

        duration = None
        if existing and existing.total_duration_minutes:
            extra = 0 if question_id else 2
            duration = max(int(existing.total_duration_minutes) + extra, len(questions) * 2)
        else:
            duration = max(len(questions) * 2, await self.default_duration_minutes())

        if existing:
            row = await self.questions_repo.replace_questions(
                existing.id,
                questions_json=questions,
                total_questions=len(questions),
                total_duration_minutes=duration,
                status="SPEAK_PREPARING",
            )
            if not row:
                raise ValueError("Could not update the question set.")
        else:
            blueprint = await self.blueprint_repo.get_latest_for_candidate(candidate_id)
            row = await self.questions_repo.create(
                candidate_id=candidate_id,
                blueprint_id=blueprint.id if blueprint else None,
                status="SPEAK_PREPARING",
                candidate_level=blueprint.candidate_level if blueprint else None,
                total_questions=len(questions),
                total_duration_minutes=duration,
                questions_json=questions,
                company_id=candidate.company_id,
            )
        return await self._to_response(row)

    async def delete_manual_question(
        self,
        candidate_id: str,
        question_id: str,
    ) -> QuestionSetResponse:
        existing = await self.questions_repo.get_latest(candidate_id)
        if not existing or not existing.questions_json:
            raise ValueError("No question set generated yet.")
        await self.require_question_edits_allowed(candidate_id)
        questions = remove_question_from_bank(list(existing.questions_json or []), question_id)
        duration = existing.total_duration_minutes
        if duration:
            duration = max(1, int(duration) - 2)
        row = await self.questions_repo.replace_questions(
            existing.id,
            questions_json=questions,
            total_questions=len(questions),
            total_duration_minutes=duration,
            status="SPEAK_PREPARING" if questions else "QUESTIONS_GENERATED",
        )
        if not row:
            raise ValueError("Could not update the question set.")
        return await self._to_response(row)

    async def prepare_speak_audio(self, question_set_id: int) -> dict[str, Any]:
        row = await self.questions_repo.get_by_id(question_set_id)
        if not row:
            raise ValueError(f"Question set not found: {question_set_id}")
        await self.questions_repo.update_status(question_set_id, "SPEAK_PREPARING")
        result = await self.tts_cache.pregenerate_for_question_set(
            candidate_id=row.candidate_id,
            question_set_id=row.id,
            questions=list(row.questions_json or []),
        )
        return result

    async def create_followups(
        self,
        candidate_id: str,
        *,
        question_id: str,
        question_text: str,
        candidate_answer: str,
        max_followups: int = 2,
    ) -> FollowUpResponse:
        candidate = await self.candidate_repo.get_by_candidate_id(candidate_id)
        if not candidate:
            raise ValueError(f"Candidate not found: {candidate_id}")

        skill_hints: list[str] = []
        question_set = await self.questions_repo.get_latest(candidate_id)
        if question_set:
            for item in question_set.questions_json or []:
                if item.get("id") == question_id:
                    skill_hints = list(item.get("skill_tags") or [])
                    if not question_text:
                        question_text = str(item.get("question_text") or "")
                    break

        base = generate_followups(
            question_id=question_id,
            question_text=question_text,
            candidate_answer=candidate_answer,
            max_followups=max_followups,
            skill_hints=skill_hints,
        )
        follow_ups = enrich_followups_with_llm(
            question_text=question_text,
            candidate_answer=candidate_answer,
            base=base,
        )
        excerpt = candidate_answer.strip()
        if len(excerpt) > 220:
            excerpt = excerpt[:217] + "..."

        return FollowUpResponse(
            parent_question_id=question_id,
            transcript_excerpt=excerpt,
            follow_ups=follow_ups[:max_followups],
        )

    async def transcribe_answer(
        self,
        candidate_id: str,
        *,
        content: bytes,
        filename: str,
        question_id: str | None = None,
        partial: bool = False,
        prior_text: str | None = None,
    ):
        from agents.interview_agent.stt_corrector import build_stt_context
        from agents.interview_agent.stt_service import transcribe_audio_bytes

        candidate = await self.candidate_repo.get_by_candidate_id(candidate_id)
        if not candidate:
            raise ValueError(f"Candidate not found: {candidate_id}")

        question_text: str | None = None
        if question_id:
            qs = await self.questions_repo.get_latest(candidate_id)
            if qs:
                for item in qs.questions_json or []:
                    if item.get("id") == question_id:
                        question_text = str(item.get("question_text") or "").strip() or None
                        break

        stt_bundle = build_stt_context(
            full_name=candidate.full_name,
            evaluation_snapshot=candidate.evaluation_snapshot,
            jd_text=candidate.jd_text,
            job_position=candidate.job_position,
            question_text=question_text,
        )

        return transcribe_audio_bytes(
            content,
            filename=filename,
            whisper_prompt=stt_bundle.get("whisper_prompt"),
            prior_text=prior_text,
            partial=partial,
            resume_context=stt_bundle.get("context"),
            resume_terms=stt_bundle.get("resume_terms"),
            question_text=question_text,
            candidate_name=stt_bundle.get("candidate_name") or candidate.full_name,
        )

    async def speak(
        self,
        candidate_id: str,
        *,
        text: str | None = None,
        question_id: str | None = None,
        voice: str | None = None,
    ) -> dict[str, Any]:
        import asyncio

        from agents.interview_agent.tts_service import synthesize_speech

        candidate = await self.candidate_repo.get_by_candidate_id(candidate_id)
        if not candidate:
            raise ValueError(f"Candidate not found: {candidate_id}")

        if question_id and not text:
            qs = await self.questions_repo.get_latest(candidate_id)
            if qs:
                for item in qs.questions_json or []:
                    if item.get("id") == question_id:
                        text = str(item.get("question_text") or "")
                        break

        # Live Q&A / closing prompts are not in the stored question bank.
        skip_question_cache = bool(question_id and str(question_id).startswith("qna-"))

        # Prefer disk/Postgres cache (instant) for bank questions only.
        if question_id and not skip_question_cache:
            row = await self.tts_cache.audio_repo.get_ready_for_candidate_question(
                candidate_id=candidate_id, question_id=question_id
            )
            if row:
                from agents.interview_agent.tts_storage import read_audio_file

                data = read_audio_file(row.file_path)
                if data:
                    return {
                        "audio_bytes": data,
                        "content_type": row.content_type or "audio/wav",
                        "provider": row.provider,
                        "model": row.model,
                        "voice": row.voice,
                        "cached": True,
                        "question_id": row.question_id,
                    }

        if not text:
            raise ValueError("No question text or cached audio available to speak.")

        # Live Indic Parler-TTS fallback (slow) — run off the event loop.
        result = await asyncio.to_thread(synthesize_speech, text, voice=voice)
        result["cached"] = False
        return result
