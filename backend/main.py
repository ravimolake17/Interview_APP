"""FastAPI application entry point — unified Agentic HR Recruitment System."""

import asyncio
import sys

# LangGraph async Postgres checkpointer needs SelectorEventLoop on Windows.
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from api.routes import (
    auth,
    blueprint,
    candidate_interview,
    candidates,
    evaluation_agent,
    fraud_agent,
    hr,
    interview,
    interview_agent,
    jobs,
    recommendation_agent,
    settings as settings_routes,
    superadmin,
    superadmin_data,
    departments,
    companies,
)
from core.config import get_settings
from core.database import AsyncSessionLocal, engine
from agents.screening_agent.config import settings as screening_settings
from agents.screening_agent.routes.candidates import router as screening_candidates_router
from agents.screening_agent.routes.extract import router as extract_router
from agents.screening_agent.routes.jd import router as jd_router
from agents.screening_agent.routes.matching import router as matching_router
from agents.screening_agent.services.document_ingestion import get_uploads_root
from services.application_settings_service import ApplicationSettingsService

logging.basicConfig(
    level=getattr(logging, screening_settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s", settings.app_name)

    async with AsyncSessionLocal() as db:
        try:
            await ApplicationSettingsService(db).load_ai_runtime()
        except Exception:
            logger.warning(
                "Persistent settings are unavailable; using environment defaults. "
                "Run `alembic upgrade head`.",
                exc_info=True,
            )

    worker_pool = None
    if screening_settings.SCREENING_QUEUE_ENABLED and screening_settings.SCREENING_EMBED_WORKERS:
        from agents.screening_agent.services.screening_worker_pool import get_worker_pool

        worker_pool = get_worker_pool()
        await worker_pool.start()

    from core.chroma_runtime import init_chroma_runtime, shutdown_chroma_runtime
    from core.langgraph_runtime import init_langgraph_runtime, shutdown_langgraph_runtime

    await init_langgraph_runtime()
    try:
        from core.trusted_time import sync_trusted_clock

        sync_trusted_clock(force=True)
    except Exception:
        logger.warning("Trusted clock could not sync at startup", exc_info=True)
    try:
        chroma_info = init_chroma_runtime()
        logger.info("ChromaDB startup: %s", chroma_info)
    except Exception:
        logger.warning("ChromaDB could not start; vector memory disabled", exc_info=True)

    agent5_startup: dict[str, object] = {"ok": False}
    try:
        from agents.proctoring_agent.integration import startup_agent5

        agent5_startup = startup_agent5()
        if agent5_startup.get("ok"):
            logger.info("Agent5 fraud detection startup: %s", agent5_startup)
        else:
            logger.warning("Agent5 fraud detection not active: %s", agent5_startup)
    except Exception:
        logger.warning("Agent5 fraud detection could not start", exc_info=True)

    # Warm Edge/Parler TTS in the background so first Speak is not cold.
    try:
        import asyncio

        from agents.interview_agent.tts_service import resolve_engine, warmup_tts

        async def _warmup() -> None:
            result = await asyncio.to_thread(warmup_tts)
            logger.info("TTS warmup: %s", result)

        asyncio.create_task(_warmup())
        logger.info("TTS engine selected: %s", resolve_engine())
    except Exception:
        logger.warning("TTS warmup could not be scheduled", exc_info=True)

    yield
    await shutdown_langgraph_runtime()
    try:
        shutdown_chroma_runtime()
    except Exception:
        logger.debug("ChromaDB shutdown skipped", exc_info=True)
    try:
        from agents.proctoring_agent.integration import shutdown_agent5

        shutdown_agent5()
    except Exception:
        logger.debug("Agent5 shutdown skipped", exc_info=True)
    if worker_pool is not None:
        await worker_pool.stop()
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    description=(
        "Agentic HR Recruitment System — Agent 1 (Resume Screening ATS) "
        "+ Agent 2 (Interview Scheduler) + Agent 3 (Interview Blueprint) "
        "+ Agent 4 (Live Interviewer) + Agent 5 (Fraud Detection / Proctoring) "
        "+ Agent 6 (Answer Evaluation) + Agent 7 (HR Recommendation)"
    ),
    version="4.0.0",
    lifespan=lifespan,
)

cors_origins = list(
    {
        settings.frontend_url.rstrip("/"),
        settings.agent5_public_url.rstrip("/"),
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8030",
        "http://127.0.0.1:8030",
        *screening_settings.cors_origin_list,
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in cors_origins if origin],
    allow_origin_regex=screening_settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Trust X-Forwarded-* from Azure Application Gateway / nginx.
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

# Agent 1 — Resume Screening
app.include_router(extract_router)
app.include_router(jd_router)
app.include_router(matching_router)
app.include_router(screening_candidates_router)


@app.get("/api/runtime-config")
async def runtime_config():
    """Same contract as the standalone Agent 5 app (empty origin = same host)."""
    return {"interview_api_origin": ""}

# Agent 2 — Interview Scheduler
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(interview.router, prefix=settings.api_prefix)
app.include_router(candidate_interview.router, prefix=settings.api_prefix)
app.include_router(candidates.router, prefix=settings.api_prefix)
app.include_router(hr.router, prefix=settings.api_prefix)
app.include_router(jobs.router, prefix=settings.api_prefix)
app.include_router(settings_routes.router, prefix=settings.api_prefix)
app.include_router(departments.router, prefix=settings.api_prefix)
app.include_router(companies.router, prefix=settings.api_prefix)
app.include_router(superadmin.router, prefix=settings.api_prefix)
app.include_router(superadmin_data.router, prefix=settings.api_prefix)

# Agent 3 — Interview Blueprint
app.include_router(blueprint.router, prefix=settings.api_prefix)

# Agent 4 — Live Interviewer (Meta Llama, Whisper STT, TTS)
app.include_router(interview_agent.router, prefix=settings.api_prefix)

# Agent 6 — Answer Evaluation (Meta Llama + resume/JD/web/Chroma)
app.include_router(evaluation_agent.router, prefix=settings.api_prefix)

# Agent 7 — HR recommendation report
app.include_router(recommendation_agent.router, prefix=settings.api_prefix)

# Agent 5 — Fraud detection bridge + optional in-process monitoring APIs
app.include_router(fraud_agent.router, prefix=settings.api_prefix)
if settings.agent5_embedded:
    try:
        from agents.proctoring_agent.api import admin as agent5_admin
        from agents.proctoring_agent.api import candidate as agent5_candidate
        from agents.proctoring_agent.api import media as agent5_media
        from agents.proctoring_agent.api import monitoring as agent5_monitoring
        from agents.proctoring_agent.api import recording as agent5_recording
        from agents.proctoring_agent.api import ws as agent5_ws
        from agents.proctoring_agent.main import readiness as agent5_readiness

        app.include_router(agent5_candidate.router)
        app.include_router(agent5_monitoring.router)
        app.include_router(agent5_recording.router)
        app.include_router(agent5_admin.router)
        app.include_router(agent5_media.router)
        app.include_router(agent5_ws.router)

        @app.get("/ready")
        async def agent5_ready_endpoint():
            return agent5_readiness()

        _agent5_frontend = None
        try:
            from agents.proctoring_agent.config import get_settings as agent5_settings

            _agent5_frontend = agent5_settings().frontend_dir
        except Exception:
            _agent5_frontend = None

        def _agent5_index():
            if _agent5_frontend and (_agent5_frontend / "index.html").is_file():
                return FileResponse(
                    _agent5_frontend / "index.html",
                    headers={"Cache-Control": "no-cache"},
                )
            return JSONResponse(
                status_code=503,
                content={
                    "detail": (
                        "Agent5 proctoring UI is not built. From repo root run: "
                        "cd frontend && npm install && npm run build"
                    )
                },
            )

        @app.get("/proctoring/")
        async def proctoring_page():
            return _agent5_index()

        @app.get("/monitor/")
        async def monitor_page():
            return _agent5_index()

        if _agent5_frontend and _agent5_frontend.exists():
            app.mount(
                "/proctoring/assets",
                StaticFiles(directory=str(_agent5_frontend / "assets"), html=False),
                name="agent5-proctoring-assets",
            )
    except Exception:
        logger.warning("Agent5 API routers could not be mounted", exc_info=True)
else:
    logger.info("AGENT5_EMBEDDED=false — camera/WebSocket routes are served by the standalone proctoring process")

# Screening recruiter UI (static HTML)
screening_ui_dir = Path(__file__).resolve().parent.parent / "frontend" / "screening"
if screening_ui_dir.exists():
    app.mount("/screening", StaticFiles(directory=screening_ui_dir, html=True), name="screening-ui")

screening_uploads_dir = get_uploads_root()
app.mount("/screening-files", StaticFiles(directory=screening_uploads_dir), name="screening-files")


@app.get("/")
async def home():
    return {
        "message": "Agentic HR Recruitment System",
        "agents": {
            "agent_1": {
                "name": "Resume Screening ATS",
                "version": screening_settings.APP_VERSION,
                "ui": "/screening/",
                "evaluate": "POST /api/candidates/evaluate",
                "evaluate_async": "POST /api/candidates/evaluate/async",
                "evaluate_batch": "POST /api/candidates/evaluate/batch/async",
                "extract": "POST /extract",
                "extract_async": "POST /extract/async",
            },
            "agent_2": {
                "name": "Interview Scheduler",
                "ui": settings.frontend_url,
                "send_invite": "POST /api/interview/send-invite",
            },
            "agent_3": {
                "name": "Interview Blueprint Planner",
                "blueprint": "POST /api/interview/blueprint",
                "blueprint_for_candidate": "POST /api/interview/blueprint/candidates/{candidate_id}",
                "get_blueprint": "GET /api/interview/blueprint/candidates/{candidate_id}",
            },
            "agent_4": {
                "name": "Live AI Interviewer (Meta Llama)",
                "status": "GET /api/interview/agent4/candidates/{candidate_id}/status",
                "generate_questions": "POST /api/interview/agent4/candidates/{candidate_id}/questions",
                "followups": "POST /api/interview/agent4/candidates/{candidate_id}/followups",
                "whisper_stt": "POST /api/interview/agent4/candidates/{candidate_id}/transcribe",
                "tts": "POST /api/interview/agent4/candidates/{candidate_id}/speak",
                "session_start": "POST /api/interview/agent4/candidates/{candidate_id}/session/start",
                "session_answer": "POST /api/interview/agent4/candidates/{candidate_id}/session/answer",
            },
            "agent_6": {
                "name": "Answer Evaluation (Meta Llama + Chroma yardstick)",
                "status": "GET /api/interview/agent6/candidates/{candidate_id}/status",
                "evaluate": "POST /api/interview/agent6/candidates/{candidate_id}/evaluate",
                "evaluations": "GET /api/interview/agent6/candidates/{candidate_id}/evaluations",
            },
            "agent_5": {
                "name": "Fraud Detection / Proctoring",
                "ready": "GET /ready",
                "bootstrap": "POST /api/interview/agent5/candidates/{candidate_id}/bootstrap",
                "status": "GET /api/interview/agent5/candidates/{candidate_id}/status",
                "proctoring_ui": "/proctoring/",
                "monitor_ui": "/monitor/",
            },
            "agent_7": {
                "name": "HR Recommendation Report",
                "status": "GET /api/interview/agent7/candidates/{candidate_id}/status",
                "generate": "POST /api/interview/agent7/candidates/{candidate_id}/generate",
                "report": "GET /api/interview/agent7/candidates/{candidate_id}/report",
                "reports": "GET /api/interview/agent7/reports",
            },
        },
        "langgraph": {
            "agents": [
                "agent_1_screening",
                "agent_2_scheduler",
                "agent_3_blueprint_retry_fallback",
                "agent_4_interview",
                "agent_5_fraud_detection",
                "agent_6_evaluation",
                "agent_7_recommendation",
            ],
            "checkpointer": "postgres (fallback memory)",
        },
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health/live")
async def health_live():
    """Cheap probe for Azure Application Gateway / load balancers."""
    return {"status": "ok"}


@app.get("/health")
async def health_check():
    from core.chroma_runtime import chroma_status

    chroma = chroma_status()
    return {
        "status": "healthy",
        "agents": [
            "Resume Screening (Agent 1)",
            "Interview Scheduler (Agent 2)",
            "Interview Blueprint (Agent 3)",
            "Live Interviewer (Agent 4)",
            "Fraud Detection (Agent 5)",
            "Answer Evaluation (Agent 6)",
            "HR Recommendation (Agent 7)",
        ],
        "chroma": chroma,
    }


def _mount_hr_spa() -> None:
    """Serve the built HR React app from the same origin as the API."""
    dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    index = dist / "index.html"
    if not index.is_file():
        logger.info("HR frontend dist not found at %s — skip SPA mount", dist)
        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets), html=False), name="hr-assets")

    skip_prefixes = (
        "api/",
        "docs",
        "redoc",
        "openapi.json",
        "health",
        "ready",
        "screening",
        "screening-files",
        "proctoring",
        "monitor",
        "candidate",
        "extract",
        "ws/",
        "ui/",
    )

    @app.get("/{full_path:path}")
    async def hr_spa(full_path: str):
        if full_path.startswith(skip_prefixes) or full_path in {"docs", "redoc", "openapi.json"}:
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = dist / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


_mount_hr_spa()

