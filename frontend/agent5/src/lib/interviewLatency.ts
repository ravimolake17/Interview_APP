/** Browser-side interview turn latency (monotonic performance.now only). */

import { jsonRequest, requestJson } from './api'

export const TURN_ID_HEADER = 'X-Interview-Turn-Id'
export const TTS_ROLE_HEADER = 'X-Interview-Tts-Role'

export type LatencySpans = Record<string, number | null>

export type InterviewTurnTrace = {
  turnId: string
  sessionId: string
  events: string[]
  spans: LatencySpans
  mark: (name: string) => void
  measure: (spanKey: string, startMark: string, endMark?: string) => number | null
  setSpan: (key: string, valueMs: number | null) => void
  unavailable: (key: string) => void
  elapsedMs: () => number
  payload: () => {
    turn_id: string
    session_id: string
    phase: string
    spans: LatencySpans
    events: string[]
  }
  emit: (phase?: string) => void
  beacon: (token: string, phase?: string) => void
}

function newTurnId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID().replace(/-/g, '')
  }
  return `${Date.now().toString(16)}${Math.random().toString(16).slice(2, 10)}`
}

export function createInterviewTurnTrace(sessionId: string): InterviewTurnTrace {
  const turnId = newTurnId()
  const t0 = performance.now()
  const marks = new Map<string, number>([['turn_start', t0]])
  const events: string[] = ['turn_start']
  const spans: LatencySpans = {}

  const mark = (name: string) => {
    marks.set(name, performance.now())
    events.push(name)
  }

  const measure = (spanKey: string, startMark: string, endMark?: string): number | null => {
    const start = marks.get(startMark)
    if (start == null) {
      spans[spanKey] = null
      return null
    }
    const end = endMark ? marks.get(endMark) : performance.now()
    if (end == null) {
      spans[spanKey] = null
      return null
    }
    const ms = Math.round((end - start) * 1000) / 1000
    spans[spanKey] = ms
    return ms
  }

  const setSpan = (key: string, valueMs: number | null) => {
    spans[key] = valueMs == null ? null : Math.round(valueMs * 1000) / 1000
  }

  const unavailable = (key: string) => {
    spans[key] = null
  }

  const elapsedMs = () => Math.round((performance.now() - t0) * 1000) / 1000

  const payload = (phase = 'client_turn') => ({
    turn_id: turnId,
    session_id: sessionId,
    phase,
    spans: { ...spans },
    events: [...events],
  })

  const emit = (phase = 'client_turn') => {
    // Structured browser log — no PII / audio / transcript.
    // eslint-disable-next-line no-console
    console.info(JSON.stringify({ event: 'interview_latency', ...payload(phase) }))
  }

  const beacon = (token: string, phase = 'client_beacon') => {
    emit(phase)
    void requestJson(
      `/api/interview/room/sessions/${sessionId}/ai/latency-beacon`,
      jsonRequest('POST', payload(phase)),
      token,
      8_000,
    ).catch(() => {
      /* best-effort; never block the interview */
    })
  }

  return {
    turnId,
    sessionId,
    events,
    spans,
    mark,
    measure,
    setSpan,
    unavailable,
    elapsedMs,
    payload: () => payload(),
    emit,
    beacon,
  }
}

export function turnHeaders(turn: InterviewTurnTrace | null | undefined, extra?: HeadersInit): Headers {
  const headers = new Headers(extra)
  if (turn?.turnId) headers.set(TURN_ID_HEADER, turn.turnId)
  return headers
}
