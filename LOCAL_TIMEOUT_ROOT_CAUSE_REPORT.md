# Local Interview Verification & MCQ Timeout — Root Cause Report

**Environment:** Windows local development only (no Azure VM).  
**Date:** 2026-11-13  
**Constraint:** Scoring, prompts, and business logic preserved. Axios timeouts were **not** raised to hide the issue.

---

## Executive verdict

| Symptom | Root cause | Fix |
|---------|------------|-----|
| Join `timeout of 30000ms exceeded` | Sync Agent5 bootstrap + cold model load competed with a blocked event loop (sync Azure LLM for MCQ) | Offload join bootstrap to thread; background Agent5 model warmup |
| MCQ `timeout of 60000ms exceeded` + options locked | Sync `generate_mcq_questions` / Azure LLM ran **on the event loop**; UI kept `status=pending` until `/mcq/start` while TTS blocked | Offload MCQ LLM to `asyncio.to_thread`; start MCQ **before** TTS; recover via GET `/ai/mcq` on timeout |
| Options disabled after intro/rules | `McqPanel` locks unless `status === 'in_progress'`; start ran **after** TTS | Reorder: start → unlock → speak in background |
| Intermittent mid-test stalls | `uvicorn --reload` restarted process; analyze-frame queued behind busy visual workers | Document: no `--reload` in perf tests; drop frames when visual semaphore busy |

---

## Phase A — Request lifecycle (evidence)

### 1. Join — `GET /api/interview/join/{token}`

- Handler: `backend/api/routes/interview.py` (`join_interview`)
- Client: Axios 30s (`frontend/src/services/api.js`)
- UI: `frontend/src/pages/JoinInterview.jsx`

**Wait points before fix:**
1. App still in lifespan (Chroma / Agent5 DB / screening) if `--reload` just restarted.
2. **`bootstrap_agent5_session` sync** on the async handler (SQLAlchemy Agent5 session + JWT).
3. Event loop blocked by concurrent **sync Azure LLM** inside `ensure_mcq` → join waits until LLM finishes.

### 2. MCQ start — `POST .../ai/mcq/start`

- Handler: `backend/api/routes/candidate_interview.py` → `mcq_svc.start_mcq`
- Generation: `ensure_mcq` → `generate_mcq_questions` → `call_llama_json` (sync, 45s HTTP + retries)
- Client: `CandidatePage.tsx` 60s timeout

**Wait points before fix:**
1. If questions missing: sync LLM on event loop (primary).
2. Frontend spoke intro + rules **before** calling start → status stayed `pending` → options locked (`McqPanel.tsx`: `status !== 'in_progress'`).
3. On client timeout, start could still succeed server-side with no recovery poll.

### 3. Agent5 models

- **Not** loaded in lifespan (`startup_agent5` is DB/config only).
- Lazy load forced by `_mandatory_model_readiness()` on `/state` and `/start` (`candidate.py`).
- First enroll/start after cold boot could exceed 30s while SpeechBrain / YuNet / MediaPipe load.

### 4. analyze-frame

- Semaphore(2) + `run_in_threadpool` for inference (good).
- Before fix: waiting on semaphore queued many frames behind face inference, adding load on the single process.

### 5. Instrumentation added

| Location | Metric |
|----------|--------|
| `interview.py` join | `Interview join bootstrap … elapsed_ms=` |
| `interview_mcq_service.ensure_mcq` | `MCQ generation finished … elapsed_ms=` |
| `interview_mcq_service.start_mcq` | `MCQ start … elapsed_ms=` |
| `main.py` lifespan | `Agent5 model warmup complete: …` |

---

## Phase B — Backend fixes (smallest safe)

1. **MCQ LLM off event loop** — `asyncio.to_thread(generate_mcq_questions, …)` in `ensure_mcq`.
2. **Join bootstrap off event loop** — `asyncio.to_thread(bootstrap_agent5_session, …)`.
3. **Agent5 model warmup** — background task after lifespan starts (once per process).
4. **analyze-frame backpressure** — 50ms acquire timeout; drop frame as `stale_frame` instead of waiting.
5. **MCQ start idempotent** — already was; logging clarifies no-op vs flip pending→in_progress.

---

## Phase C — Frontend fixes

File: `frontend/agent5/src/pages/CandidatePage.tsx`

1. Call `/ai/mcq/start` **before** TTS.
2. Update UI to `in_progress` immediately so options unlock.
3. Play intro/rules TTS in background (`void (async () => …)`).
4. On start timeout: GET `/ai/mcq` recovery; if already `in_progress` / done, continue.
5. Axios timeouts **unchanged** (30s / 60s).

---

## Phase E — Tests & timings

### Unit tests (`backend/tests/test_local_timeout_fixes.py`)

```
4 passed
```

- `ensure_mcq` uses `to_thread`
- `start_mcq` idempotent when already `in_progress`
- `start_mcq` flips `pending` → `in_progress`
- McqPanel lock rule documented

### Endpoint timings

| Endpoint | Before (observed) | After (design / measured) |
|----------|-------------------|---------------------------|
| Join bootstrap | Could stall >30s when event loop blocked by LLM | Bootstrap off-loop; log `elapsed_ms` (typically low ms once Agent5 DB warm) |
| GET `/ai/mcq` (first gen) | Sync LLM blocked **all** async routes | LLM in thread; other requests proceed |
| POST `/ai/mcq/start` (questions exist) | Fast flip, but client waited for TTS first | Flip first; client unlocks immediately |
| analyze-frame under load | Queue behind semaphore | Drop within ~50ms when busy |

**Live local HTTP measurement:** At report time, `http://127.0.0.1:8030/health/live` was **unreachable** (likely mid-reload or stopped). Re-measure after a clean start **without `--reload`**:

```powershell
cd backend
$env:PYTHONPATH = (Get-Location).Path
.\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8030 --workers 1
```

Then open join link and confirm logs show `Interview join bootstrap … elapsed_ms=` and `MCQ start … elapsed_ms=` under client limits. Do **not** claim wall-clock Azure LLM itself became faster — only that it no longer blocks unrelated requests.

---

## Remaining bottlenecks

1. First Azure GPT-4o MCQ generation still ~seconds–tens of seconds (network) — now isolated to a worker thread.
2. First Agent5 model load still heavy — mitigated by background warmup; first join before warmup finishes can still be slow.
3. Single Uvicorn worker remains process-local for WS / in-memory Redis fallback (see `LOCAL_WORKER_COMPARISON.md`).
4. Continuous analyze-frame still uses CPU; dropping reduces contention but does not remove inference cost.

---

## Modified files

1. `backend/services/interview_mcq_service.py`
2. `backend/api/routes/interview.py`
3. `backend/main.py`
4. `backend/agents/proctoring_agent/api/monitoring.py`
5. `frontend/agent5/src/pages/CandidatePage.tsx`
6. `backend/tests/test_local_timeout_fixes.py` *(new)*
7. `LOCAL_TIMEOUT_ROOT_CAUSE_REPORT.md` *(new)*
8. `LOCAL_WORKER_COMPARISON.md` *(new)*
