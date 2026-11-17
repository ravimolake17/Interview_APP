# Local Uvicorn Worker Comparison Plan

**Scope:** Windows local only. No automatic worker scaling. No production deploy changes.

---

## Current process-local state (why workers≠2 by default)

| Concern | Location | Multi-worker risk |
|---------|----------|-------------------|
| Interview eval consumer | FastAPI lifespan → `start_interview_eval_worker` | Each worker starts its own consumer (Redis BLPOP OK; memory fallback **not** shared) |
| Redis memory fallback | `core/redis_client.py` when `REDIS_URL` empty | Per-process queues/caches diverge |
| Azure concurrency semaphores | `agents/shared/azure_concurrency.py` | Per-process; limits multiply |
| Agent5 WebSocket / session affinity | Proctoring ConnectionManager in process memory | Sticky sessions required; join→room may hit another worker |
| Agent5 model warmup | Lifespan background task | Loaded **once per process** (2× RAM/CPU if workers=2) |
| DB pool | `core/database.py` pool_size=10 max_overflow=20 | Multiplies × worker count |
| Screening embed workers | Lifespan pool | Multiplies claimers |

**Recommendation for local interview testing:** keep `--workers 1` and **do not use `--reload`**.

---

## Safe comparison plan

### Prerequisites

1. Set `REDIS_URL=redis://127.0.0.1:6379/0` (required for coherent multi-worker eval).
2. Stop any running `--reload` server.
3. Warmup: wait for log `Agent5 model warmup complete`.
4. Use the same candidate join link; one browser only for WS affinity tests.

### Scenario A — One worker (baseline)

```powershell
cd backend
.\venv\Scripts\activate
$env:PYTHONPATH = (Get-Location).Path
python -m uvicorn main:app --host 127.0.0.1 --port 8030 --workers 1
```

Measure (stopwatch / browser Network / server logs):

| Metric | How |
|--------|-----|
| Join `elapsed_ms` | Server log `Interview join bootstrap` |
| GET `/ai/mcq` first | Server log `MCQ generation finished` |
| POST `/ai/mcq/start` | Server log `MCQ start` |
| Options unlock | UI clickable immediately after start (before TTS ends) |
| analyze-frame drop rate | Responses with `stale_frame` under load |

### Scenario B — Two workers (experimental)

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8030 --workers 2
```

**Only with Redis configured.** Expect:

| Check | Pass criteria |
|-------|---------------|
| Join still <30s | Pass |
| MCQ start / unlock | Pass |
| Eval jobs | Exactly one consumer processing each job (no duplicate scores) |
| WebSocket proctoring | May fail or flap if requests hit different workers — **document failure** |
| RAM | ~2× Agent5 model footprint |

### Decision rule

| Result | Action |
|--------|--------|
| workers=1 meets join <30s and MCQ unlock without timeout | **Stay at 1** for local |
| workers=2 helps CPU but breaks WS or doubles model RAM | Do **not** adopt; extract eval consumer before scaling |
| workers=2 only helps when Redis is up | Document Redis as mandatory before any worker increase |

---

## Performance testing rules

- Never use `--reload` during timing runs.
- Do not raise Axios timeouts to “pass” the test.
- Do not claim improvement without log `elapsed_ms` or Network panel timings.
- Production Azure VM settings are out of scope for this document.
