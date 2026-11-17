# Phase 4 — Enterprise concurrency & Azure performance

**Status:** implemented incrementally on the existing single-process App VM topology.  
**Non-goals:** do not raise Uvicorn `--workers` blindly; do not change scoring prompts/providers; do not run 25/50 concurrent production load without written approval.

---

## 1. Current deployment architecture

```
Browser
  → App Gateway (HTTPS)
    → nginx (intapp / proctor)
      → App VM: uvicorn main:app --workers 1 :8030
      → Proctor VM: uvicorn agents.proctoring_agent.main:app --workers 1 :8030

App process (lifespan):
  - Screening worker pool (optional, SCREENING_EMBED_WORKERS)
  - LangGraph checkpointer + Chroma
  - Agent5 bootstrap (routes off when AGENT5_EMBEDDED=false)
  - TTS warmup (background task)
  - Interview eval Redis consumer (ONE asyncio task; parallel job slots inside)

External:
  - PostgreSQL (App VM / shared)
  - Redis (optional; memory fallback if REDIS_URL empty)
  - Azure OpenAI GPT-4o (chat / Agent 6 / correction)
  - Azure Speech STT + TTS (same region preferred)
```

`docker-compose.yml` only runs Postgres. There is **no** app Dockerfile / Gunicorn. Production systemd (see `docs/AZURE_TWO_VM_DEPLOYMENT.md`) pins `--workers 1`.

---

## 2. Actual Uvicorn worker configuration

| Process | Command | Workers |
|--------|---------|---------|
| Interview API | `uvicorn main:app --host 0.0.0.0 --port 8030 --workers 1` | **1** |
| Proctor API | `uvicorn agents.proctoring_agent.main:app … --workers 1` | **1** |
| Redis eval consumers | Started inside App FastAPI lifespan | **1 loop / process** |
| Eval job parallelism | `INTERVIEW_EVAL_CONCURRENCY` (default **2**) inside that loop | not extra processes |
| Screening | Embedded pool or `python -m workers.screening_worker` | configured separately |

**Duplicate background risk if `--workers` > 1:** each worker process would start another eval consumer, another screening pool, another TTS warmup, and another set of in-process Azure semaphores / Agent5 rate limits. Redis `BLPOP` would still deliver each job once, but memory-fallback queues and WebSocket affinity would break. **Keep workers at 1.**

---

## 3. Recommended worker count (justification)

| Layer | Recommendation | Why |
|------|----------------|-----|
| Uvicorn `--workers` | **1** | Lifespan embeds eval + screening; WS/session state is process-local; Azure gates are process-local |
| `INTERVIEW_EVAL_CONCURRENCY` | **2** (raise to 3–4 only after load test) | Agent 6 is off the hot path; more slots increase GPT TPM pressure |
| `STT_WORKER_THREADS` | **4** | Matches Phase 1; covers overlapping answer uploads |
| `AZURE_LLM_MAX_CONCURRENT` | **8** | Caps GPT-4o fan-out (live turns + eval + correction) |
| `AZURE_STT_MAX_CONCURRENT` | **6** | Caps short-audio REST / streaming sessions |
| `AZURE_TTS_MAX_CONCURRENT` | **6** | Caps speak + stream + follow-up pre-gen |
| DB `pool_size` / `max_overflow` | **10 / 20** | Sized for one API process + eval slots |
| Redis `max_connections` | **32** | Shared client pool; avoid unbounded sockets |

Horizontal scale path (future): extract eval consumer to a standalone worker process (`INTERVIEW_EVAL_WORKER_ENABLED=false` on API), keep API at workers=1 or sticky WS sessions, add Redis-required mode.

---

## 4. Azure capacity recommendations

Confirm live quotas in Azure Portal → Foundry / OpenAI → Quotas for your subscription/region. Typical GPT-4o guidance:

- RPM is proportional to assigned TPM; burst windows (1–10s) can 429 even under average RPM.
- Prefer **same region** for Speech STT/TTS and OpenAI as the App VM (e.g. `centralindia` / `eastus2` as already configured) to cut RTT.
- Request TPM/RPM uplift **before** aiming for 25–50 concurrent oral interviews.
- Concurrent Speech sessions are limited by Speech resource tier; streaming STT holds a recognizer per candidate — budget `AZURE_STT_MAX_CONCURRENT` accordingly.

App behavior (Phase 4):

- Process-wide semaphores for LLM / STT / TTS (`agents/shared/azure_concurrency.py`)
- Shared httpx keep-alive clients (`agents/shared/azure_http.py`)
- Bounded retries (default +2) with Retry-After / exponential jitter (`agents/shared/azure_retry.py`) — **no unbounded loops**
- Catalog fallback on 429 still applies after local retries exhaust

Rough capacity planning (order-of-magnitude, not a guarantee):

| Concurrent interviews | Hot-path Azure calls / turn | Notes |
|----------------------|-----------------------------|-------|
| 1–5 | Comfortable on default gates | Validate with load harness |
| 10 | Watch GPT TPM + Speech concurrency | Pause for quota review |
| 25–50 | Requires quota uplift + possibly dedicated eval worker VM | **Approval required** |

---

## 5. Redis worker configuration

| Setting | Default | Role |
|---------|---------|------|
| `REDIS_URL` | empty → memory | **Required in production** for multi-turn durability across restarts |
| `INTERVIEW_ASYNC_EVAL` | true | Live turns do not wait for Agent 6 |
| `INTERVIEW_EVAL_WORKER_ENABLED` | true | Lifespan starts consumer |
| `INTERVIEW_EVAL_CONCURRENCY` | 2 | Parallel `_run_one` slots |
| `INTERVIEW_EVAL_MAX_JOB_RETRIES` | 2 | Then DLQ `interview:eval:dlq` |
| Claim key | `interview:eval:claim:…` SET NX | Dedup same answer enqueue |
| Queue | `interview:eval:queue` RPUSH/BLPOP | Reliable delivery with Redis |

Shutdown: stop signal → cancel consumer → wait up to ~8s for in-flight jobs.

Follow-up generation remains after successful eval, per-candidate pending FU queue + budget keys (unchanged logic).

---

## 6. Load-testing report (harness; live high-volume not run)

Script: `backend/scripts/load_test_interview_concurrency.py`

```bash
# Dry-run plan only (default)
python scripts/load_test_interview_concurrency.py --max-concurrent 50

# Safe live probe (≤5) against health endpoint
python scripts/load_test_interview_concurrency.py --confirm-live --max-concurrent 5

# Above 5 requires --allow-high AND operator approval
```

Ladder: **1 → 5 → 10 → 25 → 50**.  
Metrics: API p50/p95, errors, 429s, `/health` azure_concurrency + interview_eval_queue, plus VM CPU/RAM and Azure portal throttling charts.

**This Phase 4 delivery did not execute high-volume production tests.** Fill the report template after staging runs:

| Concurrent | API p50 | API p95 | STT p95 | GPT p95 | TTS TTFA p95 | Error % | 429s | Redis depth | CPU % | RAM % |
|------------|---------|---------|---------|---------|--------------|---------|------|-------------|-------|-------|
| 1 | | | | | | | | | | |
| 5 | | | | | | | | | | |
| 10 | | | | | | | | | | |
| 25 | *approval* | | | | | | | | | |
| 50 | *approval* | | | | | | | | | |

---

## 7. Failure recovery strategy

| Failure | Behavior |
|---------|----------|
| Azure 429 / 503 | Bounded retry + backoff; then catalog fallback if configured; local semaphore provides backpressure |
| Azure capacity gate timeout | `AzureCapacityError` → client can retry; no stampede |
| Eval / correction transient error | Job requeued with `job_retry_count` / `retry_count` caps |
| Eval exhausted retries | Payload → `interview:eval:dlq` (inspect/replay manually) |
| Redis down | Memory fallback (single process only); set `REDIS_URL` in prod |
| Process crash mid-eval | Job already BLPOP’d may be lost unless replayed from DLQ/audit; prefer Redis + low concurrency + idempotent claim keys |
| Uvicorn restart | Lifespan stops eval worker (drain), closes Azure httpx clients, disposes DB engine |
| Duplicate answer submit | `claim_eval_job` SET NX prevents double Agent 6 |

Observability: `GET /health` includes `azure_concurrency`, `interview_eval_queue`, `redis_memory_fallback`, `uvicorn_workers_policy: 1`.

---

## Event-loop notes (Task 2)

| Area | Mitigation |
|------|------------|
| Azure STT/TTS/GPT sync httpx | Off event loop via executors / STT pool; connection reuse |
| Agent 6 + follow-ups | Background eval worker + `run_in_executor` |
| Shared session state | Per-candidate Redis keys (`interview:questions:`, `pending_fu`, TTS cache) |
| DB / Redis pools | Explicit sizes in config (Phase 4) |

---

## Rollout checklist

1. Confirm systemd still has `--workers 1`.
2. Set `REDIS_URL` on App VM.
3. Deploy Phase 4 code; verify `/health` shows concurrency snapshot.
4. Dry-run load script; then staging 1 → 5 → 10.
5. Adjust `AZURE_*_MAX_CONCURRENT` only after measuring 429s / queue depth.
6. Do **not** raise Uvicorn workers without extracting the eval consumer.
