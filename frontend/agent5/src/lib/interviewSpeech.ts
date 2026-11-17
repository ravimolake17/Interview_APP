import { ApiError, requestBlobDetailed, resolveApiUrl } from './api'
import { TTS_ROLE_HEADER, turnHeaders, type InterviewTurnTrace } from './interviewLatency'

export type AudioPlayerRef = {
  current: HTMLAudioElement | null
  /** Bumped by stopSpokenAudio so in-flight fetch/play can abort before starting. */
  generation?: number
}

export type SpeakOptions = {
  turn?: InterviewTurnTrace | null
  /** ack | question | combined — maps to server X-Interview-Tts-Role for metric naming */
  ttsRole?: 'ack' | 'question' | 'combined'
  /** Prefer Azure MP3 streaming when available; falls back to batch /ai/speak. */
  preferStream?: boolean
}

function mseSupportsMp3(): boolean {
  try {
    return typeof MediaSource !== 'undefined'
      && MediaSource.isTypeSupported('audio/mpeg')
  } catch {
    return false
  }
}

function ttsStillCurrent(playerRef: AudioPlayerRef | undefined, generation: number): boolean {
  return !playerRef || (playerRef.generation ?? 0) === generation
}

/** Play TTS from backend with optional early MP3 streaming + batch fallback. */
export async function playSpokenText(
  sessionId: string,
  token: string,
  text: string,
  onSpeakingChange?: (speaking: boolean) => void,
  playerRef?: AudioPlayerRef,
  options?: SpeakOptions,
): Promise<void> {
  const trimmed = text.trim()
  if (!trimmed) return

  onSpeakingChange?.(true)
  const turn = options?.turn
  const ttsRole = options?.ttsRole || 'question'
  stopSpokenAudio(playerRef)
  const generation = playerRef?.generation ?? 0
  try {
    turn?.mark(ttsRole === 'ack' ? 'acknowledgement_tts_request_start' : 'question_tts_request_start')
    if (options?.preferStream !== false && mseSupportsMp3()) {
      try {
        if (!ttsStillCurrent(playerRef, generation)) return
        await playStreamingSpeak(sessionId, token, { text: trimmed }, playerRef, turn, ttsRole)
        return
      } catch (error) {
        console.warn('Streaming TTS unavailable, using batch speak', error)
      }
    }
    if (!ttsStillCurrent(playerRef, generation)) return
    const headers = turnHeaders(turn, { 'Content-Type': 'application/json' })
    headers.set(TTS_ROLE_HEADER, ttsRole === 'combined' ? 'question' : ttsRole)
    const { blob, headers: responseHeaders, downloadMs } = await requestBlobDetailed(
      `/api/interview/room/sessions/${sessionId}/ai/speak`,
      {
        method: 'POST',
        headers,
        body: JSON.stringify({ text: trimmed }),
      },
      token,
      120_000,
    )
    if (!ttsStillCurrent(playerRef, generation)) return
    turn?.setSpan('audio_download_ms', downloadMs)
    turn?.setSpan(
      ttsRole === 'ack' ? 'acknowledgement_tts_ms' : 'question_tts_ms',
      downloadMs,
    )
    const cached = responseHeaders.get('X-TTS-Cached')
    if (cached != null) turn?.setSpan('tts_cache_hit', cached === '1' ? 1 : 0)
    const ratio = responseHeaders.get('X-TTS-Cache-Hit-Ratio')
    if (ratio) turn?.setSpan('tts_cache_hit_ratio', Number(ratio))
    turn?.mark('audio_download_complete')
    await playAudioBlob(blob, playerRef, turn)
    return
  } catch (error) {
    if (!ttsStillCurrent(playerRef, generation)) return
    const detail = error instanceof ApiError ? error.message : String(error)
    console.warn('Server TTS failed, using browser voice fallback:', detail)
    await playBrowserSpeech(trimmed, onSpeakingChange)
  } finally {
    onSpeakingChange?.(false)
    if (playerRef) playerRef.current = null
  }
}

export async function playQuestionAudio(
  sessionId: string,
  token: string,
  questionId: string | undefined,
  questionText: string | undefined,
  onSpeakingChange?: (speaking: boolean) => void,
  playerRef?: AudioPlayerRef,
  options?: SpeakOptions,
): Promise<void> {
  onSpeakingChange?.(true)
  const turn = options?.turn
  stopSpokenAudio(playerRef)
  const generation = playerRef?.generation ?? 0
  try {
    turn?.mark('question_tts_request_start')
    const payload: { question_id?: string; text?: string } = {}
    if (questionId) payload.question_id = questionId
    if (questionText?.trim()) payload.text = questionText.trim()

    // Bank questions: prefer batch /ai/speak so Redis/disk cache can return instantly.
    if (!ttsStillCurrent(playerRef, generation)) return
    const headers = turnHeaders(turn, { 'Content-Type': 'application/json' })
    headers.set(TTS_ROLE_HEADER, 'question')
    const { blob, headers: responseHeaders, downloadMs } = await requestBlobDetailed(
      `/api/interview/room/sessions/${sessionId}/ai/speak`,
      {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      },
      token,
      120_000,
    )
    if (!ttsStillCurrent(playerRef, generation)) return
    turn?.setSpan('audio_download_ms', downloadMs)
    turn?.setSpan('question_tts_ms', downloadMs)
    const cached = responseHeaders.get('X-TTS-Cached')
    if (cached != null) turn?.setSpan('tts_cache_hit', cached === '1' ? 1 : 0)
    const ratio = responseHeaders.get('X-TTS-Cache-Hit-Ratio')
    if (ratio) turn?.setSpan('tts_cache_hit_ratio', Number(ratio))
    turn?.mark('audio_download_complete')
    await playAudioBlob(blob, playerRef, turn)
  } catch (error) {
    if (!ttsStillCurrent(playerRef, generation)) return
    const fallback = (questionText || '').trim()
    if (!fallback) throw error
    console.warn('Question TTS failed, using browser voice fallback', error)
    await playBrowserSpeech(fallback, onSpeakingChange)
  } finally {
    onSpeakingChange?.(false)
    if (playerRef) playerRef.current = null
  }
}

export function stopSpokenAudio(playerRef?: AudioPlayerRef, onSpeakingChange?: (speaking: boolean) => void): void {
  if (playerRef) {
    playerRef.generation = (playerRef.generation ?? 0) + 1
  }
  try {
    window.speechSynthesis?.cancel()
  } catch { /* ignore */ }
  const player = playerRef?.current as (HTMLAudioElement & { __agent5Resolve?: () => void; __agent5Abort?: AbortController }) | null
  if (player) {
    try {
      player.__agent5Abort?.abort()
      player.pause()
      player.currentTime = 0
      player.__agent5Resolve?.()
    } catch { /* ignore */ }
    if (playerRef) playerRef.current = null
  }
  onSpeakingChange?.(false)
}

async function playStreamingSpeak(
  sessionId: string,
  token: string,
  body: { text?: string; question_id?: string },
  playerRef?: AudioPlayerRef,
  turn?: InterviewTurnTrace | null,
  ttsRole: SpeakOptions['ttsRole'] = 'question',
): Promise<void> {
  const headers = turnHeaders(turn, { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` })
  headers.set(TTS_ROLE_HEADER, ttsRole === 'combined' ? 'question' : (ttsRole || 'question'))
  const t0 = performance.now()
  const response = await fetch(
    resolveApiUrl(`/api/interview/room/sessions/${sessionId}/ai/speak-stream`),
    { method: 'POST', headers, body: JSON.stringify(body) },
  )
  if (!response.ok) {
    throw new ApiError(response.status, await response.text())
  }
  const cached = response.headers.get('X-TTS-Cached') === '1'
  const streamFlag = response.headers.get('X-TTS-Stream')
  // Cached complete WAV/audio from speak-stream peek — play as blob.
  if (cached || streamFlag === '0' || !response.body || !mseSupportsMp3()) {
    const blob = await response.blob()
    turn?.setSpan('audio_download_ms', Math.round((performance.now() - t0) * 1000) / 1000)
    turn?.setSpan('tts_cache_hit', cached ? 1 : 0)
    turn?.mark('audio_download_complete')
    await playAudioBlob(blob, playerRef, turn)
    return
  }

  await playMpegStream(response, playerRef, turn, t0, ttsRole)
}

function playMpegStream(
  response: Response,
  playerRef: AudioPlayerRef | undefined,
  turn: InterviewTurnTrace | null | undefined,
  startedAt: number,
  ttsRole: SpeakOptions['ttsRole'],
): Promise<void> {
  return new Promise((resolve, reject) => {
    const mediaSource = new MediaSource()
    const url = URL.createObjectURL(mediaSource)
    const player = new Audio(url) as HTMLAudioElement & {
      __agent5Resolve?: () => void
      __agent5Abort?: AbortController
    }
    const abort = new AbortController()
    let settled = false
    let firstChunkAt: number | null = null
    const finish = (error?: Error) => {
      if (settled) return
      settled = true
      try { mediaSource.endOfStream() } catch { /* ignore */ }
      URL.revokeObjectURL(url)
      delete player.__agent5Resolve
      delete player.__agent5Abort
      if (playerRef && playerRef.current === player) playerRef.current = null
      if (error) reject(error)
      else resolve()
    }
    player.__agent5Resolve = () => finish()
    player.__agent5Abort = abort
    if (playerRef) playerRef.current = player
    player.onended = () => {
      turn?.mark('audio_playback_end')
      finish()
    }
    player.onerror = () => finish(new Error('Streaming audio playback failed'))
    player.onplaying = () => {
      turn?.mark('audio_playback_start')
      if (firstChunkAt != null) {
        turn?.setSpan('playback_start_delay_ms', Math.round((performance.now() - firstChunkAt) * 1000) / 1000)
      }
      turn?.measure('total_turn_latency_ms', 'candidate_speech_end')
    }

    mediaSource.addEventListener('sourceopen', () => {
      void (async () => {
        try {
          const sourceBuffer = mediaSource.addSourceBuffer('audio/mpeg')
          const reader = response.body!.getReader()
          const append = (chunk: Uint8Array) => new Promise<void>((res, rej) => {
            const onUpdate = () => {
              sourceBuffer.removeEventListener('updateend', onUpdate)
              sourceBuffer.removeEventListener('error', onErr)
              res()
            }
            const onErr = () => {
              sourceBuffer.removeEventListener('updateend', onUpdate)
              sourceBuffer.removeEventListener('error', onErr)
              rej(new Error('SourceBuffer append failed'))
            }
            sourceBuffer.addEventListener('updateend', onUpdate)
            sourceBuffer.addEventListener('error', onErr)
            sourceBuffer.appendBuffer(chunk as BufferSource)
          })

          while (!abort.signal.aborted) {
            const { done, value } = await reader.read()
            if (done) break
            if (!value?.byteLength) continue
            if (firstChunkAt == null) {
              firstChunkAt = performance.now()
              turn?.setSpan('tts_time_to_first_audio_ms', Math.round((firstChunkAt - startedAt) * 1000) / 1000)
              turn?.mark('first_audio_chunk')
              void player.play().catch(() => undefined)
            }
            await append(value)
          }
          turn?.setSpan(
            ttsRole === 'ack' ? 'acknowledgement_tts_ms' : 'question_tts_ms',
            Math.round((performance.now() - startedAt) * 1000) / 1000,
          )
          turn?.setSpan('tts_cache_hit', 0)
          if (mediaSource.readyState === 'open') {
            try { mediaSource.endOfStream() } catch { /* ignore */ }
          }
          if (player.paused) await player.play()
        } catch (error) {
          finish(error instanceof Error ? error : new Error(String(error)))
        }
      })()
    }, { once: true })
  })
}

function playAudioBlob(blob: Blob, playerRef?: AudioPlayerRef, turn?: InterviewTurnTrace | null): Promise<void> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob)
    const player = new Audio(url) as HTMLAudioElement & { __agent5Resolve?: () => void }
    let settled = false
    const downloadCompleteAt = performance.now()
    const finish = () => {
      if (settled) return
      settled = true
      turn?.mark('audio_playback_end')
      URL.revokeObjectURL(url)
      delete player.__agent5Resolve
      if (playerRef && playerRef.current === player) playerRef.current = null
      resolve()
    }
    player.__agent5Resolve = finish
    if (playerRef) playerRef.current = player
    player.onended = () => finish()
    player.onerror = () => {
      if (settled) return
      settled = true
      URL.revokeObjectURL(url)
      delete player.__agent5Resolve
      if (playerRef && playerRef.current === player) playerRef.current = null
      reject(new Error('Audio playback failed'))
    }
    player.onplaying = () => {
      turn?.mark('audio_playback_start')
      turn?.setSpan('playback_start_delay_ms', Math.round((performance.now() - downloadCompleteAt) * 1000) / 1000)
      turn?.measure('total_turn_latency_ms', 'candidate_speech_end')
    }
    void player.play().catch((error) => {
      if (settled) return
      settled = true
      URL.revokeObjectURL(url)
      delete player.__agent5Resolve
      if (playerRef && playerRef.current === player) playerRef.current = null
      reject(error)
    })
  })
}

function playBrowserSpeech(text: string, onSpeakingChange?: (speaking: boolean) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!('speechSynthesis' in window)) {
      reject(new Error('Speech synthesis is not available in this browser'))
      return
    }
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'en-IN'
    utterance.rate = 0.95
    let settled = false
    let watchdog = 0
    const finish = (ok: boolean, error?: Error) => {
      if (settled) return
      settled = true
      window.clearTimeout(watchdog)
      onSpeakingChange?.(false)
      if (ok) resolve()
      else reject(error || new Error('Browser speech synthesis failed'))
    }
    utterance.onstart = () => onSpeakingChange?.(true)
    utterance.onend = () => finish(true)
    utterance.onerror = () => finish(true)
    const watchdogMs = Math.min(60_000, Math.max(8_000, text.split(/\s+/).length * 700))
    watchdog = window.setTimeout(() => finish(true), watchdogMs)
    window.speechSynthesis.speak(utterance)
  })
}

export type SilenceMonitor = {
  stop: () => void
  /** Signal speech from another source (e.g. STT partial text) when mic energy is too low to detect. */
  markSpeech: () => void
  /** Milliseconds since speech was last detected (Infinity if never). */
  msSinceSpeech: () => number
}

export type SilenceMonitorMeta = {
  /** Monotonic ms from last speech energy to silence callback. */
  silenceWaitMs: number
  reason: 'silence' | 'no_speech'
}

/** Auto-submit when the candidate stops speaking for a pause (not mid-thought). */
export function startSilenceMonitor(
  stream: MediaStream,
  onSilence: (meta?: SilenceMonitorMeta) => void,
  options?: {
    silenceMs?: number
    threshold?: number
    minSpeechMs?: number
    /** If the candidate never speaks, call onNoSpeech after this many ms (default 10s). */
    noSpeechTimeoutMs?: number
    onNoSpeech?: (meta?: SilenceMonitorMeta) => void
  },
): SilenceMonitor {
  const silenceMs = options?.silenceMs ?? 2500
  const minThreshold = options?.threshold ?? 0.006
  const minSpeechMs = options?.minSpeechMs ?? 1200
  const noSpeechTimeoutMs = options?.noSpeechTimeoutMs ?? 10_000
  const onNoSpeech = options?.onNoSpeech
  const startedAt = performance.now()
  const ctx = new AudioContext()
  void ctx.resume().catch(() => undefined)
  const analyser = ctx.createAnalyser()
  analyser.fftSize = 2048
  const source = ctx.createMediaStreamSource(new MediaStream(stream.getAudioTracks()))
  source.connect(analyser)

  let speechDetected = false
  let speechStartedAt = 0
  let speechAccumulatedMs = 0
  let lastSpeechAt = 0
  let silenceStart = 0
  let noiseFloor = minThreshold / 2
  let speechPeak = minThreshold
  let externalSpeechAt = 0
  const calibratedUntil = performance.now() + 700
  let stopped = false

  const finish = (kind: 'silence' | 'no_speech') => {
    if (stopped) return
    stopped = true
    const now = performance.now()
    const silenceWaitMs = kind === 'silence'
      ? Math.round((now - (silenceStart || lastSpeechAt || now)) * 1000) / 1000
      : Math.round((now - startedAt) * 1000) / 1000
    const meta: SilenceMonitorMeta = { silenceWaitMs, reason: kind }
    if (kind === 'no_speech' && onNoSpeech) onNoSpeech(meta)
    else onSilence(meta)
  }

  const binHz = ctx.sampleRate / analyser.fftSize
  const bandLo = Math.max(1, Math.floor(80 / binHz))
  const voiceLo = Math.floor(300 / binHz)
  const voiceHi = Math.ceil(3400 / binHz)
  const bandHi = Math.min(analyser.frequencyBinCount - 1, Math.ceil(8000 / binHz))
  const timeData = new Float32Array(analyser.fftSize)
  const freqData = new Float32Array(analyser.frequencyBinCount)

  /** Share of 80–8000 Hz energy that falls in the 300–3400 Hz voice band (fans/hum score low). */
  const voiceBandRatio = (): number => {
    analyser.getFloatFrequencyData(freqData)
    let voice = 0
    let total = 0
    for (let i = bandLo; i <= bandHi; i += 1) {
      const db = freqData[i]
      if (!Number.isFinite(db)) continue
      const power = 10 ** (db / 10)
      total += power
      if (i >= voiceLo && i <= voiceHi) voice += power
    }
    return total > 0 ? voice / total : 0
  }

  const tick = () => {
    if (stopped) return
    analyser.getFloatTimeDomainData(timeData)
    let sum = 0
    for (const sample of timeData) sum += sample * sample
    const rms = Math.sqrt(sum / timeData.length)
    const voiceRatio = voiceBandRatio()
    const now = performance.now()

    if (!speechDetected && now - startedAt >= noSpeechTimeoutMs) {
      finish('no_speech')
      return
    }

    if (now < calibratedUntil || rms < noiseFloor * 1.35) {
      noiseFloor = Math.min(0.03, Math.max(0.001, noiseFloor * 0.92 + rms * 0.08))
    }

    const speechGate = Math.max(minThreshold, noiseFloor * 2.2)
    const quietGate = Math.max(noiseFloor * 1.5, speechPeak * 0.3, minThreshold * 0.6)
    // STT text arriving recently means the candidate is talking even if the mic level is low.
    const externallySpeaking = externalSpeechAt > 0 && now - externalSpeechAt < 1200
    const voiceLike = voiceRatio >= 0.45
    const isSpeech = (rms >= speechGate && voiceLike) || externallySpeaking

    if (isSpeech) {
      if (!speechDetected) speechStartedAt = now
      speechDetected = true
      speechPeak = Math.max(speechPeak * 0.97, rms)
      if (lastSpeechAt) speechAccumulatedMs += Math.min(80, now - lastSpeechAt)
      lastSpeechAt = now
      silenceStart = 0
    } else if (speechDetected) {
      speechPeak = Math.max(speechPeak * 0.995, noiseFloor)
      const spokenLongEnough =
        speechAccumulatedMs >= minSpeechMs || (speechStartedAt > 0 && now - speechStartedAt >= minSpeechMs)
      // Steady non-voice noise above the level gate must not keep the turn open forever.
      const isQuiet = !externallySpeaking && (rms <= quietGate || voiceRatio < 0.3)
      if (!spokenLongEnough || !isQuiet) {
        silenceStart = 0
      } else if (!silenceStart) {
        silenceStart = now
      } else if (now - silenceStart >= silenceMs) {
        finish('silence')
        return
      }
    }
  }

  // setInterval instead of requestAnimationFrame: rAF pauses when the window is occluded.
  const timer = window.setInterval(() => {
    if (stopped) window.clearInterval(timer)
    else tick()
  }, 40)

  return {
    stop: () => {
      stopped = true
      window.clearInterval(timer)
      source.disconnect()
      void ctx.close().catch(() => undefined)
    },
    markSpeech: () => {
      if (stopped) return
      const now = performance.now()
      externalSpeechAt = now
      if (!speechDetected) {
        speechDetected = true
        speechStartedAt = now
      }
      lastSpeechAt = now
      silenceStart = 0
    },
    msSinceSpeech: () => (lastSpeechAt ? performance.now() - lastSpeechAt : Number.POSITIVE_INFINITY),
  }
}
