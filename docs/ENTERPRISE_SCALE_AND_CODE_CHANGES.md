# Enterprise scale and code-flow changes

How to take this product from **one Azure VM + one Groq key + one Python process** to an enterprise live-interview platform.

**Target load:** ~100 HR/admin users and ~500 concurrent candidate interviews.  
**Current honest capacity on one 8 vCPU / 32 GB VM:** about **8 staggered live interviews**, not 500.

This document is the plan only. It does not change runtime code by itself.

---

## 1. Best enterprise fix (not a bigger VM)

Split the work so live interviews do **not** share one machine, one Groq key, and one Python process.

### 1. Keep video on the candidate laptop

Do not stream full camera to your server. The browser already has the camera. Send the server **fewer, smaller** checks (for example 1 frame every 2–3 seconds, or on-device first). Recordings go to **Blob storage**, not the app disk. That is what stops Agent 5 from killing the VM.

### 2. Split into 3 systems (not 7 VMs)

| System | What it does | Why |
|--------|----------------|-----|
| **HR API** | Login, jobs, schedule, dashboards (Agents 2, 3) | Cheap, many users, easy to scale |
| **Interview workers** | STT, next question, scoring, TTS (Agents 4, 6) | Queue + many workers |
| **Proctoring workers** | Face / mic (Agent 5) | Separate CPU/GPU pool |

Screening (Agent 1) and HR reports (Agent 7) stay on a **background queue**. They should never run on the live-interview path.

### 3. Queue every heavy AI call

After the candidate speaks: put the audio on a queue → worker does Whisper → worker does scoring → worker does TTS → browser plays it.

If 50 people finish answers together, they **wait in line**, they do not crash the API. Use **Azure Service Bus** or **Redis + workers**.

### 4. More than one LLM

- Fast model (Groq) for live questions
- Stronger model (Azure OpenAI / Anthropic) for scoring and Agent 7
- Second vendor as **fallback** when Groq is 429 or out of tokens

STT can be Groq Whisper **or** Azure Speech so one quota does not freeze the room.

### 5. Many copies of the API, one database

Run the FastAPI app as **several instances** (AKS or App Service). Postgres stays the source of truth. Redis for live session / WebSocket fan-out. Chroma / embeddings as its own small service, **not** inside the interview request.

### What “good” looks like for your numbers

| Load | How it is handled |
|------|-------------------|
| 100 HR/admin | HR API + Postgres. Easy. |
| 500 live interviews | Many interview workers + light proctoring + LLM quota plan |

**One 8 vCPU VM cannot do 500 live interviews.**

### Practical path

1. **Short term:** 8 vCPU VM is only for ~8 staggered interviews.
2. **Next:** queue Agent 4/6, cut Agent 5 frame rate, store video in Blob.
3. **Enterprise:** AKS (or App Service) + queues + Azure OpenAI fallback + Blob + Redis.

Standard pattern: **stateless APIs, queues for AI, object storage for video, more than one model vendor.** A single Groq-on-one-VM setup is a prototype, not an enterprise live-interview platform.

---

## 2. What is deployed today

Everything below runs inside **one process**: `backend/main.py` (uvicorn).

```
Candidate browser (frontend/agent5)
        │  camera stays in the tab
        │  JPEG frames, audio windows, recording chunks, STT audio
        ▼
One FastAPI app on the VM
        │
        ├── Agent 1 screening
        ├── Agent 2 scheduler
        ├── Agent 3 blueprint
        ├── Agent 4 interview (Whisper + Llama + TTS)
        ├── Agent 5 proctoring (YuNet / SFace / MediaPipe)
        ├── Agent 6 evaluation (same Groq chat as Agent 4)
        ├── Agent 7 HR report
        ├── ChromaDB on local disk
        └── Postgres
                │
                ▼
            Groq cloud  (Whisper STT + chat LLM)
```

| Piece | Where it runs now |
|-------|-------------------|
| HR dashboard | `frontend/` → REST on the same API |
| Live interview UI | `frontend/agent5/` → same API |
| Postgres | Same VM or Docker (`interview_scheduler`) |
| Recordings | Local disk via `safe_session_dir()` in Agent 5 |
| Face / attention | In-process CPU, **global semaphore of 2 frames** |
| Answer scoring | In-process `ThreadPoolExecutor(max_workers=4)` |
| WebSockets | In-memory `ConnectionManager` (one process only) |
| Groq | One API key for STT **and** evaluation |

HR/admin load is small. **Live camera interviews** are what fill the VM and Groq.

---

## 3. Current live-interview code flow

This is what happens **today** after a candidate joins the in-app room.

```
Candidate speaks
    → browser MediaRecorder (cloned mic tracks)
    → POST /api/interview/room/sessions/{id}/ai/transcribe
         InterviewAgentService.transcribe_answer()
         → Groq Whisper  (usually 1–3s)
    → POST /api/interview/room/sessions/{id}/ai/answer
         InterviewLangGraphAgent.submit_answer()
         → Agent 6 evaluate_answer_with_llama()     Groq chat
         → Agent 4 generate_followups()            Groq chat (parallel)
         → refine follow-up                        Groq chat again
         (all on a 4-thread pool shared by every interview)
    → POST /api/interview/room/sessions/{id}/ai/speak
         Edge TTS on the VM
    → browser plays next question
```

**At the same time, the whole interview:**

| Traffic | Interval | Code | Hits |
|---------|----------|------|------|
| Face frame JPEG | ~750 ms | `POST /api/sessions/{id}/analyze-frame` | Agent 5 CPU |
| Audio window | ~6 s | `POST /api/sessions/{id}/analyze-audio` | Agent 5 CPU |
| Recording chunk | 5 s | `POST /api/sessions/{id}/recording/chunks` | VM disk |
| Room socket | persistent | `WS /ws/sessions/{id}` | RAM, one process |

Main files:

| Step | File |
|------|------|
| Browser capture + timers | `frontend/agent5/src/pages/CandidatePage.tsx` |
| Transcribe / answer / speak HTTP | `backend/api/routes/candidate_interview.py` |
| LangGraph turn | `backend/agents/interview_agent/graph.py`, `nodes.py` |
| Whisper | `backend/agents/interview_agent/stt_service.py` |
| Scoring | `backend/agents/evaluation_agent/evaluator.py` |
| TTS | `backend/agents/interview_agent/tts_service.py` |
| Frames / audio | `backend/agents/proctoring_agent/api/monitoring.py` |
| Chunks on disk | `backend/agents/proctoring_agent/services/recordings.py` |
| WebSocket map | `backend/agents/proctoring_agent/api/ws.py` |

**Why it feels slow after speaking:** Whisper (STT) often finishes first. The UI still waits for **evaluation + follow-up + TTS**. Under load, Groq can slow STT as well.

**Hard caps in code today**

- Face inference: `_VISUAL_WORKERS = Semaphore(2)` for the **whole server**
- Answer/eval threads: `_executor = ThreadPoolExecutor(max_workers=4)` for the **whole server**
- Frame rate: `VITE_AGENT5_FRAME_INTERVAL_MS` default **750**
- Groq timeout: ~45 seconds, 1 retry

---

## 4. Which agents take load on the VM (today)

| Agent | When it works hard | Load goes to |
|-------|--------------------|--------------|
| **5 Proctoring** | Whole live interview | **VM CPU** |
| **4 Interviewer** | Each spoken Q/A | **Groq** |
| **6 Evaluation** | After each answer | **Groq** |
| **1 Screening** | HR uploads resumes | Queue + Groq (already queued) |
| **2 Scheduler** | Booking / email | Light |
| **3 Blueprint** | Once per job | Light / occasional Groq |
| **7 HR report** | After interview ends | Groq (should stay off the live path) |

If 8–12 people are in interviews: the VM feels **Agent 5**. The “waiting for next question” delay is **Agent 4 + 6 on Groq**. Screening and reports are not what fills the VM during the live room.

---

## 5. Target flow (what to change the code toward)

```
Candidate speaks
    → API accepts audio, returns job_id immediately  (HTTP 202)
    → Azure Service Bus / Redis queue
         Worker A: STT  (Groq Whisper or Azure Speech, with fallback)
         Worker B: score + next question  (Groq fast model, Azure OpenAI fallback)
         Worker C: TTS  (Edge / Azure Speech)
    → Redis pub/sub or WebSocket gateway tells the browser
    → browser plays audio / shows next question

Meanwhile
    → camera stays in the browser
    → 1 small frame every 2–3s (or on-device first) → proctoring workers
    → recording chunks → Azure Blob (not local disk)
```

HR dashboards keep calling a **stateless HR API**. They never share the 4-thread eval pool with live rooms.

---

## 6. Code and workflow changes (by area)

### A. Live answer path (highest priority)

**Today:** `transcribe` then `answer` then `speak` are three **blocking** HTTP calls on the API process.

**Change:**

1. `POST .../ai/transcribe` only **enqueues** audio (`interview_jobs` table or Service Bus). Return `{ job_id, status: "queued" }`.
2. New worker module, e.g. `backend/workers/interview_turn_worker.py`, runs STT → eval → TTS **off the API**.
3. Browser polls `GET .../ai/turns/{job_id}` **or** receives `turn_ready` on the existing WebSocket.
4. Do **not** call Agent 6 from `nodes.py` inside the FastAPI request.
5. Raise or remove the shared `ThreadPoolExecutor(max_workers=4)` as the global limiter; workers scale instead.

Files to change:

- `backend/api/routes/candidate_interview.py`
- `backend/agents/interview_agent/nodes.py`
- `backend/services/interview_agent_service.py`
- `frontend/agent5/src/pages/CandidatePage.tsx` (`submitAnswerCapture`)

Keep the same UI states (`processing` → next question). Only the **transport** becomes async.

### B. Agent 5 proctoring (VM CPU)

**Today:** JPEG every 750 ms, CPU models, 2-frame global lock.

**Change:**

1. Default frame interval **2000–3000 ms** (`VITE_AGENT5_FRAME_INTERVAL_MS`).
2. Optional: run a cheap “face present?” check in the browser; upload only suspicious or sampled frames.
3. Move `analyze-frame` / `analyze-audio` to **proctoring workers** (same pattern as screening jobs).
4. Increase `_VISUAL_WORKERS` only **inside the proctoring pool**, not on the HR API.
5. Client already skips a frame if one is in flight (`frameInFlightRef`) — keep that.

Files:

- `frontend/agent5/src/pages/CandidatePage.tsx`
- `backend/agents/proctoring_agent/api/monitoring.py`

### C. Recordings (disk)

**Today:** `recordings.py` writes WebM/MP4 chunks to local session folders.

**Change:**

1. Upload each chunk to **Azure Blob** (`recordings/{session_id}/...`).
2. Postgres stores blob URLs + sequence (already has chunk rows).
3. Stop treating the API disk as the recording store.
4. Concatenate / finalize in a background job, not on hang-up of the API worker.

Files:

- `backend/agents/proctoring_agent/services/recordings.py`
- `backend/agents/proctoring_agent/api/recording.py`
- `frontend/agent5/src/lib/recordingQueue.ts` (URL / SAS if needed)

### D. Multiple LLM / STT providers

**Today:** `GROQ_API_KEY` + `GROQ_MODEL` for chat; Groq Whisper for STT.

**Change:**

1. Router in `backend/agents/shared/llama_client.py`: primary Groq, fallback Azure OpenAI on 429/401/timeout.
2. Fast model for Agent 4 live questions; stronger model for Agent 6 scoring and Agent 7.
3. STT router in `stt_service.py`: Groq Whisper → Azure Speech.
4. Keep Edge TTS as default; Azure Speech TTS as fallback.

Live path should stay **fast model only**. Do not run Agent 7 (full HR report) until the session is `COMPLETED`.

### E. WebSockets and many API replicas

**Today:** `ConnectionManager` keeps sockets in process memory. A second uvicorn worker cannot see them.

**Change:**

1. Redis pub/sub (or Azure SignalR / Web PubSub) so any API replica can notify a session.
2. `broadcast_ai_session` in `interview_room_service.py` publishes to Redis, not only local websockets.

Files:

- `backend/agents/proctoring_agent/api/ws.py`
- `backend/services/interview_room_service.py`

### F. Chroma / embeddings

**Today:** Chroma process + BGE-M3 can load inside the API. Live eval already skips Chroma (`use_chroma=False` in `nodes.py`).

**Change:**

1. Run Chroma (or Azure AI Search) as a **separate service**.
2. Index Agent 6 examples **after** the turn, in a worker — never on the live HTTP request.
3. Agent 1 screening embeddings stay on the screening worker pool (already queued).

### G. Split deploy (3 systems)

Keep **one Git repo**. Change **how it is run**, then optionally extract services.

| Deployable | Includes | Does not include |
|------------|----------|------------------|
| `hr-api` | auth, jobs, slots, dashboards, Agent 2/3 | frame loop, Whisper, TTS |
| `interview-workers` | Agent 4/6 jobs, TTS | screening batch |
| `proctoring-workers` | Agent 5 models | Groq chat |

`backend/main.py` today mounts **all** of these. Split with:

- env flags (`ENABLE_HR_API`, `ENABLE_INTERVIEW_WORKERS`, `ENABLE_PROCTORING`), or
- separate entrypoints: `main_hr.py`, `workers/interview_turn_worker.py`, `workers/proctoring_worker.py`

Screening already has `SCREENING_EMBED_WORKERS` and `workers.screening_worker`. Copy that pattern.

### H. Scheduling vs live capacity

Today a calendar slot is “one person at this time.” For 500 concurrent AI rooms you need **capacity per window** (`N` seats), Redis/Postgres reservation, and a waiting room if workers are full. That is Agent 2 + session manager, not a bigger LLM.

---

## 7. Suggested Azure building blocks

| Concern | Service |
|---------|---------|
| HR + room API replicas | Azure Container Apps or AKS |
| Interview / proctoring workers | Same, separate scale rules |
| Database | Azure Database for PostgreSQL |
| Cache / socket fan-out | Azure Cache for Redis |
| Job queue | Azure Service Bus |
| Recordings / resumes | Azure Blob Storage |
| Secrets | Azure Key Vault |
| Fast LLM | Groq |
| Fallback LLM | Azure OpenAI |
| Fallback STT/TTS | Azure Speech |
| Gateway | Azure Front Door |

Postgres remains the **system of record**. Queues and Redis are for **in-flight** work only.

---

## 8. Phased rollout (do this order)

### Phase 0 — Pilot on one VM

- Cap concurrent live rooms (e.g. 8).
- Do not use `--reload` in production.
- Paid Groq quota sized for those 8 rooms.

### Phase 1 — Same repo, less damage (weeks)

- Slow Agent 5 to 2–3 seconds per frame.
- Blob for recording chunks.
- Queue Agent 4/6 turns (STT / eval / TTS off the request thread).
- LLM + STT fallback.

**Outcome:** tens of interviews on a few worker VMs, not 500 yet.

### Phase 2 — Horizontal (months)

- Several API replicas + Redis WebSockets.
- Separate proctoring worker pool.
- Slot capacity = worker pool size.
- Chroma/search out of process.

**Outcome:** hundreds of interviews with autoscale and quota alerts.

### Phase 3 — Enterprise hardening

- Multi-tenant, Entra ID, audit, retention jobs.
- Load test (k6): 100 HR sessions + N live rooms.
- Runbooks for Groq 429 and worker backlog.

---

## 9. Definition of done for “enterprise live interviews”

- API returns quickly; AI work is in a queue.
- Video is not stored on the API disk.
- Agent 5 cannot starve Agent 4/6 (separate pools).
- Two LLM/STT vendors; 429 does not freeze the room.
- More than one API instance can run (no in-memory-only sockets).
- Documented max concurrent rooms and a waiting-room UX when full.

Until those are true, treat the product as a **prototype**: one VM, one Groq key, one process.

---

## 10. Related code

| Topic | Path |
|-------|------|
| Unified app | `backend/main.py` |
| In-app room APIs | `backend/api/routes/candidate_interview.py` |
| Turn graph | `backend/agents/interview_agent/nodes.py` |
| Groq chat | `backend/agents/shared/llama_client.py` |
| Groq Whisper | `backend/agents/interview_agent/stt_service.py` |
| Face semaphore | `backend/agents/proctoring_agent/api/monitoring.py` |
| Local recordings | `backend/agents/proctoring_agent/services/recordings.py` |
| Screening queue (pattern to copy) | `backend/agents/screening_agent/services/screening_worker_pool.py` |
| Live UI | `frontend/agent5/src/pages/CandidatePage.tsx` |

Older planning notes (partly outdated on agent status): [ENTERPRISE_ARCHITECTURE.md](./ENTERPRISE_ARCHITECTURE.md).
