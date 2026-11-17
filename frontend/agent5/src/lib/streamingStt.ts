/**
 * Real-time interview STT over WebSocket.
 * Sends 16 kHz mono PCM s16le — Azure PushAudioInputStream does not accept WebM/Opus.
 */

import { resolveApiUrl } from './api'
import type { InterviewTurnTrace } from './interviewLatency'

export type SttModeInfo = {
  interview_stt_mode: string
  streaming_available: boolean
  effective_mode: 'batch' | 'streaming'
  sample_rate: number
  format: string
  channels: number
  end_silence_ms: number
  finalization_timeout_ms: number
}

export type StreamingFinalResult = {
  ok: boolean
  text: string
  raw_text?: string
  correction_status?: string | null
  correction_tier?: string | null
  needs_llm_correction?: boolean
  metrics?: Record<string, number | null | undefined>
  error?: string | null
}

export type StreamingSttHandlers = {
  onPartial?: (text: string) => void
  onSegment?: (text: string) => void
  onSpeechEnd?: () => void
  /** Azure service-side voice activity: 'start' when speech begins, 'end' at a speech boundary. */
  onVad?: (state: 'start' | 'end') => void
  onError?: (message: string, code?: string) => void
  onReady?: () => void
}

const TARGET_RATE = 16_000

function wsUrl(sessionId: string, token: string): string {
  const path = resolveApiUrl(`/api/interview/room/sessions/${sessionId}/ai/stt-stream`)
  const url = new URL(path, window.location.origin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.searchParams.set('token', token)
  return url.toString()
}

function floatSampleToInt16(sample: number): number {
  const clipped = Math.max(-1, Math.min(1, sample))
  return clipped < 0 ? clipped * 0x8000 : clipped * 0x7fff
}

/**
 * Resample Float32 PCM from AudioContext rate to 16 kHz Int16 LE.
 * Uses linear interpolation (better than nearest-neighbor for speech).
 */
export function floatToPcm16k(input: Float32Array, inputRate: number): ArrayBuffer {
  if (!input.length) return new ArrayBuffer(0)
  if (!Number.isFinite(inputRate) || inputRate <= 0) return new ArrayBuffer(0)

  if (Math.abs(inputRate - TARGET_RATE) < 0.5) {
    const out = new Int16Array(input.length)
    for (let i = 0; i < input.length; i += 1) {
      out[i] = floatSampleToInt16(input[i] ?? 0)
    }
    return out.buffer
  }

  const ratio = inputRate / TARGET_RATE
  const outLen = Math.max(1, Math.floor(input.length / ratio))
  const out = new Int16Array(outLen)
  const last = input.length - 1
  for (let i = 0; i < outLen; i += 1) {
    const srcIndex = i * ratio
    const i0 = Math.min(last, Math.floor(srcIndex))
    const i1 = Math.min(last, i0 + 1)
    const frac = srcIndex - i0
    const sample = (input[i0] ?? 0) * (1 - frac) + (input[i1] ?? 0) * frac
    out[i] = floatSampleToInt16(sample)
  }
  return out.buffer
}

export async function fetchSttMode(sessionId: string, token: string): Promise<SttModeInfo> {
  const response = await fetch(
    resolveApiUrl(`/api/interview/room/sessions/${sessionId}/ai/stt-mode`),
    { headers: { Authorization: `Bearer ${token}` } },
  )
  if (!response.ok) {
    return {
      interview_stt_mode: 'batch',
      streaming_available: false,
      effective_mode: 'batch',
      sample_rate: TARGET_RATE,
      format: 'pcm_s16le',
      channels: 1,
      end_silence_ms: 2500,
      finalization_timeout_ms: 5000,
    }
  }
  const data = await response.json()
  const effective = String(data.effective_mode || data.interview_stt_mode || 'batch').toLowerCase()
  return {
    interview_stt_mode: String(data.interview_stt_mode || 'batch'),
    streaming_available: Boolean(data.streaming_available),
    effective_mode: effective === 'streaming' ? 'streaming' : 'batch',
    sample_rate: Number(data.sample_rate || TARGET_RATE),
    format: String(data.format || 'pcm_s16le'),
    channels: Number(data.channels || 1),
    end_silence_ms: Number(data.end_silence_ms || 2500),
    finalization_timeout_ms: Number(data.finalization_timeout_ms || 5000),
  }
}

export class StreamingSttClient {
  private socket: WebSocket | null = null
  private audioCtx: AudioContext | null = null
  private worklet: AudioWorkletNode | ScriptProcessorNode | null = null
  private source: MediaStreamAudioSourceNode | null = null
  private gain: GainNode | null = null
  private monitorStream: MediaStream | null = null
  private finalWaiters: Array<(result: StreamingFinalResult) => void> = []
  private ready = false
  private closed = false
  private reconnectAttempts = 0
  private framesSent = 0
  private startedAt = 0
  private firstFrameCapturedAt = 0
  private firstFrameSentAt = 0
  private inputSampleRate = 0

  constructor(
    private readonly sessionId: string,
    private readonly token: string,
    private readonly handlers: StreamingSttHandlers = {},
  ) {}

  get captureMetrics() {
    return {
      framesSent: this.framesSent,
      inputSampleRate: this.inputSampleRate,
      firstFrameCapturedAt: this.firstFrameCapturedAt,
      firstFrameSentAt: this.firstFrameSentAt,
      startedAt: this.startedAt,
    }
  }

  get isReady(): boolean {
    return this.ready && this.socket?.readyState === WebSocket.OPEN
  }

  async connect(): Promise<void> {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return
    }
    await new Promise<void>((resolve, reject) => {
      const socket = new WebSocket(wsUrl(this.sessionId, this.token))
      socket.binaryType = 'arraybuffer'
      this.socket = socket
      const timer = window.setTimeout(() => {
        reject(new Error('STT WebSocket connect timed out'))
        try { socket.close() } catch { /* ignore */ }
      }, 12_000)
      socket.onopen = () => {
        window.clearTimeout(timer)
        this.reconnectAttempts = 0
        resolve()
      }
      socket.onerror = () => {
        window.clearTimeout(timer)
        reject(new Error('STT WebSocket failed to connect'))
      }
      socket.onclose = () => {
        this.ready = false
        if (!this.closed && this.reconnectAttempts < 2) {
          this.reconnectAttempts += 1
          window.setTimeout(() => {
            void this.connect().catch(() => undefined)
          }, 800 * this.reconnectAttempts)
        }
      }
      socket.onmessage = (event) => this.onMessage(event)
    })
  }

  private onMessage(event: MessageEvent) {
    if (typeof event.data !== 'string') return
    let data: Record<string, unknown>
    try {
      data = JSON.parse(event.data)
    } catch {
      return
    }
    const type = String(data.type || '')
    if (type === 'ready') {
      this.ready = true
      this.handlers.onReady?.()
      return
    }
    if (type === 'partial') {
      const text = String(data.text || '')
      if (text) this.handlers.onPartial?.(text)
      return
    }
    if (type === 'segment') {
      const text = String(data.text || '')
      if (text) this.handlers.onSegment?.(text)
      return
    }
    if (type === 'speech_end') {
      this.handlers.onSpeechEnd?.()
      return
    }
    if (type === 'vad') {
      const state = String(data.state || '')
      if (state === 'start' || state === 'end') this.handlers.onVad?.(state)
      return
    }
    if (type === 'final') {
      const result: StreamingFinalResult = {
        ok: Boolean(data.ok),
        text: String(data.text || ''),
        raw_text: data.raw_text != null ? String(data.raw_text) : undefined,
        correction_status: data.correction_status != null ? String(data.correction_status) : null,
        correction_tier: data.correction_tier != null ? String(data.correction_tier) : null,
        needs_llm_correction: Boolean(data.needs_llm_correction),
        metrics: (data.metrics as StreamingFinalResult['metrics']) || undefined,
        error: data.error != null ? String(data.error) : null,
      }
      const waiters = this.finalWaiters.splice(0, this.finalWaiters.length)
      waiters.forEach((resolve) => resolve(result))
      return
    }
    if (type === 'error') {
      const message = String(data.message || 'Streaming STT error')
      this.handlers.onError?.(message, data.code != null ? String(data.code) : undefined)
    }
  }

  async startTurn(params: {
    mediaStream: MediaStream
    questionId?: string | null
    turn?: InterviewTurnTrace | null
  }): Promise<void> {
    this.closed = false
    await this.connect()
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      throw new Error('STT WebSocket is not open')
    }
    this.startedAt = performance.now()
    this.framesSent = 0
    this.firstFrameCapturedAt = 0
    this.firstFrameSentAt = 0
    params.turn?.mark('mic_capture_started')
    this.socket.send(JSON.stringify({
      type: 'start',
      question_id: params.questionId || null,
      turn_id: params.turn?.turnId || null,
    }))
    // Wait briefly for Azure ready (recognizer start).
    const readyDeadline = performance.now() + 8_000
    while (!this.ready && performance.now() < readyDeadline) {
      await new Promise((r) => window.setTimeout(r, 40))
    }
    if (!this.ready) throw new Error('Streaming speech recognition did not become ready')

    const AudioConstructor = window.AudioContext || window.webkitAudioContext
    if (!AudioConstructor) throw new Error('Web Audio is not supported')
    const context = new AudioConstructor()
    this.audioCtx = context
    // Suspended contexts produce silent frames — resume before capturing.
    if (context.state === 'suspended') await context.resume()
    this.monitorStream = new MediaStream(params.mediaStream.getAudioTracks().map((t) => t.clone()))
    const liveTracks = this.monitorStream.getAudioTracks()
    if (!liveTracks.length || liveTracks.every((t) => t.muted || t.readyState !== 'live')) {
      throw new Error('Microphone track is not live for streaming STT')
    }
    this.source = context.createMediaStreamSource(this.monitorStream)
    const sampleRate = context.sampleRate
    this.inputSampleRate = sampleRate
    params.turn?.setSpan('audio_input_sample_rate', sampleRate)

    const sendPcm = (block: Float32Array) => {
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN || this.closed) return
      if (!this.firstFrameCapturedAt) {
        this.firstFrameCapturedAt = performance.now()
        params.turn?.mark('first_audio_frame_captured')
      }
      const pcm = floatToPcm16k(block, sampleRate)
      if (!pcm.byteLength) return
      this.socket.send(pcm)
      this.framesSent += 1
      if (!this.firstFrameSentAt) {
        this.firstFrameSentAt = performance.now()
        params.turn?.mark('first_audio_frame_sent')
      }
      params.turn?.setSpan('audio_stream_frames', this.framesSent)
    }

    if (context.audioWorklet && window.AudioWorkletNode) {
      await context.audioWorklet.addModule(`${import.meta.env.BASE_URL}pcm-worklet.js`)
      const node = new AudioWorkletNode(context, 'agent5-pcm-processor')
      node.port.onmessage = (event: MessageEvent<Float32Array>) => {
        if (event.data?.length) sendPcm(event.data)
      }
      this.worklet = node
    } else {
      const node = context.createScriptProcessor(4096, 1, 1)
      node.onaudioprocess = (event) => {
        sendPcm(event.inputBuffer.getChannelData(0))
      }
      this.worklet = node
    }
    this.gain = context.createGain()
    this.gain.gain.value = 0
    this.source.connect(this.worklet)
    this.worklet.connect(this.gain)
    this.gain.connect(context.destination)
    if (context.state === 'suspended') await context.resume()
    params.turn?.mark('stt_stream_started')
  }

  async stopTurn(turn?: InterviewTurnTrace | null): Promise<StreamingFinalResult> {
    turn?.mark('stt_stream_stop_requested')
    turn?.mark('last_audio_frame_sent')
    this.stopMicGraph()
    const socket = this.socket
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return { ok: false, text: '', error: 'socket_closed' }
    }
    const resultPromise = new Promise<StreamingFinalResult>((resolve) => {
      this.finalWaiters.push(resolve)
      window.setTimeout(() => {
        resolve({ ok: false, text: '', error: 'final_timeout' })
      }, 12_000)
    })
    socket.send(JSON.stringify({ type: 'stop' }))
    const result = await resultPromise
    turn?.mark('stt_stream_final_received')
    if (result.metrics?.speech_end_to_final_ms != null) {
      turn?.setSpan('speech_end_to_final_ms', Number(result.metrics.speech_end_to_final_ms))
    }
    if (result.metrics?.partial_first_ms != null) {
      turn?.setSpan('partial_first_ms', Number(result.metrics.partial_first_ms))
    }
    if (result.metrics?.first_final_segment_ms != null) {
      turn?.setSpan('first_final_segment_ms', Number(result.metrics.first_final_segment_ms))
    }
    if (this.startedAt) {
      turn?.setSpan('stt_stream_total_ms', Math.round((performance.now() - this.startedAt) * 1000) / 1000)
    }
    this.ready = false
    return result
  }

  private stopMicGraph() {
    try {
      this.worklet?.disconnect()
    } catch { /* ignore */ }
    try {
      this.source?.disconnect()
    } catch { /* ignore */ }
    try {
      this.gain?.disconnect()
    } catch { /* ignore */ }
    this.worklet = null
    this.source = null
    this.gain = null
    if (this.monitorStream) {
      this.monitorStream.getTracks().forEach((t) => t.stop())
      this.monitorStream = null
    }
    if (this.audioCtx) {
      void this.audioCtx.close().catch(() => undefined)
      this.audioCtx = null
    }
  }

  close() {
    this.closed = true
    this.stopMicGraph()
    try {
      this.socket?.close()
    } catch { /* ignore */ }
    this.socket = null
    this.ready = false
  }
}
