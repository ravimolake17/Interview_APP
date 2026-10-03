# Application stack, models, and per-candidate cost

**Product:** RR Parkon / RR Kabel Agentic HR Recruitment System  
**Document date:** 19 September 2026  
**Prices:** Groq Cloud public list prices as of 8–9 September 2026 ([groq.com/pricing](https://groq.com/pricing), [console.groq.com/docs/models](https://console.groq.com/docs/models)). Convert rupees at the day’s FX rate; examples below use **₹88 / USD**.

This file lists every major library, local model, and paid API used in development, **agent by agent**, then estimates Groq spend for **one candidate** through screening plus a **30-minute** live interview.

---

## How to read this

| Column | Meaning |
| --- | --- |
| **Paid?** | Needs a commercial API key / subscription for production |
| **Runs where** | Cloud API vs downloaded once and run on your server |
| **Fallback** | What the app does if that piece is missing |

**You do not subscribe to OpenAI ChatGPT, Anthropic Claude, Google Gemini, or Azure OpenAI.** Chat and transcription go through **Groq Cloud**. Open-source weights (BGE-M3, Docling, YuNet, Whisper via Groq, etc.) are not billed per inference except Groq-hosted Whisper/LLM.

---

## 0. Shared platform (all agents)

| Layer | Stack | Version / notes | Paid? |
| --- | --- | --- | --- |
| Language | Python | 3.11 recommended | No |
| API | FastAPI + Uvicorn | `fastapi 0.116.1`, `uvicorn 0.35.0` | No |
| Validation | Pydantic / pydantic-settings | 2.x | No |
| Database | PostgreSQL 16 | `docker-compose.yml` (`postgres:16-alpine`) | Hosting only (self-hosted here) |
| ORM / migrations | SQLAlchemy 2 async + Alembic + asyncpg + psycopg v3 | System of record | No |
| Orchestration | LangGraph + LangGraph Postgres checkpointer + langchain-core | Durable graphs for Agents 1, 2, 4, 6, 7 | No |
| Auth | PyJWT, passlib/bcrypt | HR / Admin / SuperAdmin | No |
| Email | SMTP (Microsoft 365 / Outlook in `.env.example`) | Jinja2 templates | Existing mailbox license |
| Vector memory | ChromaDB persistent client | Local disk `backend/storage/chroma` | No |
| Embeddings for Chroma | Same BGE-M3 as Agent 1 | Local | No |
| HR UI | React 18, Vite 6, Tailwind, React Router 7, Axios, Recharts, Framer Motion, Lucide, react-hook-form, react-hot-toast, date-fns, react-dropzone | `frontend/` | No |
| Proctoring UI | React 19, TypeScript, Vite 8 | `frontend/agent5/` | No |
| Screening static UI | Served from backend | `/screening/` | No |

**Shared LLM client:** `backend/agents/shared/llama_client.py`

| Setting | Value |
| --- | --- |
| Provider | Groq Cloud (`groq` Python SDK 1.5.0) |
| Model ID | `openai/gpt-oss-120b` (`GROQ_MODEL`) |
| Retired IDs remapped | `llama-3.3-70b-versatile` → `openai/gpt-oss-120b`; `llama-3.1-8b-instant` → `openai/gpt-oss-20b` |
| Env | `GROQ_API_KEY` (required for LLM + Whisper) |

---

## 1. Agent 1 — Resume / JD screening (ATS)

**Folder:** `backend/agents/screening_agent/`  
**Job:** Extract JD + resume, score, shortlist / needs review / reject.

### Libraries

| Library | Role |
| --- | --- |
| Docling `[easyocr]` 2.107.0 | PDF / DOCX layout extraction |
| EasyOCR | OCR when PDF has little embedded text (`PDF_OCR_MODE=auto`) |
| pypdfium2 | PDF rendering for Docling |
| python-docx | DOCX fallback |
| transformers 4.51–4.x | Docling layout (RT-DETR v2) |
| sentence-transformers / FlagEmbedding | Skill embeddings |
| numpy | Vector math |
| Groq SDK | JD + resume JSON extraction |
| LangGraph | `evaluate` graph with Postgres checkpoint |

### Models (local, free after download)

| Model | ID / source | Role | Paid inference? |
| --- | --- | --- | --- |
| BGE-M3 | `BAAI/bge-m3` (Hugging Face) | Semantic skill matching + Chroma embeddings | No — runs on CPU via PyTorch |
| Docling layout / OCR | IBM Docling + EasyOCR weights | Resume/JD text from scans | No — first-run Hugging Face download |
| PyTorch 2.6 CPU | `torch==2.6.0+cpu` | Embedding + OCR backends | No |

### Paid LLM

| Call | When | Typical size |
| --- | --- | --- |
| JD parse | Once per job description | Up to ~12k chars of JD + JSON out (`GROQ_MAX_TOKENS` up to 8192) |
| Resume parse | Once per resume | Text truncated (~5,500 chars) + JSON sections |

Rule-based parsers still run if Groq is down.

**Subscription:** Groq API key. Hugging Face account is optional (helps if anonymous downloads are rate-limited).

---

## 2. Agent 2 — Scheduler

**Folder:** `backend/agents/scheduler_agent/`  
**Job:** Shortlist → secure token → slots → invite email → booking → confirmation → interview room.

### Libraries

| Library | Role |
| --- | --- |
| LangGraph | Load candidate → token → slots → email → interrupt → reserve → room → confirm |
| SQLAlchemy | `candidate`, `schedule_token`, `available_slots`, `interview` |
| Jinja2 | Email HTML |
| smtplib / Microsoft 365 SMTP | Invite + confirmation |

### Models / LLM

**None.** No Groq call.

**Paid (not Groq):** A mailbox that can send SMTP (Microsoft 365 in this deployment). Cost is the existing M365 seat, not per interview.

---

## 3. Agent 3 — Interview blueprint planner

**Folder:** `backend/agents/blueprint_agent/`  
**Job:** Plan categories, question counts, difficulty, and minutes. **Does not generate spoken questions.**

### Libraries

Python + Pydantic schemas. Deterministic planner in `generator.py`; `fallback.py` if planning fails.

### Models / LLM

**None.** No Groq call.

For a **30-minute** slot the conservative plan is about **10 questions** (2 intro, 4 skills/JD, 2 projects, 2 education), plus a small time buffer.

---

## 4. Agent 4 — Live AI interview

**Folder:** `backend/agents/interview_agent/`  
**Job:** Question bank, TTS of questions, Whisper STT of answers, follow-ups, optional MCQ / candidate Q&A.

### Libraries

| Library | Role |
| --- | --- |
| LangGraph | Present question → wait for answer → evaluate ∥ follow-up |
| Groq SDK | Chat (`gpt-oss-120b`) + audio transcription |
| edge-tts | Default Indian English TTS (CPU, seconds per clip) |
| parler-tts (Hugging Face git) + accelerate + sentencepiece + soundfile | Optional GPU Indic TTS |
| miniaudio | Audio decode helpers |
| Chroma | Retrieve similar past questions |

### Models

| Model | ID | Where it runs | Paid? |
| --- | --- | --- | --- |
| Chat LLM | Groq `openai/gpt-oss-120b` | Cloud | **Yes — tokens** |
| Speech-to-text | Groq `whisper-large-v3` | Cloud | **Yes — per hour of audio** |
| TTS (default) | Microsoft Edge neural: `en-IN-NeerjaNeural` / `en-IN-PrabhatNeural` via `edge-tts` | Your server calling Microsoft Edge | No extra invoice (unofficial client; no Azure Speech subscription) |
| TTS (optional) | `ai4bharat/indic-parler-tts` | Local GPU (`TTS_ENGINE=parler`) | No API fee; needs NVIDIA GPU |

### Groq calls in a live interview

| Step | Frequency (30 min, ~10–14 turns) |
| --- | --- |
| Rewrite question bank | 1 call at prepare |
| Whisper transcribe | **1 call per spoken answer** (full answer blob, not a 30-minute continuous stream) |
| STT name/skill correction | Optional small chat call per answer |
| Adaptive follow-up | A few calls when an answer is weak but usable |
| Per-turn evaluation | Agent 6 (below), once per answer |
| MCQ generation | 1 call only if MCQ mode is used |
| Candidate Q&A | 0–2 calls at the end |

---

## 5. Agent 5 — Proctoring / identity

**Folder:** `backend/agents/proctoring_agent/`  
**Job:** Face match, liveness, gaze, speaker check, session recording. Candidate UI is the interview room.

### Libraries

| Library | Role |
| --- | --- |
| OpenCV headless | Face detect / recognize |
| MediaPipe | Face landmarker (gaze / head pose) |
| SpeechBrain | Speaker embedding |
| Silero VAD | Voice activity |
| librosa + scipy | Audio resample / features |
| reportlab | PDF evidence packs |
| cryptography, argon2-cffi | Secrets / hashing |
| imageio-ffmpeg | ffmpeg helper |
| PyTorch CPU | ONNX / SpeechBrain runtime |

### Models (downloaded by `python -m scripts.agent5.prepare_models`)

| Model | File / repo | License | Paid inference? |
| --- | --- | --- | --- |
| OpenCV YuNet 2023 | `face_detection_yunet_2023mar.onnx` | MIT | No |
| OpenCV SFace 2021 | `face_recognition_sface_2021dec.onnx` | Apache-2.0 | No |
| MediaPipe Face Landmarker float16 | `face_landmarker.task` | Apache-2.0 | No |
| MiniFASNetV2 | `MiniFASNetV2.onnx` | Apache-2.0 | No |
| SpeechBrain ECAPA-TDNN VoxCeleb | `speechbrain/spkrec-ecapa-voxceleb` | Apache-2.0 | No |
| Silero VAD | bundled with `silero-vad` | Permissive | No |

Room STT **reuses Agent 4 Groq Whisper** (`/ai/transcribe`). That cost is counted under Agent 4, not twice.

**Subscription:** none for vision/speaker models. Hugging Face download for SpeechBrain.

---

## 6. Agent 6 — Answer evaluation

**Folder:** `backend/agents/evaluation_agent/`  
**Job:** Score each answer against resume, JD, and short web snippets.

### Libraries / APIs

| Piece | Role | Paid? |
| --- | --- | --- |
| Groq `openai/gpt-oss-120b` | JSON score, verdict, feedback (`max_tokens` 1200) | **Yes** |
| httpx → DuckDuckGo Instant Answer | 2s timeout, 3 snippets | No |
| Chroma | Similar past evaluations | No |

One Groq call **per answered question** (including follow-ups).

---

## 7. Agent 7 — HR recommendation report

**Folder:** `backend/agents/recommendation_agent/`  
**Job:** Hire / consider / reject / hold from screening + interview + integrity, plus similar past cases.

### Libraries

| Piece | Role | Paid? |
| --- | --- | --- |
| Chroma `retrieve_hr_outcomes` | Neighbour cases | No |
| Groq `openai/gpt-oss-120b` | Written rationale (`max_tokens` 1200) | **Yes** — one call per report |
| Deterministic scorer | Decision if LLM is off | No |

---

## Paid products you actually need

### 1. Groq Cloud (required for production AI)

| Item | Detail |
| --- | --- |
| What | API key at [console.groq.com](https://console.groq.com) |
| Models we use | `openai/gpt-oss-120b` (chat) and `whisper-large-v3` (STT) |
| Billing | Pay-as-you-go. Developer **free** tier exists but **rate-limits** screening batches and live interviews. Production should use a **paid / on-demand** Groq plan (no ChatGPT Plus, no Azure OpenAI). |
| List price (Sep 2026) | **$0.15 / 1M input tokens**, **$0.60 / 1M output tokens** for gpt-oss-120b; cached input **$0.075 / 1M**. Whisper Large v3: **$0.111 per hour of audio**. |

### 2. SMTP mailbox (required for invites)

Microsoft 365 / Outlook SMTP as configured. Not billed by Groq. Incremental cost per candidate is essentially **two emails**.

### 3. Optional, not required

| Optional | When |
| --- | --- |
| Hugging Face account / token | If model downloads are throttled |
| NVIDIA GPU + more RAM | Only if you switch `TTS_ENGINE` from Edge to Indic Parler-TTS |
| Cloud VM / GPU instance | If you stop running on a local office PC |
| Groq `whisper-large-v3-turbo` | Cheaper STT (~$0.04/hour) if you accept a small accuracy drop — **not wired today** |

### Not used (do not buy for this app)

OpenAI ChatGPT subscription, Azure Speech, Google Cloud Speech, ElevenLabs, Pinecone, Redis (not in this stack), LangSmith (optional, not required).

---

## Cost for one candidate: screening + 30-minute interview

### Assumptions (typical path)

- One JD parse (if this JD is only used for this person; if many people share a JD, JD cost is almost $0 per person).
- One resume screen.
- Blueprint + question prepare once.
- **~12 spoken answers** (10 planned + ~2 follow-ups).
- Candidate talk time billed to Whisper ≈ **12–18 minutes** of audio (not the full 30 minutes — TTS, thinking, and silence are not all uploaded).
- Agent 6 evaluates each answer; Agent 7 writes one report.
- Edge TTS, Docling, BGE-M3, YuNet, MediaPipe, ECAPA: **$0 usage**.
- SMTP: **$0 incremental** on an existing M365 mailbox.

### Groq token estimate (gpt-oss-120b)

| Stage | Calls | ~Input tokens | ~Output tokens | USD |
| --- | --- | --- | --- | --- |
| Agent 1 JD parse | 1 | 6,000 | 2,500 | $0.0024 |
| Agent 1 resume parse | 1 | 3,000 | 2,500 | $0.0020 |
| Agent 4 question rewrite | 1 | 4,000 | 1,800 | $0.0017 |
| Agent 4 STT corrector | 12 | 10,000 | 2,400 | $0.0029 |
| Agent 4 follow-ups | 3 | 4,500 | 1,200 | $0.0014 |
| Agent 6 evaluations | 12 | 30,000 | 7,200 | $0.0088 |
| Agent 7 HR report | 1 | 3,000 | 800 | $0.0009 |
| **Chat subtotal** | | **~60k** | **~18k** | **~$0.020** |

Formula: `(input / 1e6 × 0.15) + (output / 1e6 × 0.60)`.

### Groq Whisper estimate

| Scenario | Audio billed | Rate | USD |
| --- | --- | --- | --- |
| Light (short answers, ~10 min) | 10 min | $0.111 / hour | **$0.019** |
| Typical (12–18 min speech) | 15 min | $0.111 / hour | **$0.028** |
| Heavy (retries, long answers, ~25 min) | 25 min | $0.111 / hour | **$0.046** |

### All-in Groq per candidate (30 min interview + screening)

| Band | Groq USD | Groq ≈ INR @ ₹88 |
| --- | --- | --- |
| **Typical** | **$0.05 – $0.08** | **₹4 – ₹7** |
| Busy / retries / unique JD + MCQ | **$0.10 – $0.15** | **₹9 – ₹13** |
| Worst case (lots of re-records, long JD, extra Q&A) | **~$0.20** | **~₹18** |

**Agents 2, 3, 5 local models, Edge TTS, DuckDuckGo, Chroma, PostgreSQL:** **$0 extra per candidate** on the current self-hosted setup.

### What this number does **not** include

- Office PC / server electricity and depreciation  
- Staff time  
- Microsoft 365 seat (shared across the company)  
- Internet uplink for live video  
- If you later move Whisper or LLM to another vendor

---

## End-to-end flow (cost where money is spent)

```
JD + resume
  → Agent 1 Docling + BGE-M3 (free) + Groq parse/score (paid, cents)
  → Agent 2 email + calendar (SMTP only)
  → Agent 3 blueprint (free)
  → Agent 5 identity / gaze / speaker (local ONNX, free)
  → Agent 4 Edge TTS (free) + Groq Whisper (paid) + Groq questions (paid)
  → Agent 6 Groq score per answer (paid) + DuckDuckGo (free)
  → Agent 7 Groq HR write-up (paid) + Chroma (free)
```

---

## Quick subscription checklist

| Must have | Why |
| --- | --- |
| **Groq Cloud API key (paid / on-demand for production)** | Only paid AI usage: `openai/gpt-oss-120b` + `whisper-large-v3` |
| **SMTP mailbox** | Invite + confirmation emails |

| Nice to have | Why |
| --- | --- |
| Hugging Face token | Reliable first-time model download |
| GPU | Only for Indic Parler-TTS, not required |

**Bottom line:** For one screened candidate and one 30-minute AI interview, **variable AI cost is about 5–8 US cents (about ₹4–₹7)** at current Groq list prices, almost all of it Whisper audio plus a dozen small gpt-oss-120b JSON calls. There is **no separate OpenAI or ChatGPT subscription** in this architecture.
