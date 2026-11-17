# Streaming vs Batch STT Latency Comparison

**Date:** 2026-11-16  
**Environment:** Local (intended) — App VM / production **not** used  
**Honesty rule:** No improvement claimed without measured samples.

---

## Measurement status

| Item | Status |
|------|--------|
| Unit / mock tests | Passed (see implementation report) |
| Real Azure integration runs | **Not completed in this session** |
| Identical-audio A/B (15/30/60/120s) | **Not measured** |
| p50 / p95 | **N/A — sample count = 0** |

**Do not treat this document as proof of a 15–30s reduction until the tables below are filled from live runs.**

---

## What should improve (hypothesis — not measured)

| Mode | Work after candidate stops speaking |
|------|-------------------------------------|
| Batch (current pain) | Upload full WebM + Azure REST on entire clip → often **15–30s** for long answers |
| Streaming (enabled locally) | Recognition already ran during speech; after silence mainly flush finals + correction + answer API + TTS |

Hypothesis: `speech_end_to_final_ms` (streaming) ≪ batch `stt_ms` for the same audio duration. **Unverified until measured.**

---

## Instrumentation available now

### Client marks / spans (`InterviewTurnTrace`)

- `mic_capture_started`
- `first_audio_frame_captured`
- `first_audio_frame_sent`
- `stt_stream_started`
- `candidate_speech_end` / `silence_detection_complete` / `silence_wait_ms`
- `stt_stream_stop_requested` / `last_audio_frame_sent`
- `stt_stream_final_received`
- `partial_first_ms`, `first_final_segment_ms`, `speech_end_to_final_ms`
- `stt_batch_fallback`, `stt_mode_effective`
- answer API + TTS marks (existing)

### Server metrics (streaming `final.metrics`)

- `partial_first_ms`
- `first_final_segment_ms`
- `first_audio_write_ms`
- `recognition_started_ms`
- `speech_end_to_final_ms`
- `stt_audio_duration_seconds`
- `segment_count`

Clocks are **monotonic within each process**. Do not subtract browser timestamps from server timestamps.

---

## Planned comparison matrix (empty — fill after runs)

Conditions: same language (`en-IN`), same Azure Speech resource, local `--workers 1`, **no `--reload`**.

### Batch

| Duration | n | speech_end→transcript p50 | speech_end→transcript p95 | speech_end→next TTS play p50 |
|----------|---|---------------------------|---------------------------|------------------------------|
| 15s | 0 | — | — | — |
| 30s | 0 | — | — | — |
| 60s | 0 | — | — | — |
| 120s | 0 | — | — | — |

### Streaming

| Duration | n | speech_end→final p50 | speech_end→final p95 | speech_end→next TTS play p50 | first_partial p50 |
|----------|---|----------------------|----------------------|------------------------------|-------------------|
| 15s | 0 | — | — | — | — |
| 30s | 0 | — | — | — | — |
| 60s | 0 | — | — | — | — |
| 120s | 0 | — | — | — | — |

---

## How to measure locally

1. Restart uvicorn with `INTERVIEW_STT_MODE=streaming` (already in `.env`), `--workers 1`, no reload.
2. Run oral answers of ~15/30/60/120s; copy latency beacon / server `stt_stream_*` metrics.
3. Set `INTERVIEW_STT_MODE=batch`, restart, replay **same scripted answers** (or saved audio via batch path).
4. Fill tables; compute p50/p95 only when **n ≥ 5** per cell (or clearly label smaller n).

---

## Rollback

```env
INTERVIEW_STT_MODE=batch
```

Restart backend. Batch path and MediaRecorder audit remain intact.
