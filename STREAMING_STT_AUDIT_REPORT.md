# Streaming STT Audit Report

**Date:** 2026-11-16  
**Scope:** Local Interview_Agentic_AI codebase only  
**Status:** Audit complete before implementation hardening

---

## Verdict

| Question | Answer |
|----------|--------|
| Default `INTERVIEW_STT_MODE` | **`batch`** (unset in `.env`) |
| Continuous Azure recognition while speaking? | **Yes, when mode=`streaming` + SDK + key** |
| Does the default path wait for full recording? | **Yes** — silence → WebM upload → Azure REST |
| AudioWorklet present? | **Yes** — `frontend/agent5/public/pcm-worklet.js` |
| True end-to-end streaming interview loop? | **Partial** — recognition streams live; turn end is still browser silence (~2.4s) |

---

## Architecture (current)

```
Candidate speaks
├─ MediaRecorder (WebM) ── always kept for audit / batch fallback / proctor
├─ startSilenceMonitor (RMS) ── gates submitAnswerCapture (turn boundary)
└─ if effective_stt_mode == streaming
       StreamingSttClient → WS binary PCM 16 kHz s16le
            → PushAudioInputStream + start_continuous_recognition()
            → partial / segment JSON while speaking
            → on silence: stop → wait finals → correction → /ai/answer
   else
       every 3s: multipart partial WebM → /ai/transcribe (batch REST)
       on silence: full WebM → /ai/transcribe → /ai/answer
```

---

## Component inventory

| Component | Path | Finding |
|-----------|------|---------|
| Feature flag | `backend/core/config.py` `interview_stt_mode` | Default `batch`; env `INTERVIEW_STT_MODE` |
| Continuous SDK | `backend/agents/interview_agent/streaming_stt.py` | PushAudio + continuous recognition; one session per turn |
| Batch REST | `backend/agents/interview_agent/stt_service.py` | Azure short-audio / Groq; chunking >45s |
| WebSocket | `backend/api/routes/candidate_interview_stt_ws.py` | Auth’d PCM in / JSON out; one active session per room |
| Client | `frontend/agent5/src/lib/streamingStt.ts` | Worklet → PCM → WS; waits for `final` |
| Worklet | `frontend/agent5/public/pcm-worklet.js` | Posts Float32 mono blocks |
| Capture UI | `frontend/agent5/src/pages/CandidatePage.tsx` | Starts streaming at answer start; silence submits |
| Silence | `frontend/agent5/src/lib/interviewSpeech.ts` | Default silence 2400ms; no-speech 10s |
| Tests | `backend/tests/test_streaming_stt.py` | Mode flags + mocked session; **no live Azure** |

---

## Azure recognizer lifecycle (streaming)

1. WS `start` → `StreamingSttSession.start()`
2. `SpeechConfig` + `PushAudioInputStream` (16 kHz / 16-bit / mono)
3. `start_continuous_recognition()`
4. Callbacks: `recognizing` → partial; `recognized` → segment; `canceled` / `session_stopped` → final ready
5. Binary PCM frames written continuously
6. WS `stop` → `stream.close()` → `stop_continuous_recognition()` → wait ≤3s → join segments

**Does not** create a new recognizer per audio frame. **Does** create one recognizer per answer turn.

---

## Gaps vs true real-time requirements

1. **Default is still batch** — long answers pay 15–30s Azure REST after silence.
2. **No `INTERVIEW_STT_END_SILENCE_MS`** — end-of-answer silence hardcoded (~2400ms).
3. **Frontend transcript merge bug** — `onPartial` replaces by length; `onSegment` appends; can duplicate text in `liveAnswerTranscriptRef`.
4. **Nearest-neighbor resample** — functional but lower quality than linear interpolation.
5. **Streaming empty → throw** — does not automatically fall back to MediaRecorder + batch STT with structured reason.
6. **`azure_slot("stt")` unused** by streaming SDK path (batch REST only).
7. **`.env.example` omits** streaming flags.
8. **Reconnect** reconnects socket only — does not remount worklet / re-`start` turn.
9. **Latency comparison** — unit tests exist; real Azure p50/p95 for 15/30/60/120s **not measured** in-repo.
10. **Dual silence clocks** — Azure phrase segmentation (~1200ms) vs browser turn-end (~2400ms); interview turn is client-driven.

---

## What already works (keep)

- Continuous recognition while speaking (opt-in streaming)
- Partial + segment WS events
- Deferred GPT correction unchanged on streaming finalize
- MediaRecorder audit path independent of STT
- Graceful degrade to batch on `streaming_disabled` / `start_failed`
- Session isolation (`_active_sessions` per room session_id)

---

## Files planned for modification

| File | Change intent |
|------|---------------|
| `STREAMING_STT_AUDIT_REPORT.md` | This audit |
| `backend/core/config.py` | End-silence + finalization timeout settings |
| `backend/.env` / `.env.example` | Local `INTERVIEW_STT_MODE=streaming` + docs |
| `backend/agents/interview_agent/streaming_stt.py` | Accumulator, metrics, concurrency slot, final wait |
| `backend/api/routes/candidate_interview_stt_ws.py` | Expose end-silence; structured fallback logging hooks |
| `frontend/agent5/src/lib/streamingStt.ts` | Linear resample, client accumulator, metrics |
| `frontend/agent5/src/pages/CandidatePage.tsx` | Fix merge; configurable silence; batch fallback |
| `frontend/agent5/src/lib/interviewSpeech.ts` | Honor end-silence option (already param) |
| `backend/tests/test_streaming_stt.py` (+ frontend tests) | Accumulator / fallback / resample |
| `STREAMING_STT_IMPLEMENTATION_REPORT.md` | Post-change report |
| `STREAMING_STT_LATENCY_COMPARISON.md` | Measured vs not-run clarity |

---

## Restrictions confirmed

- Local only; no production VM / worker-count changes
- Batch STT retained
- Prompts / scoring / deferred correction preserved
- No Azure resource replacement
