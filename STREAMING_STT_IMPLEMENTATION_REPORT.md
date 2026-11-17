# Streaming STT Implementation Report

**Date:** 2026-11-16  
**Scope:** Local development only  
**Related audit:** `STREAMING_STT_AUDIT_REPORT.md`

---

## Summary

Hardened the existing Azure continuous-recognition path so long answers no longer *depend* on post-silence batch REST STT when streaming is enabled.

| Item | Status |
|------|--------|
| Continuous recognition while speaking | Implemented (opt-in / now local-enabled) |
| Partial ≠ final transcript | Fixed with shared accumulator |
| Batch fallback | Implemented with structured `streaming_stt_fallback_reason` logs |
| Deferred autocorrection | Unchanged |
| Prompts / scoring | Unchanged |
| Live Azure e2e latency measured | **Not run in this session** (see latency report) |

---

## Modified files

| File | Change |
|------|--------|
| `backend/core/config.py` | `interview_stt_end_silence_ms`, `interview_stt_finalization_timeout_ms` |
| `backend/.env` | `INTERVIEW_STT_MODE=streaming`, end-silence + finalization timeouts |
| `backend/.env.example` | Documented streaming flags |
| `backend/agents/interview_agent/streaming_stt.py` | Accumulator, azure_slot, metrics, safer errors |
| `backend/agents/interview_agent/transcript_accumulator.py` | **New** ordered final-segment accumulator |
| `backend/api/routes/candidate_interview_stt_ws.py` | Empty-final logging; expose silence/finalization; empty → `ok:false` |
| `backend/api/routes/candidate_interview.py` | Runtime exposes `end_silence_ms` |
| `backend/tests/test_streaming_stt.py` | Accumulator + end-silence tests |
| `frontend/agent5/src/lib/streamingStt.ts` | Linear resample; capture marks; end-silence in mode API |
| `frontend/agent5/src/lib/transcriptAccumulator.ts` | **New** client accumulator |
| `frontend/agent5/src/lib/transcriptAccumulator.test.ts` | **New** unit tests |
| `frontend/agent5/src/lib/interviewSpeech.ts` | Default end silence 2500ms |
| `frontend/agent5/src/pages/CandidatePage.tsx` | Fixed merge; configurable silence; batch fallback |

---

## Streaming architecture

```
Mic → AudioWorklet → linear resample → PCM s16le 16k
   → WebSocket binary frames
   → PushAudioInputStream (one recognizer / answer turn)
   → recognizing → partial (UI only)
   → recognized → final segments (accumulator)
Browser silence (INTERVIEW_STT_END_SILENCE_MS=2500)
   → stop frames → close push stream → wait finals
   → deterministic resume correction (deferred GPT unchanged)
   → POST /ai/answer (same pipeline as batch)
If streaming empty/fails and MediaRecorder blob exists
   → batch /ai/transcribe fallback (logged)
```

---

## Audio format

| Property | Value |
|----------|-------|
| Capture | Browser AudioContext (often 48 kHz) |
| Transport | PCM signed 16-bit LE, mono, 16 kHz |
| Resample | Linear interpolation (`floatToPcm16k`) |
| Worklet | `frontend/agent5/public/pcm-worklet.js` |
| Audit | Separate MediaRecorder WebM (always) |

---

## Transcript rules

- Partials never submitted as answers.
- Finals ordered; consecutive duplicates / overlap trimmed.
- NoMatch clears partial only; never becomes a segment.
- Empty streaming final → batch fallback when recording exists.
- Correction: same `correct_transcript_with_resume` (deferred LLM).

---

## Feature flags / env

| Variable | Default | Local `.env` |
|----------|---------|--------------|
| `INTERVIEW_STT_MODE` | `batch` | `streaming` |
| `INTERVIEW_STT_END_SILENCE_MS` | `2500` | `2500` |
| `INTERVIEW_STT_FINALIZATION_TIMEOUT_MS` | `5000` | `5000` |

Rollback: set `INTERVIEW_STT_MODE=batch` and restart uvicorn (no `--reload`).

---

## Unit tests

| Suite | Result |
|-------|--------|
| `tests/test_streaming_stt.py` + correction | **27 passed** (mocked; no live Azure) |
| `transcriptAccumulator.test.ts` | **4 passed** |

### Not run / not claimed

| Test | Status |
|------|--------|
| Real Azure continuous recognition e2e | **Not run** this session |
| 15/30/60/120s identical-audio batch vs streaming | **Not measured** |
| Concurrent multi-candidate load | **Not run** |
| Production VM | **Out of scope** |

---

## Known limitations

1. Turn end is still browser VAD (`INTERVIEW_STT_END_SILENCE_MS`), not Azure-only.
2. `streaming_stt_available` requires Azure Speech key hydrated from SuperAdmin secrets (same as batch).
3. Holding `azure_slot("stt")` for the full spoken turn reduces concurrent STT capacity (intentional quota guard).
4. WS reconnect does not auto remount the worklet mid-turn (falls back / next turn).
5. Performance improvement must be proven with live measurements — see latency report.

---

## Local validation checklist

1. Restart backend **without** `--reload`:  
   `.\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8030 --workers 1`
2. Confirm `/api/interview/room/sessions/{id}/ai/stt-mode` → `effective_mode: streaming` once speech key is loaded.
3. Join interview; speak; confirm partials update while talking.
4. Pause mid-answer (~1s) without auto-submit; stop speaking ~2.5s → finalize.
5. Confirm next question TTS and Agent6 async eval still work.
6. Force fallback: stop Azure / break WS → confirm batch recovery log `streaming_stt_fallback_reason`.
