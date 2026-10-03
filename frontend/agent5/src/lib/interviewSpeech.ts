import { ApiError, requestBlob } from './api'

export type AudioPlayerRef = { current: HTMLAudioElement | null }

/** Play TTS from backend (Edge/Parler) with browser speechSynthesis fallback. */
export async function playSpokenText(
  sessionId: string,
  token: string,
  text: string,
  onSpeakingChange?: (speaking: boolean) => void,
  playerRef?: AudioPlayerRef,
): Promise<void> {
  const trimmed = text.trim()
  if (!trimmed) return

  onSpeakingChange?.(true)
  try {
    const audio = await requestBlob(
      `/api/interview/room/sessions/${sessionId}/ai/speak`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: trimmed }),
      },
      token,
      120_000,
    )
    await playAudioBlob(audio, playerRef)
    return
  } catch (error) {
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
): Promise<void> {
  onSpeakingChange?.(true)
  try {
    const payload: { question_id?: string; text?: string } = {}
    if (questionId) payload.question_id = questionId
    if (questionText?.trim()) payload.text = questionText.trim()
    const audio = await requestBlob(
      `/api/interview/room/sessions/${sessionId}/ai/speak`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
      token,
      120_000,
    )
    await playAudioBlob(audio, playerRef)
  } catch (error) {
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
  try {
    window.speechSynthesis?.cancel()
  } catch { /* ignore */ }
  const player = playerRef?.current as (HTMLAudioElement & { __agent5Resolve?: () => void }) | null
  if (player) {
    try {
      player.pause()
      player.currentTime = 0
      player.__agent5Resolve?.()
    } catch { /* ignore */ }
    if (playerRef) playerRef.current = null
  }
  onSpeakingChange?.(false)
}

function playAudioBlob(blob: Blob, playerRef?: AudioPlayerRef): Promise<void> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob)
    const player = new Audio(url) as HTMLAudioElement & { __agent5Resolve?: () => void }
    let settled = false
    const finish = () => {
      if (settled) return
      settled = true
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

export type SilenceMonitor = { stop: () => void }

/** Auto-submit when the candidate stops speaking for a short pause. */
export function startSilenceMonitor(
  stream: MediaStream,
  onSilence: () => void,
  options?: { silenceMs?: number; threshold?: number },
): SilenceMonitor {
  const silenceMs = options?.silenceMs ?? 2400
  const threshold = options?.threshold ?? 0.018
  const ctx = new AudioContext()
  const analyser = ctx.createAnalyser()
  analyser.fftSize = 2048
  const source = ctx.createMediaStreamSource(new MediaStream(stream.getAudioTracks()))
  source.connect(analyser)

  let speechDetected = false
  let silenceStart = 0
  let frameId = 0
  let stopped = false

  const tick = () => {
    if (stopped) return
    const data = new Uint8Array(analyser.fftSize)
    analyser.getByteTimeDomainData(data)
    let sum = 0
    for (const value of data) {
      const sample = (value - 128) / 128
      sum += sample * sample
    }
    const rms = Math.sqrt(sum / data.length)
    const now = Date.now()
    if (rms > threshold) {
      speechDetected = true
      silenceStart = 0
    } else if (speechDetected) {
      if (!silenceStart) silenceStart = now
      else if (now - silenceStart >= silenceMs) {
        stopped = true
        onSilence()
        return
      }
    }
    frameId = window.requestAnimationFrame(tick)
  }

  frameId = window.requestAnimationFrame(tick)

  return {
    stop: () => {
      stopped = true
      window.cancelAnimationFrame(frameId)
      source.disconnect()
      void ctx.close().catch(() => undefined)
    },
  }
}
