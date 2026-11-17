# Production Validation Report

**Project:** Interview Agentic AI  
**Report date:** 2026-11-13  
**Scope:** Read-only audit of FastAPI/Uvicorn startup, Redis evaluation workers, Azure Speech clients, and connection pools.  
**Constraint honored:** No source code, configuration, or services were modified or restarted for this report.

**Companion docs:**
- `docs/AZURE_TWO_VM_DEPLOYMENT.md` — production systemd / two-VM topology
- `docs/PHASE4_CONCURRENCY_AND_AZURE.md` — concurrency gates and capacity guidance
- `README.md` — local development startup only

---

## Deliverable 1 — Current deployment architecture

### Finding

Production is a **two-VM** topology behind Application Gateway + nginx. The API is **not** containerized. `docker-compose.yml` runs **Postgres only**. There is **no** application Dockerfile and **no** Gunicorn usage anywhere in the repository.

```
Browser
  → Azure Application Gateway (HTTPS :443)
    → nginx (App VM / Proctor VM)
      → App VM:     uvicorn main:app --workers 1 :8030
      → Proctor VM: uvicorn agents.proctoring_agent.main:app --workers 1 :8030

App process lifespan side effects:
  - Optional screening worker pool
  - LangGraph checkpointer + Chroma
  - Agent5 bootstrap (routes off when AGENT5_EMBEDDED=false)
  - TTS warmup (background task)
  - Interview Redis eval consumer (one asyncio loop per process)

External dependencies:
  - PostgreSQL (App VM / shared)
  - Redis (optional; in-process memory fallback if REDIS_URL empty)
  - Azure OpenAI GPT-4o
  - Azure Speech STT + TTS
```

### Code / config references

| Item | Path | Lines |
|------|------|-------|
| App systemd ExecStart | `docs/AZURE_TWO_VM_DEPLOYMENT.md` | 518 |
| Proctor systemd ExecStart | `docs/AZURE_TWO_VM_DEPLOYMENT.md` | 548 |
| Compose (Postgres only) | `docker-compose.yml` | 3–19 |
| nginx App | `deploy/nginx/intapp.conf` | (proxy only) |
| nginx Proctor | `deploy/nginx/proctor.conf` | (proxy only) |
| App FastAPI lifespan | `backend/main.py` | 59–162, 174 |
| Proctor FastAPI lifespan | `backend/agents/proctoring_agent/main.py` | 84–106 |
| Gunicorn | — | **Not present** (repo-wide search: zero matches) |
| Checked-in `.service` files | — | **None** (units are created on the VM from the deploy doc) |

### Validation instructions

```bash
# On App VM
systemctl cat interview-app
systemctl status interview-app --no-pager
ss -ltnp | grep 8030

# On Proctor VM
systemctl cat interview-proctor
systemctl status interview-proctor --no-pager
```

Confirm `ExecStart` matches the documented uvicorn command and that only one listener binds `:8030`.

---

## Deliverable 2 — Actual Uvicorn worker count

### Finding

**Worker count = 1** for both App and Proctor in the production systemd definitions.

### Code / config references

```text
docs/AZURE_TWO_VM_DEPLOYMENT.md:518
ExecStart=.../uvicorn main:app --host 0.0.0.0 --port 8030 --workers 1

docs/AZURE_TWO_VM_DEPLOYMENT.md:548
ExecStart=.../uvicorn agents.proctoring_agent.main:app --host 0.0.0.0 --port 8030 --workers 1
```

Additional identical commands: lines **460**, **472**, **1165**, **1170**.  
Policy statement: lines **1143**, **1151** (`--workers 1` required; do not raise).

Health policy echo:

```text
backend/main.py:457
"uvicorn_workers_policy": 1
```

### Missing metrics

| Metric | Status |
|--------|--------|
| Live `ps` / `systemctl show` worker count from production VMs | **Not collected** (read-only audit; no SSH/session to live hosts in this pass) |
| Historical worker-count drift after manual edits on VM | **Unknown** until `systemctl cat` is run on each host |

### Validation instructions

```bash
systemctl show interview-app -p ExecStart --value
# Expect: ... uvicorn main:app ... --workers 1

curl -s http://127.0.0.1:8030/health | jq '.uvicorn_workers_policy'
# Expect: 1
```

---

## Deliverable 3 — Reload enabled?

### Finding

| Environment | `--reload` |
|-------------|------------|
| **Production systemd** | **No** |
| **Local README** | **Yes** (dev only) |

Production explicitly forbids reload:

```text
docs/AZURE_TWO_VM_DEPLOYMENT.md:1151
- `uvicorn --reload` or `--workers` > 1
```

Local only:

```text
README.md:64
uvicorn main:app --reload --host 127.0.0.1 --port 8030
```

### Validation instructions

```bash
systemctl cat interview-app | grep -E 'reload|workers'
# Must show --workers 1 and must NOT show --reload
```

---

## Deliverable 4 — Number of running application processes

### Finding (configuration intent)

| Host | Unit | Intended processes |
|------|------|--------------------|
| Interview App VM | `interview-app.service` | **1** Uvicorn process (`--workers 1`) |
| Interview Proctor VM | `interview-proctor.service` | **1** Uvicorn process |
| **Total API processes** | | **2** (one per VM) |

`--workers 1` means a single worker process (no multi-worker prefork farm). There is no separate Gunicorn master.

### Missing metrics

| Metric | Status |
|--------|--------|
| Live PID count on App VM | **Not observed** |
| Live PID count on Proctor VM | **Not observed** |
| Accidental second foreground uvicorn still running | **Not observed** (deploy doc warns about this at line 497) |

### Validation instructions

```bash
# App VM
systemctl status interview-app --no-pager
pgrep -af 'uvicorn main:app'
# Expect exactly one matching process owned by the service

# Proctor VM
pgrep -af 'uvicorn agents.proctoring_agent.main:app'
```

---

## Deliverable 5 — Redis evaluation workers start inside FastAPI lifespan?

### Finding

**Yes — on the App process only.**

App lifespan starts Redis client + interview eval worker:

```text
backend/main.py:122-127
get_redis()
await start_interview_eval_worker()
```

Lifespan attached at `backend/main.py:174`.

Worker task creation:

```text
backend/services/interview_eval_queue.py:385-393
async def start_interview_eval_worker() -> None:
    ...
    _worker_task = asyncio.create_task(_worker_loop(), name="interview-eval-worker")
```

Config defaults (`backend/core/config.py:62–67`):
- `interview_async_eval = True`
- `interview_eval_worker_enabled = True`
- `interview_eval_concurrency = 2` (parallel **jobs** inside the single consumer loop)
- `interview_eval_max_job_retries = 2`

Proctor lifespan does **not** start eval workers (`backend/agents/proctoring_agent/main.py:84–99`).

### Validation instructions

```bash
# App logs after start
journalctl -u interview-app -b --no-pager | grep -i 'Interview eval worker'

# Health snapshot
curl -s http://127.0.0.1:8030/health | jq '.interview_eval_queue, .redis_memory_fallback'
```

Expect `redis_memory_fallback: false` in production (requires `REDIS_URL`).

---

## Deliverable 6 — Does every Uvicorn worker start a separate Redis evaluation worker?

### Finding

**With current production config (`--workers 1`): No — only one consumer exists.**

**If `--workers` were raised above 1: Yes — each worker process runs the full App lifespan and would call `start_interview_eval_worker()` again** (`backend/main.py:127`). That would create **N competing BLPOP consumers** (safe for uniqueness under Redis) but would also multiply screening pools, TTS warmup, Azure semaphores, and break memory-fallback / WebSocket affinity.

In-process guard only prevents duplicate tasks **inside one process**:

```text
backend/services/interview_eval_queue.py:390-391
if _worker_task and not _worker_task.done():
    return
```

That guard does **not** span multiple OS processes.

### Validation instructions

```bash
# Confirm workers remain 1
systemctl show interview-app -p ExecStart --value | grep -o -- '--workers [0-9]*'

# Confirm a single eval task name in process (optional debug)
# Do not enable --workers > 1 without extracting the eval consumer first.
```

---

## Deliverable 7 — Azure Speech clients: per-request vs reused

### Finding

| Path | Initialization | Reuse? | Reference |
|------|----------------|--------|-----------|
| Batch STT (REST) | Shared process-wide `httpx.Client` via `get_azure_http_client("speech")` | **Reused** | `backend/agents/interview_agent/stt_service.py` (~475–478); `backend/agents/shared/azure_http.py:24–40` |
| Batch TTS (REST) | Same shared Speech httpx client | **Reused** | `backend/agents/interview_agent/tts_service.py` (~373–396) |
| Streaming STT (SDK) | New `SpeechConfig` + `SpeechRecognizer` per streaming session/turn | **Per session** | `backend/agents/interview_agent/streaming_stt.py:72`, `140–165` |
| Streaming TTS (SDK) | New `SpeechConfig` + `SpeechSynthesizer` per synthesis | **Per synthesis** | `backend/agents/interview_agent/streaming_tts.py:73–87` |
| Azure OpenAI chat | Shared `httpx.Client` name `"openai"` | **Reused** | `backend/agents/shared/llama_client.py` (~168–211); `azure_http.py:24–40` |

HTTP client singleton:

```text
backend/agents/shared/azure_http.py:24-40
def get_azure_http_client(name: str = "default"):
    """Return a process-wide sync httpx.Client with connection pooling."""
    ...
    client = httpx.Client(limits=limits, timeout=90.0)
    _clients[name] = client
```

SDK recognizer/synthesizer objects are intentionally not process-global (session isolation / stream lifetime).

### Missing metrics

| Metric | Status |
|--------|--------|
| Live Azure Speech concurrent session count | **Not collected** |
| httpx pool saturation / connect wait times | **Not instrumented as a dedicated metric** |
| STT/TTS 429 rate under concurrency | **Not measured** (load tests not run on production) |

### Validation instructions

```bash
curl -s http://127.0.0.1:8030/health | jq '.azure_concurrency'
# Inspect stt/tts in_flight, rejected, wait_ms_total under load
```

Use latency_trace / `X-Interview-*` headers from Phases 0–3 for per-turn STT/TTS timings in staging.

---

## Deliverable 8 — Database and Redis connection pools

### Finding — Main App DB: configured correctly for `--workers 1`

```text
backend/core/database.py:12-18
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=...,      # default 10 (config.py:20)
    max_overflow=...,   # default 20 (config.py:21)
    pool_timeout=...,   # default 30 (config.py:22)
)
```

Defaults sized for a **single** Uvicorn process + embedded eval slots. Raising `--workers` would multiply connections (`workers × (pool_size + max_overflow)`).

### Finding — Redis: configured when `REDIS_URL` is set

```text
backend/core/redis_client.py:53-60
client = redis.Redis.from_url(
    url,
    decode_responses=False,
    max_connections=max_conn,   # default 32 (config.py:60)
    socket_connect_timeout=2.0,
    socket_timeout=5.0,
    health_check_interval=30,
)
```

Empty `REDIS_URL` → in-process memory fallback (`redis_client.py:37–38`). Acceptable only for single-process local/dev; **production must set `REDIS_URL`**.

### Finding — Proctor Agent5 DB: pool not explicitly sized

```text
backend/agents/proctoring_agent/db.py:17-21
engine = create_engine(
    settings.resolved_database_url,
    pool_pre_ping=True,
    future=True,
)
```

Uses SQLAlchemy defaults (typically `pool_size=5`, `max_overflow=10`). Acceptable for one Proctor process; weaker than main App explicit sizing.

### Missing metrics

| Metric | Status |
|--------|--------|
| Postgres `pg_stat_activity` connection count under interview load | **Not collected** |
| SQLAlchemy pool checkout wait time | **Not exposed** |
| Redis `INFO clients` / rejected connections | **Not collected** |
| Confirmation that production `REDIS_URL` is non-empty | **Must be verified on VM `.env`** |

### Validation instructions

```bash
# App health
curl -s http://127.0.0.1:8030/health | jq '.redis_memory_fallback'
# Expect: false

# Postgres (App DB host)
psql "$DATABASE_URL_SYNC" -c "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database();"

# Redis
redis-cli -u "$REDIS_URL" PING
redis-cli -u "$REDIS_URL" INFO clients
redis-cli -u "$REDIS_URL" LLEN interview:eval:queue
redis-cli -u "$REDIS_URL" LLEN interview:eval:dlq
```

---

## Deliverable 9 — Recommended capacity, Azure limits, and Redis worker settings

### Recommended worker / concurrency posture (do not raise blindly)

| Layer | Recommendation | Justification |
|-------|----------------|---------------|
| Uvicorn `--workers` | **1** | Eval + screening + WS/session state + Azure gates are process-local |
| `INTERVIEW_EVAL_CONCURRENCY` | **2** (3–4 only after load test) | Agent 6 is off the hot path; more slots raise GPT TPM pressure |
| `STT_WORKER_THREADS` | **4** | Overlapping answer uploads |
| `AZURE_LLM_MAX_CONCURRENT` | **8** | Caps GPT-4o fan-out (live + eval + correction) |
| `AZURE_STT_MAX_CONCURRENT` | **6** | Caps REST + streaming recognizers |
| `AZURE_TTS_MAX_CONCURRENT` | **6** | Caps speak/stream/follow-up pre-gen |
| DB `pool_size` / `max_overflow` | **10 / 20** | One API process + eval |
| Redis `max_connections` | **32** | Shared singleton client |

Env documentation: `backend/.env.example` (Redis / eval / Azure / DB pool section).  
Implementation: `backend/agents/shared/azure_concurrency.py`, `azure_http.py`, `azure_retry.py`.

### Azure capacity notes

- Confirm live GPT-4o TPM/RPM in Azure Portal before targeting 10+ concurrent oral interviews.
- Prefer same region for Speech and OpenAI as the App VM.
- Streaming STT holds a recognizer per active session — budget `AZURE_STT_MAX_CONCURRENT`.
- Bounded retries only (`AZURE_RETRY_MAX_ATTEMPTS`, default 2 → 3 total attempts). No uncontrolled retry loops.

### Redis evaluation reliability

| Item | Value / location |
|------|------------------|
| Queue | `interview:eval:queue` |
| DLQ | `interview:eval:dlq` (`interview_eval_queue.py`) |
| Dedup claim | `claim_eval_job` SET NX (`interview_speed_cache.py`) |
| Shutdown drain | ~8s in-flight wait (`stop_interview_eval_worker`) |

### Missing metrics (capacity)

| Metric | Status |
|--------|--------|
| Azure portal TPM/RPM assigned vs observed | **Operator must confirm** |
| Speech concurrent session quota | **Operator must confirm** |
| p50/p95 STT, GPT, TTS under 1/5/10 concurrent interviews | **Not filled** (see Deliverable 10) |

---

## Deliverable 10 — Load-testing status, missing metrics, failure recovery, and validation runbook

### 10a. Load-testing report status

Harness exists: `backend/scripts/load_test_interview_concurrency.py`.

| Scenario | Planned | Executed against production? |
|----------|---------|------------------------------|
| 1 concurrent | Yes | **No** |
| 5 concurrent | Yes | **No** |
| 10 concurrent | Yes (approval note) | **No** |
| 25 concurrent | Yes (approval required) | **No** |
| 50 concurrent | Yes (approval required) | **No** |

Default script mode is **dry-run**. Live runs require `--confirm-live`; above 5 concurrent requires `--allow-high` and explicit operator approval. **This audit did not run high-volume production tests.**

### 10b. Missing metrics checklist (fill after staging/approved runs)

| Metric | 1 | 5 | 10 | 25* | 50* |
|--------|---|---|----|-----|-----|
| API p50 / p95 (ms) | | | | | |
| STT p95 (ms) | | | | | |
| GPT-4o p95 (ms) | | | | | |
| TTS TTFA p95 (ms) | | | | | |
| Error rate (%) | | | | | |
| Azure 429 count | | | | | |
| Redis queue depth / delay | | | | | |
| DB connection usage | | | | | |
| CPU % / RAM % (App VM) | | | | | |
| `azure_concurrency.*.rejected` | | | | | |

\*Requires written approval and Azure quota confirmation.

### 10c. Failure recovery strategy (as implemented)

| Failure | Expected behavior |
|---------|-------------------|
| Azure 429 / 503 | Bounded retry + backoff; then catalog fallback if configured; local semaphore backpressure |
| Azure capacity gate timeout | `AzureCapacityError`; client can retry; no stampede |
| Eval / correction transient error | Requeue with capped `job_retry_count` / `retry_count` |
| Eval retries exhausted | Dead-letter → `interview:eval:dlq` |
| Redis unavailable | Memory fallback (single process only) |
| Process restart | Lifespan stops eval worker (drain), closes Azure httpx clients, disposes DB engine |
| Duplicate answer submit | `claim_eval_job` SET NX prevents double Agent 6 enqueue |

### 10d. End-to-end validation runbook (safe, incremental)

1. **Config identity (App VM)**
   ```bash
   systemctl cat interview-app | grep ExecStart
   # Expect: --workers 1, no --reload
   ```
2. **Health**
   ```bash
   curl -s http://127.0.0.1:8030/health/live
   curl -s http://127.0.0.1:8030/health | jq '{redis_memory_fallback, azure_concurrency, interview_eval_queue, uvicorn_workers_policy}'
   ```
3. **Redis required in prod**
   ```bash
   # redis_memory_fallback must be false
   redis-cli -u "$REDIS_URL" LLEN interview:eval:queue
   redis-cli -u "$REDIS_URL" LLEN interview:eval:dlq
   ```
4. **Dry-run load plan**
   ```bash
   cd /opt/apps/Interview_Agentic_AI/backend
   source venv/bin/activate
   python scripts/load_test_interview_concurrency.py --max-concurrent 50
   ```
5. **Staging live probes only (≤5) after approval for that environment**
   ```bash
   python scripts/load_test_interview_concurrency.py --confirm-live --max-concurrent 5 --path /health/live
   ```
6. **Do not** run 25/50 against production without written approval and Azure quota review.
7. **Do not** change `--workers` above 1 without extracting the eval consumer (`INTERVIEW_EVAL_WORKER_ENABLED=false` on API + standalone worker).

---

## Audit inventory (what exists vs what does not)

| Artifact | Present in repo? | Role |
|----------|------------------|------|
| systemd unit **files** (`.service`) | No | Created on VM from deploy doc snippets |
| Docker Compose | Yes | Postgres only (`docker-compose.yml`) |
| App Dockerfile | No | — |
| Gunicorn config | No | — |
| Uvicorn production start | Documented | `docs/AZURE_TWO_VM_DEPLOYMENT.md` |
| nginx configs | Yes | `deploy/nginx/intapp.conf`, `proctor.conf` |
| Phase 4 concurrency gates | Yes | `backend/agents/shared/azure_*.py` |
| Load-test harness | Yes | `backend/scripts/load_test_interview_concurrency.py` |
| Live production metrics tables | No | To be filled after approved runs |

---

## Verdict summary

| # | Deliverable | Verdict |
|---|-------------|---------|
| 1 | Deployment architecture | Two-VM systemd → Uvicorn; Compose is Postgres-only; no Gunicorn |
| 2 | Uvicorn workers | **1** (documented production) |
| 3 | Reload | **Disabled** in production; enabled only in README local start |
| 4 | App processes | **1 per VM** by config; live PIDs not observed in this pass |
| 5 | Eval worker in lifespan | **Yes** on App (`main.py` lifespan); not on Proctor |
| 6 | Per-worker Redis consumer | **Not today** (workers=1); **would duplicate** if workers raised |
| 7 | Azure Speech clients | REST **reused** (httpx); SDK recognizer/synthesizer **per use** |
| 8 | DB / Redis pools | App DB + Redis **explicitly pooled**; Proctor DB uses defaults; confirm `REDIS_URL` |
| 9 | Capacity recommendations | Keep workers=1; tune Azure/eval concurrency only after measurement |
| 10 | Load test / recovery / validation | Harness ready; **production high-volume tests not run**; runbook above |

**Overall:** Production configuration intent is coherent for a single-process App API with an embedded Redis eval consumer. Highest operational risks are (a) raising `--workers` without redesign, (b) empty `REDIS_URL` in production, and (c) Azure quota exhaustion before concurrent-interview scale-up.

---

*End of report.*
