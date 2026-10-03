import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { BrandMark } from '../components/BrandMark'
import { McqPanel } from '../components/McqPanel'
import { MessageBanner } from '../components/MessageBanner'
import { Spinner } from '../components/Spinner'
import { StatusPill } from '../components/StatusPill'
import { Stepper } from '../components/Stepper'
import { TopBar } from '../components/TopBar'
import {
  AddIcon,
  BotIcon,
  CamIcon,
  CamOffIcon,
  FullscreenIcon,
  HangUpIcon,
  MeetFab,
  MicIcon,
  MicOffIcon,
  NextIcon,
  PauseIcon,
  PersonIcon,
  PinIcon,
  PlayIcon,
  SkipIcon,
  SpeakerOffIcon,
} from '../components/MeetIcons'
import { ApiError, jsonRequest, requestBlob, requestJson } from '../lib/api'
import { getChunks, putChunk } from '../lib/idbQueue'
import { flushRecordingQueue } from '../lib/recordingQueue'
import { captureVideoFrame, cloneMediaStream, formatElapsed, mergePcm, pcmToWav, sha256, startMediaRecorder, stopMediaStream, supportedMime } from '../lib/media'
import { LatestQueue } from '../lib/latestQueue'
import { attentionLiveStatus, faceLiveStatus, voiceLiveStatus } from '../lib/liveStatus'
import { evaluateLiveSentence } from '../lib/sentence'
import { isLiveDictationSupported, startLiveDictation } from '../lib/liveDictation'
import { RoomPeerConnection, type WebRtcSignalPayload } from '../lib/roomWebRtc'
import { resolveParticipantRole, readCompanyCodeFromToken } from '../lib/sessionRole'
import { resolveCompanyBrand, setCompanyCode, subscribeCompanyBrand } from '../lib/branding'
import { playQuestionAudio, playSpokenText, startSilenceMonitor, stopSpokenAudio, type AudioPlayerRef, type SilenceMonitor } from '../lib/interviewSpeech'
import type {
  AiInterviewSessionResponse,
  AnalysisResponse,
  CandidatePhase,
  CandidateRegistrationResponse,
  CandidateSessionCredentials,
  FinishResponse,
  McqStateResponse,
  MessageKind,
  SessionStateResponse,
  TabSwitchResponse,
  VerificationResponse,
  VoiceSentenceResponse,
} from '../lib/types'

interface MessageState {
  text: string
  kind: MessageKind
}

interface BiometricState {
  faceEnrolled: boolean
  faceVerified: boolean
  voiceEnrolled: boolean
  voiceVerified: boolean
}

interface DeviceState {
  camera: 'pending' | 'ready' | 'failed'
  microphone: 'pending' | 'ready' | 'failed'
}

interface FinishState {
  title: string
  text: string
}

interface TabVisibilityEpisode {
  episodeId: string
  hiddenStartedAt: string
  hiddenStartedMs: number
  focusLost: boolean
  triggeringEvents: string[]
}

interface AudioWindowJob {
  samples: Float32Array
  sampleRate: number
  windowStartMs: number
  windowEndMs: number
  sequenceNumber: number
  segmentId: string
}

const FRAME_REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_AGENT5_FRAME_REQUEST_TIMEOUT_MS ?? 8_000)
const FRAME_INTERVAL_MS = Math.max(500, Number(import.meta.env.VITE_AGENT5_FRAME_INTERVAL_MS ?? 750))
const AUDIO_REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_AGENT5_AUDIO_REQUEST_TIMEOUT_MS ?? 25_000)
const TAB_MIN_HIDDEN_MS = Math.max(250, Number(import.meta.env.VITE_AGENT5_TAB_MIN_HIDDEN_MS ?? 350))

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && typeof error.detail === 'object' && error.detail !== null) {
    const detail = error.detail as Record<string, unknown>
    if (typeof detail.message === 'string') {
      const missing = Array.isArray(detail.missing) ? ` Missing: ${detail.missing.join(', ')}.` : ''
      return `${detail.message}.${missing}`
    }
  }
  return error instanceof Error ? error.message : String(error)
}

function terminationCopy(reason: string | null | undefined): string {
  const key = String(reason || '').trim()
  if (key === 'repeated_tab_switch') {
    return 'the interview window was left more than once'
  }
  if (!key) return 'the proctoring system ended the session'
  return key.replaceAll('_', ' ')
}

function isMcqActive(mcq: McqStateResponse | null | undefined): boolean {
  const status = String(mcq?.status || '')
  return status === 'pending' || status === 'in_progress'
}

function isMcqDone(mcq: McqStateResponse | null | undefined): boolean {
  const status = String(mcq?.status || '')
  return status === 'completed' || status === 'timed_out'
}

const CLOSING_FALLBACK =
  'Thank you for your time today. Our team will follow up with next steps. Wishing you all the best.'

function isClosingSession(session: AiInterviewSessionResponse | null | undefined): boolean {
  if (!session) return false
  const question = session.current_question
  const questionId = String(question?.id || '')
  return (
    session.status === 'COMPLETED'
    || session.interview_phase === 'DONE'
    || Boolean(question?.is_closing)
    || questionId.startsWith('qna-close')
  )
}

function isCandidateQnaSession(session: AiInterviewSessionResponse | null | undefined): boolean {
  if (!session) return false
  const question = session.current_question
  return Boolean(
    question?.is_candidate_qna
    || question?.is_closing
    || question?.category_id === 'candidate_qna'
    || session.interview_phase === 'CANDIDATE_QNA'
    || session.interview_phase === 'DONE'
    || isClosingSession(session)
  )
}

async function awaitWithTimeout(task: Promise<void>, timeoutMs: number): Promise<void> {
  let timer = 0
  try {
    await Promise.race([
      task,
      new Promise<void>((resolve) => {
        timer = window.setTimeout(resolve, timeoutMs)
      }),
    ])
  } finally {
    window.clearTimeout(timer)
  }
}

interface JoinStatusResponse {
  session_id: string
  status: string
  termination_reason?: string | null
  can_join: boolean
  title: string
  message: string
}

function voiceCompletionPercent(result: VerificationResponse): number {
  const sentence = result.sentence_verification
    ?? (result.measurements?.sentence_verification as { completion_percentage?: number } | undefined)
  return Number(sentence?.completion_percentage ?? 0)
}

function voiceFullyCaptured(result: VerificationResponse): boolean {
  return Boolean(result.passed) && voiceCompletionPercent(result) >= 99.5
}

function faceStatusCopy(action: 'enroll' | 'verify', result: VerificationResponse): { ok: boolean; title: string; detail: string } {
  if (action === 'enroll') {
    const accepted = Boolean(result.passed || result.measurements.sample_accepted || result.measurements.enrollment_complete)
    if (result.passed || result.measurements.enrollment_complete) {
      return { ok: true, title: 'Face captured', detail: 'Please take one more photo to confirm it is you.' }
    }
    if (accepted) {
      return { ok: true, title: 'Photo captured', detail: 'Please capture the next photo.' }
    }
    return { ok: false, title: 'Face not verified', detail: 'Please capture your photo again in good lighting, looking at the camera.' }
  }
  if (result.passed) {
    return { ok: true, title: 'Face verified', detail: 'Your identity photo has been accepted.' }
  }
  return { ok: false, title: 'Face not verified', detail: 'Please capture your photo again.' }
}

function voiceStatusCopy(action: 'enroll' | 'verify', captured: boolean): { ok: boolean; title: string; detail: string } {
  if (captured && action === 'enroll') {
    return { ok: true, title: 'Voice captured', detail: 'Please read the sentence once more to confirm it is you.' }
  }
  if (captured && action === 'verify') {
    return { ok: true, title: 'Voice verified', detail: 'Your voice has been accepted.' }
  }
  return { ok: false, title: 'Voice not captured', detail: 'Please read the full sentence clearly and try again.' }
}

export function CandidatePage() {
  const [phase, setPhase] = useState<CandidatePhase>('registration')
  const [sessionGate, setSessionGate] = useState<'loading' | 'ready' | 'missing' | 'blocked'>('loading')
  const [accessError, setAccessError] = useState<{ title: string; text: string } | null>(null)
  const [step, setStep] = useState(0)
  const [message, setMessage] = useState<MessageState>({ text: '', kind: 'notice' })
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [consent, setConsent] = useState(false)
  const [credentials, setCredentials] = useState<CandidateSessionCredentials | null>(null)
  const [devices, setDevices] = useState<DeviceState>({ camera: 'pending', microphone: 'pending' })
  const [mandatoryModelsReady, setMandatoryModelsReady] = useState(false)
  const [biometrics, setBiometrics] = useState<BiometricState>({
    faceEnrolled: false,
    faceVerified: false,
    voiceEnrolled: false,
    voiceVerified: false,
  })
  const [faceResult, setFaceResult] = useState<VerificationResponse | null>(null)
  const [voiceResult, setVoiceResult] = useState<VerificationResponse | null>(null)
  const [voiceSentence, setVoiceSentence] = useState<VoiceSentenceResponse | null>(null)
  const [recognizedTranscript, setRecognizedTranscript] = useState('')
  const [voiceRecording, setVoiceRecording] = useState(false)
  const [transcriptionError, setTranscriptionError] = useState<string | null>(null)
  const recognizedTranscriptRef = useRef('')
  const voiceSentenceTextRef = useRef('')
  const liveDictationStopRef = useRef<(() => void) | null>(null)
  const [busy, setBusy] = useState<string>('')
  const [active, setActive] = useState(false)
  const [resumeRequired, setResumeRequired] = useState(false)
  const [elapsed, setElapsed] = useState('00:00')
  const [faceLive, setFaceLive] = useState<{ label: string; state: 'neutral' | 'ok' | 'bad' }>({ label: 'Face waiting', state: 'neutral' })
  const [voiceLive, setVoiceLive] = useState<{ label: string; state: 'neutral' | 'ok' | 'bad' }>({ label: 'Voice waiting', state: 'neutral' })
  const [attentionLive, setAttentionLive] = useState<{ label: string; state: 'neutral' | 'ok' | 'bad' }>({ label: 'Waiting for attention analysis', state: 'neutral' })
  const [connectionLive, setConnectionLive] = useState<{ label: string; state: 'neutral' | 'ok' | 'bad' }>({ label: 'Disconnected', state: 'neutral' })
  const [terminationReason, setTerminationReason] = useState<string | null>(null)
  const [finishState, setFinishState] = useState<FinishState | null>(null)
  const [aiSession, setAiSession] = useState<AiInterviewSessionResponse | null>(null)
  const [aiSpeaking, setAiSpeaking] = useState(false)
  const [capturingAnswer, setCapturingAnswer] = useState(false)
  const [hrIntervention, setHrIntervention] = useState(false)
  const [hrMessage, setHrMessage] = useState('')
  const [leaveOpen, setLeaveOpen] = useState(false)
  const [participantRole, setParticipantRole] = useState<'candidate' | 'hr'>('candidate')
  const hrAutoStartRef = useRef(false)
  const isHrParticipant = participantRole === 'hr'
  const isHrParticipantRef = useRef(false)
  const [hrNewQuestion, setHrNewQuestion] = useState('')
  const [hrSpeakingLocal, setHrSpeakingLocal] = useState(false)
  const [candidatePresent, setCandidatePresent] = useState(false)
  const [hrPresent, setHrPresent] = useState(false)
  const [remoteStream, setRemoteStream] = useState<MediaStream | null>(null)
  const [pinnedView, setPinnedView] = useState<'local' | 'remote'>('remote')
  const [aiInterviewStarted, setAiInterviewStarted] = useState(false)
  const [cameraEnabled, setCameraEnabled] = useState(true)
  const [micEnabled, setMicEnabled] = useState(true)
  const hrStartTriggeredRef = useRef(false)
  useEffect(() => {
    isHrParticipantRef.current = isHrParticipant
  }, [isHrParticipant])
  const [fullscreenLost, setFullscreenLost] = useState(false)
  const [facePhotoUrl, setFacePhotoUrl] = useState<string | null>(null)
  const [faceSampleCount, setFaceSampleCount] = useState(0)
  const [candidateDisplayName, setCandidateDisplayName] = useState('')
  const [candidateJobTitle, setCandidateJobTitle] = useState('')
  const [introPlayed, setIntroPlayed] = useState(false)
  const [conversationState, setConversationState] = useState<'idle' | 'ai_speaking' | 'listening' | 'processing'>('idle')
  const [interviewStage, setInterviewStage] = useState<'idle' | 'mcq' | 'oral'>('idle')
  const [mcq, setMcq] = useState<McqStateResponse | null>(null)
  const [mcqRemaining, setMcqRemaining] = useState(0)
  const [mcqLockedOptionId, setMcqLockedOptionId] = useState<string | null>(null)
  const [mcqBusy, setMcqBusy] = useState(false)
  const [brand, setBrand] = useState(() => resolveCompanyBrand())
  useEffect(() => subscribeCompanyBrand(() => setBrand(resolveCompanyBrand())), [])

  const previewRef = useRef<HTMLVideoElement>(null)
  const liveVideoRef = useRef<HTMLVideoElement>(null)
  const pipVideoRef = useRef<HTMLVideoElement>(null)
  const roomPeerRef = useRef<RoomPeerConnection | null>(null)
  const remoteStreamRef = useRef<MediaStream | null>(null)
  const pinnedViewRef = useRef<'local' | 'remote'>('remote')
  const credentialsRef = useRef<CandidateSessionCredentials | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const activeRef = useRef(false)
  const startAtRef = useRef(0)
  const resumeElapsedRef = useRef(0)
  const fullRecorderRef = useRef<MediaRecorder | null>(null)
  const fullRecordStreamRef = useRef<MediaStream | null>(null)
  const answerRecordStreamRef = useRef<MediaStream | null>(null)
  const audioMonitorStreamRef = useRef<MediaStream | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const audioNodeRef = useRef<AudioNode | null>(null)
  const audioSourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const audioGainRef = useRef<GainNode | null>(null)
  const audioChunksRef = useRef<Float32Array[]>([])
  const audioSampleCountRef = useRef(0)
  const audioWindowStartedAtRef = useRef(0)
  const audioQueueRef = useRef(new LatestQueue<AudioWindowJob>(2))
  const audioPumpPromiseRef = useRef<Promise<void> | null>(null)
  const audioSequenceRef = useRef(0)
  const lastProcessedAudioSequenceRef = useRef(-1)
  const frameSequenceRef = useRef(0)
  const lastProcessedFrameSequenceRef = useRef(-1)
  const frameInFlightRef = useRef(false)
  const droppedFrameRef = useRef(0)
  const sequenceRef = useRef(0)
  const segmentIdRef = useRef('')
  const segmentSequenceRef = useRef(0)
  const segmentIdsRef = useRef<Set<string>>(new Set())
  const lastChunkCapturedAtRef = useRef(0)
  const stoppingRecorderRef = useRef(false)
  const chunkWritePromiseRef = useRef<Promise<void>>(Promise.resolve())
  const flushPromiseRef = useRef<Promise<void> | null>(null)
  const tabVisibilityEpisodeRef = useRef<TabVisibilityEpisode | null>(null)
  const finishingRef = useRef(false)
  const frameTimerRef = useRef<number | null>(null)
  const clockTimerRef = useRef<number | null>(null)
  const heartbeatTimerRef = useRef<number | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const messageTimerRef = useRef<number | null>(null)
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null)
  const answerRecorderRef = useRef<MediaRecorder | null>(null)
  const startAnswerCaptureRef = useRef<(() => Promise<void>) | null>(null)
  const submitAnswerCaptureRef = useRef<(() => Promise<void>) | null>(null)
  const speakAiQuestionRef = useRef<((current: CandidateSessionCredentials, session: AiInterviewSessionResponse) => Promise<void>) | null>(null)
  const lastBroadcastQuestionIdRef = useRef<string | null>(null)
  const answerChunksRef = useRef<Blob[]>([])
  const phaseRef = useRef<CandidatePhase>('registration')
  const leavingInterviewRef = useRef(false)
  const capturingAnswerRef = useRef(false)
  const silenceMonitorRef = useRef<SilenceMonitor | null>(null)
  const submittingAnswerRef = useRef(false)
  const durationExtendedNotifiedRef = useRef(false)
  const hangingUpRef = useRef(false)
  const speakingNowRef = useRef<string | null>(null)
  const interviewStageRef = useRef<'idle' | 'mcq' | 'oral'>('idle')
  const oralStartedRef = useRef(false)
  const mcqFinishingRef = useRef(false)
  const mcqBusyRef = useRef(false)
  const mcqRef = useRef<McqStateResponse | null>(null)
  const beginOralAfterMcqRef = useRef<(
    current: CandidateSessionCredentials,
    session: AiInterviewSessionResponse | null,
    oralRules?: string,
  ) => Promise<void>>(async () => {})
  const stopAndFinalizeRef = useRef<(reason: string) => Promise<void>>(async () => {})
  const speakClosingThenHangUpRef = useRef<(
    current: CandidateSessionCredentials,
    session: AiInterviewSessionResponse,
  ) => Promise<void>>(async () => {})

  useEffect(() => {
    interviewStageRef.current = interviewStage
  }, [interviewStage])
  useEffect(() => {
    mcqRef.current = mcq
  }, [mcq])

  const voiceProgress = useMemo(
    () => evaluateLiveSentence(voiceSentence?.text ?? '', recognizedTranscript),
    [recognizedTranscript, voiceSentence?.text],
  )

  const currentQuestionText = useMemo(() => {
    if (interviewStage === 'mcq') {
      return isHrParticipant
        ? 'Candidate is taking the short MCQ test.'
        : 'Multiple-choice test in progress. Select one option to lock your answer.'
    }
    return (
      aiSession?.current_question?.question_text
      || (aiSession?.status === 'COMPLETED'
        ? 'Thank you. The AI interview is complete.'
        : isHrParticipant && !aiInterviewStarted
          ? 'AI interview has not started yet. It will begin when the candidate joins.'
          : 'Preparing your first question…')
    )
  }, [aiInterviewStarted, aiSession, interviewStage, isHrParticipant])

  const currentQuestionMeta = useMemo(() => {
    if (interviewStage === 'mcq') {
      const total = mcq?.total_questions || 0
      const current = Math.min(total, (mcq?.current_index || 0) + (mcq?.current_question ? 1 : 0))
      return `MCQ test · ${current} of ${total}`
    }
    if (isClosingSession(aiSession)) return 'Closing'
    if (isCandidateQnaSession(aiSession)) return 'Your questions'
    return `${aiSession?.current_question?.category_name || (isHrParticipant && !aiInterviewStarted ? 'Lobby' : 'Interview question')}${aiSession ? ` · ${(aiSession.current_index || 0) + 1} of ${aiSession.total_questions || 0}` : ''}`
  }, [aiInterviewStarted, aiSession, interviewStage, isHrParticipant, mcq])

  const otherPartyPresent = isHrParticipant ? candidatePresent : hrPresent

  const mainParticipantLabel = useMemo(() => {
    if (pinnedView === 'local') {
      return isHrParticipant ? 'You (HR)' : (candidateDisplayName || 'You')
    }
    return isHrParticipant ? (candidateDisplayName || 'Candidate') : 'HR interviewer'
  }, [pinnedView, isHrParticipant, candidateDisplayName])

  const pipParticipantLabel = useMemo(() => {
    if (pinnedView !== 'local') {
      return isHrParticipant ? 'You (HR)' : (candidateDisplayName || 'You')
    }
    return isHrParticipant ? (candidateDisplayName || 'Candidate') : 'HR interviewer'
  }, [pinnedView, isHrParticipant, candidateDisplayName])

  useEffect(() => {
    recognizedTranscriptRef.current = recognizedTranscript
  }, [recognizedTranscript])

  useEffect(() => {
    voiceSentenceTextRef.current = voiceSentence?.text ?? ''
  }, [voiceSentence?.text])

  useEffect(() => () => {
    liveDictationStopRef.current?.()
    liveDictationStopRef.current = null
  }, [])

  useEffect(() => {
    phaseRef.current = phase
  }, [phase])

  useEffect(() => {
    credentialsRef.current = credentials
  }, [credentials])

  useEffect(() => {
    activeRef.current = active
  }, [active])

  useEffect(() => {
    capturingAnswerRef.current = capturingAnswer
  }, [capturingAnswer])

  const stopSilenceMonitor = useCallback(() => {
    silenceMonitorRef.current?.stop()
    silenceMonitorRef.current = null
  }, [])

  const closeInterviewTab = useCallback(() => {
    sessionStorage.removeItem('agent5-session')
    try {
      window.open('', '_self')
      window.close()
    } catch {
      /* ignore */
    }
    window.setTimeout(() => {
      if (!window.closed) {
        window.location.replace('about:blank')
      }
    }, 300)
  }, [])

  const showMessage = useCallback((text: string, kind: MessageKind = 'notice') => {
    setMessage({ text, kind })
    if (messageTimerRef.current) window.clearTimeout(messageTimerRef.current)
    messageTimerRef.current = window.setTimeout(() => setMessage({ text: '', kind: 'notice' }), 8000)
  }, [])

  const api = useCallback(<T,>(path: string, options: RequestInit = {}): Promise<T> => {
    const current = credentialsRef.current
    if (!current) return Promise.reject(new Error('Candidate session is not available'))
    return requestJson<T>(path, options, current.token)
  }, [])

  const attachStream = useCallback(() => {
    const stream = streamRef.current
    if (!stream) return
    if (previewRef.current && previewRef.current.srcObject !== stream) {
      previewRef.current.srcObject = stream
      void previewRef.current.play().catch(() => undefined)
    }
    if (phaseRef.current !== 'interview') {
      if (liveVideoRef.current && liveVideoRef.current.srcObject !== stream) {
        liveVideoRef.current.srcObject = stream
        void liveVideoRef.current.play().catch(() => undefined)
      }
    }
  }, [])

  const syncInterviewVideos = useCallback(() => {
    if (phaseRef.current !== 'interview') return
    const local = streamRef.current
    const remote = remoteStreamRef.current
    const pinned = pinnedViewRef.current
    const mainStream = pinned === 'local' ? local : (remote ?? local)
    const pipStream = pinned === 'local' ? remote : local

    const attachToVideo = (element: HTMLVideoElement | null, stream: MediaStream | null) => {
      if (!element) return
      if (element.srcObject !== stream) {
        element.srcObject = stream
      }
      // Video tiles are display-only; never play mic audio back (prevents echo/feedback).
      element.muted = true
      element.volume = 0
      if (stream) {
        void element.play().catch(() => undefined)
      }
    }

    attachToVideo(liveVideoRef.current, mainStream ?? null)
    attachToVideo(pipVideoRef.current, pipStream ?? null)
  }, [])

  const tearDownRoomPeer = useCallback(() => {
    roomPeerRef.current?.close()
    roomPeerRef.current = null
    remoteStreamRef.current = null
    setRemoteStream(null)
  }, [])

  const ensureRoomPeer = useCallback(() => {
    const stream = streamRef.current
    if (!stream || roomPeerRef.current) return
    const peer = new RoomPeerConnection(
      stream,
      isHrParticipantRef.current,
      (remote) => {
        remoteStreamRef.current = remote
        setRemoteStream(remote)
        syncInterviewVideos()
        window.requestAnimationFrame(() => syncInterviewVideos())
      },
      (signal) => {
        if (socketRef.current?.readyState === WebSocket.OPEN) {
          socketRef.current.send(JSON.stringify({ type: 'webrtc_signal', ...signal }))
        }
      },
    )
    peer.connect()
    roomPeerRef.current = peer
  }, [syncInterviewVideos])

  useEffect(() => {
    remoteStreamRef.current = remoteStream
    syncInterviewVideos()
    const frame = window.requestAnimationFrame(() => syncInterviewVideos())
    return () => window.cancelAnimationFrame(frame)
  }, [remoteStream, syncInterviewVideos])

  useEffect(() => {
    pinnedViewRef.current = pinnedView
    syncInterviewVideos()
  }, [pinnedView, syncInterviewVideos])

  useEffect(() => {
    if (phase !== 'interview' || !active) return
    syncInterviewVideos()
    const frame = window.requestAnimationFrame(() => syncInterviewVideos())
    return () => window.cancelAnimationFrame(frame)
  }, [phase, active, syncInterviewVideos])

  useEffect(() => {
    if (phase !== 'interview' || !active) return
    ensureRoomPeer()
    return () => tearDownRoomPeer()
  }, [phase, active, ensureRoomPeer, tearDownRoomPeer])

  useEffect(() => {
    if (phase !== 'interview' || !active) return
    const otherPresent = isHrParticipant ? candidatePresent : hrPresent
    if (!otherPresent || !roomPeerRef.current) return
    if (isHrParticipant) {
      void roomPeerRef.current.makeOffer()
    }
  }, [phase, active, candidatePresent, hrPresent, isHrParticipant])

  useEffect(() => {
    attachStream()
  }, [attachStream, phase])

  const reportInterruption = useCallback(async (kind: 'camera' | 'microphone' | 'connection' | 'recording') => {
    const current = credentialsRef.current
    if (!activeRef.current || !current) return
    const form = new FormData()
    form.append('kind', kind)
    form.append('relative_ms', String(Math.max(0, Date.now() - startAtRef.current)))
    try {
      await requestJson(`/api/sessions/${current.sessionId}/device-interruption`, { method: 'POST', body: form }, current.token)
    } catch (error) {
      console.warn('Could not report interruption', error)
    }
  }, [])

  const ensureMedia = useCallback(async (): Promise<MediaStream> => {
    const current = streamRef.current
    if (current && current.getTracks().some((track) => track.readyState === 'live')) {
      attachStream()
      return current
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('Camera and microphone access require a supported browser and a secure/localhost origin')
    }
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 960 }, height: { ideal: 540 }, frameRate: { ideal: 15, max: 24 } },
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    })
    streamRef.current = stream
    for (const track of stream.getVideoTracks()) {
      track.onended = () => void reportInterruption('camera')
      track.onmute = () => { if (activeRef.current) void reportInterruption('camera') }
    }
    for (const track of stream.getAudioTracks()) {
      track.onended = () => void reportInterruption('microphone')
      track.onmute = () => { if (activeRef.current) void reportInterruption('microphone') }
    }
    attachStream()
    if (phaseRef.current === 'interview') {
      syncInterviewVideos()
    }
    return stream
  }, [attachStream, reportInterruption, syncInterviewVideos])

  const hydrateSession = useCallback(async (saved: CandidateSessionCredentials) => {
    credentialsRef.current = saved
    setCredentials(saved)
    const tokenCompany = readCompanyCodeFromToken(saved.token)
    if (tokenCompany) setCompanyCode(tokenCompany, saved.sessionId)
    else if (saved.company) setCompanyCode(saved.company, saved.sessionId)
    const applyClosedSession = (status: string, reason: string | null | undefined, title?: string, message?: string) => {
      sessionStorage.removeItem('agent5-session')
      credentialsRef.current = null
      setCredentials(null)
      setPhase('finished')
      setStep(4)
      setSessionGate('blocked')
      if (status === 'terminated') {
        setAccessError({
          title: title || 'This interview has been terminated',
          text: message || `You cannot rejoin because ${terminationCopy(reason)}. Please contact HR if you need further information.`,
        })
        return
      }
      setAccessError({
        title: title || 'This interview is already complete',
        text: message || 'You have already finished this interview. Please contact HR if you need further information.',
      })
    }
    try {
      const state = await requestJson<SessionStateResponse>(`/api/sessions/${saved.sessionId}/state`, {}, saved.token)
      if (state.company_code) setCompanyCode(state.company_code, saved.sessionId)
      setMandatoryModelsReady(Boolean(state.mandatory_models_ready))
      resumeElapsedRef.current = Math.max(0, Number(state.current_client_elapsed_ms ?? 0))
      setElapsed(formatElapsed(resumeElapsedRef.current))
      setResumeRequired(state.status === 'active' || state.status === 'terminating')
      setTerminationReason(state.termination_reason)
      if (state.status === 'completed' || state.status === 'terminated') {
        applyClosedSession(state.status, state.termination_reason)
        return
      }
      setDevices({ camera: 'pending', microphone: 'pending' })
      setBiometrics({
        faceEnrolled: state.face_enrolled,
        faceVerified: false,
        voiceEnrolled: state.voice_enrolled,
        voiceVerified: state.initial_voice_verified,
      })
      setPhase('devices')
      setStep(1)
      setSessionGate('ready')
      try {
        const runtime = await requestJson<{ company_code?: string; company_name?: string; can_rejoin?: boolean; room_visit_open?: boolean; room_join_count?: number; max_room_joins?: number }>(
          `/api/interview/room/sessions/${saved.sessionId}/runtime`,
          {},
          saved.token,
        )
        if (runtime.company_code) setCompanyCode(runtime.company_code, saved.sessionId)
        if (runtime.can_rejoin === false && !runtime.room_visit_open) {
          applyClosedSession(
            'terminated',
            'room_join_limit',
            'Interview rejoin limit reached',
            `You have already joined this interview ${runtime.max_room_joins || 3} times. A fourth entry is not allowed. Please contact HR.`,
          )
          return
        }
      } catch {
        /* branding is best-effort until the room runtime is available */
      }
      if (state.status === 'active' || state.status === 'terminating') {
        showMessage('Complete camera, microphone, and a face photo in this browser before the interview opens in fullscreen.', 'notice')
      }
    } catch (error) {
      sessionStorage.removeItem('agent5-session')
      credentialsRef.current = null
      setCredentials(null)
      try {
        const closed = await requestJson<JoinStatusResponse>(`/api/sessions/${saved.sessionId}/join-status`)
        if (!closed.can_join) {
          applyClosedSession(closed.status, closed.termination_reason, closed.title, closed.message)
          return
        }
      } catch {
        // Fall through to a generic access error when the session cannot be read.
      }
      const expired = error instanceof ApiError && (error.status === 401 || error.status === 403)
      setSessionGate('blocked')
      setAccessError({
        title: expired ? 'This interview link is no longer valid' : 'Unable to open this interview',
        text: expired
          ? 'The join link has expired or this session is no longer available. Please contact HR for a new interview link.'
          : errorMessage(error),
      })
    }
  }, [showMessage])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const querySessionId = params.get('session_id')
    const queryToken = params.get('token')
    const queryRoleHint = params.get('role') === 'hr' ? 'hr' : 'candidate'
    if (querySessionId && queryToken) {
      const resolvedRole = resolveParticipantRole(queryToken, queryRoleHint)
      const queryCompany = new URLSearchParams(window.location.search).get('company')
      const tokenCompany = readCompanyCodeFromToken(queryToken)
      const company = (queryCompany || tokenCompany || '').trim()
      if (company) setCompanyCode(company, querySessionId)
      const saved: CandidateSessionCredentials = {
        sessionId: querySessionId,
        token: queryToken,
        role: resolvedRole,
        company,
      }
      setParticipantRole(resolvedRole)
      sessionStorage.setItem('agent5-session', JSON.stringify(saved))
      void hydrateSession(saved)
      return
    }
    const raw = sessionStorage.getItem('agent5-session')
    if (!raw) {
      setSessionGate('missing')
      return
    }
    try {
      const saved = JSON.parse(raw) as CandidateSessionCredentials
      if (saved.sessionId && saved.token) {
        const resolvedRole = resolveParticipantRole(saved.token, saved.role ?? null)
        if (resolvedRole !== saved.role) {
          saved.role = resolvedRole
          sessionStorage.setItem('agent5-session', JSON.stringify(saved))
        }
        setParticipantRole(resolvedRole)
        void hydrateSession(saved)
      } else {
        setSessionGate('missing')
      }
    } catch {
      sessionStorage.removeItem('agent5-session')
      setSessionGate('missing')
    }
  }, [hydrateSession])

  const register = async () => {
    if (!fullName.trim() || !email.trim()) {
      showMessage('Enter your full name and email address.', 'error')
      return
    }
    if (!consent) {
      showMessage('Recording and biometric consent is required.', 'error')
      return
    }
    setBusy('Creating session')
    try {
      const data = await requestJson<CandidateRegistrationResponse>('/api/candidate/register', jsonRequest('POST', {
        full_name: fullName.trim(),
        email: email.trim(),
        consent,
      }))
      const saved = { sessionId: data.session_id, token: data.token }
      credentialsRef.current = saved
      setCredentials(saved)
      setMandatoryModelsReady(Boolean(data.mandatory_models_ready))
      sessionStorage.setItem('agent5-session', JSON.stringify(saved))
      setPhase('devices')
      setStep(1)
      showMessage('Session created. Continue with the device check.', 'success')
    } catch (error) {
      showMessage(errorMessage(error), 'error')
    } finally {
      setBusy('')
    }
  }

  const checkDevices = async () => {
    const current = credentialsRef.current
    if (!current) return
    setBusy('Checking devices')
    try {
      const stream = await ensureMedia()
      const cameraOk = stream.getVideoTracks().some((track) => track.readyState === 'live')
      const microphoneOk = stream.getAudioTracks().some((track) => track.readyState === 'live')
      setDevices({ camera: cameraOk ? 'ready' : 'failed', microphone: microphoneOk ? 'ready' : 'failed' })
      await api(`/api/sessions/${current.sessionId}/device-check`, jsonRequest('POST', {
        camera_ok: cameraOk,
        microphone_ok: microphoneOk,
        details: {
          video: stream.getVideoTracks()[0]?.getSettings(),
          audio: stream.getAudioTracks()[0]?.getSettings(),
          user_agent: navigator.userAgent,
        },
      }))
      if (cameraOk && microphoneOk) {
        setPhase('enrollment')
        setStep(2)
        showMessage('Camera and microphone are ready.', 'success')
      } else {
        showMessage('Both camera and microphone must be available.', 'error')
      }
    } catch (error) {
      setDevices({ camera: 'failed', microphone: 'failed' })
      showMessage(errorMessage(error), 'error')
    } finally {
      setBusy('')
    }
  }

  const loadVoiceSentence = useCallback(async (rotate = false) => {
    const current = credentialsRef.current
    if (!current) return
    const path = `/api/sessions/${current.sessionId}/voice/sentence${rotate ? '/change' : ''}`
    const sentence = await requestJson<VoiceSentenceResponse>(path, rotate ? { method: 'POST' } : {}, current.token)
    setVoiceSentence(sentence)
    setRecognizedTranscript('')
    setTranscriptionError(null)
  }, [])

  useEffect(() => {
    if (phase !== 'devices' && phase !== 'enrollment') return
    void ensureMedia().catch((error) => {
      if (phase === 'devices') showMessage(errorMessage(error), 'error')
    })
  }, [ensureMedia, phase, showMessage])

  useEffect(() => {
    if (phase === 'enrollment' && credentials && !voiceSentence) {
      void loadVoiceSentence().catch((error) => showMessage(errorMessage(error), 'error'))
    }
  }, [credentials, loadVoiceSentence, phase, showMessage, voiceSentence])

  const captureBlob = useCallback(async () => {
    const video = liveVideoRef.current ?? previewRef.current
    if (!video) throw new Error('Camera preview is not ready')
    const deadline = Date.now() + 2500
    let lastError: unknown = null
    while (Date.now() < deadline) {
      if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.videoWidth >= 160 && video.videoHeight >= 120) {
        try {
          return await captureVideoFrame(video)
        } catch (error) {
          lastError = error
        }
      }
      await new Promise((resolve) => window.setTimeout(resolve, 100))
    }
    throw lastError instanceof Error ? lastError : new Error('Camera did not produce a usable frame')
  }, [])

  const rememberFacePhoto = useCallback((blob: Blob) => {
    setFacePhotoUrl((current) => {
      if (current) URL.revokeObjectURL(current)
      return URL.createObjectURL(blob)
    })
  }, [])

  const sendImage = async (action: 'enroll' | 'verify') => {
    const current = credentialsRef.current
    if (!current) throw new Error('Candidate session is unavailable')
    await ensureMedia()
    const blob = await captureBlob()
    rememberFacePhoto(blob)
    const form = new FormData()
    form.append('image', blob, 'face.jpg')
    return api<VerificationResponse>(`/api/sessions/${current.sessionId}/face/${action}`, { method: 'POST', body: form })
  }

  const handleFace = async (action: 'enroll' | 'verify') => {
    setBusy(action === 'enroll' ? 'Taking face photo' : 'Verifying face photo')
    try {
      const result = await sendImage(action)
      setFaceResult(result)
      const count = Number(result.measurements.sample_count ?? 0)
      setFaceSampleCount(count)
      const enrollmentComplete = Boolean(result.passed || result.measurements.enrollment_complete)
      setBiometrics((current) => ({
        ...current,
        faceEnrolled: action === 'enroll' ? enrollmentComplete : current.faceEnrolled,
        faceVerified: action === 'verify' ? result.passed : current.faceVerified,
      }))
      if (action === 'enroll') {
        const copy = faceStatusCopy(action, result)
        showMessage(
          `${copy.title}. ${copy.detail}`,
          copy.ok ? 'success' : 'error',
        )
        return
      }
      const copy = faceStatusCopy(action, result)
      showMessage(`${copy.title}. ${copy.detail}`, copy.ok ? 'success' : 'error')
    } catch (error) {
      showMessage(errorMessage(error), 'error')
    } finally {
      setBusy('')
    }
  }

  const recordVoiceSample = useCallback(async (milliseconds = 12000): Promise<Blob> => {
    const stream = await ensureMedia()
    const audioStream = new MediaStream(stream.getAudioTracks())
    return new Promise((resolve, reject) => {
      const parts: Blob[] = []
      const mimeType = supportedMime(true)
      const recorder = new MediaRecorder(audioStream, mimeType ? { mimeType } : undefined)
      let settled = false
      let earlyStopTimer: number | undefined

      const finish = (blob: Blob) => {
        if (settled) return
        settled = true
        window.clearTimeout(hardTimeout)
        if (earlyStopTimer !== undefined) window.clearInterval(earlyStopTimer)
        resolve(blob)
      }

      const hardTimeout = window.setTimeout(() => {
        if (!settled) {
          settled = true
          if (earlyStopTimer !== undefined) window.clearInterval(earlyStopTimer)
          reject(new Error('Audio sample recorder did not stop'))
        }
      }, milliseconds + 10000)

      recorder.ondataavailable = (event) => { if (event.data.size) parts.push(event.data) }
      recorder.onerror = (event) => {
        if (!settled) {
          settled = true
          window.clearTimeout(hardTimeout)
          if (earlyStopTimer !== undefined) window.clearInterval(earlyStopTimer)
          reject((event as ErrorEvent).error ?? new Error('Audio recording failed'))
        }
      }
      recorder.onstop = () => {
        finish(new Blob(parts, { type: recorder.mimeType || mimeType || 'audio/webm' }))
      }
      recorder.start(250)

      // Stop early once every expected word has been recognized live.
      earlyStopTimer = window.setInterval(() => {
        if (recorder.state === 'inactive') return
        const progress = evaluateLiveSentence(voiceSentenceTextRef.current, recognizedTranscriptRef.current)
        if (progress.completedCount > 0 && progress.completedCount >= progress.words.length) {
          recorder.stop()
        }
      }, 200)

      window.setTimeout(() => { if (recorder.state !== 'inactive') recorder.stop() }, milliseconds)
    })
  }, [ensureMedia])

  const sendVoice = async (action: 'enroll' | 'verify') => {
    const current = credentialsRef.current
    if (!current) throw new Error('Candidate session is unavailable')
    if (!voiceSentence) throw new Error('Verification sentence is unavailable')
    const blob = await recordVoiceSample()
    const form = new FormData()
    form.append('audio', blob, blob.type.includes('mp4') ? 'voice.mp4' : 'voice.webm')
    form.append('sentence_id', voiceSentence.id)
    return api<VerificationResponse>(`/api/sessions/${current.sessionId}/voice/${action}`, { method: 'POST', body: form })
  }

  const handleVoice = async (action: 'enroll' | 'verify') => {
    setRecognizedTranscript('')
    recognizedTranscriptRef.current = ''
    setTranscriptionError(null)
    setVoiceRecording(true)
    setBusy(action === 'enroll' ? 'Speak the sentence — words turn green as they are recognized' : 'Speak to verify — words turn green as they are recognized')

    liveDictationStopRef.current?.()
    const dictation = startLiveDictation((transcript) => {
      recognizedTranscriptRef.current = transcript
      setRecognizedTranscript(transcript)
    })
    liveDictationStopRef.current = dictation.stop
    if (!dictation.supported) {
      setTranscriptionError('Live word highlighting needs Chrome or Edge. Whisper will still check the full recording.')
    }

    try {
      const result = await sendVoice(action)
      setVoiceResult(result)
      const captured = voiceFullyCaptured(result)
      setBiometrics((current) => ({
        ...current,
        voiceEnrolled: action === 'enroll' ? captured : current.voiceEnrolled,
        voiceVerified: action === 'verify' ? captured : current.voiceVerified,
      }))
      const sentence = result.sentence_verification
      const transcript = sentence?.recognized_transcript
        ?? (sentence?.recognized_words?.length ? sentence.recognized_words.join(' ') : '')
      if (transcript) {
        recognizedTranscriptRef.current = transcript
        setRecognizedTranscript(transcript)
      }
      if (sentence?.recognition_error) {
        setTranscriptionError('We could not capture your voice clearly. Please try again.')
      } else if (sentence && sentence.recognition_available === false) {
        setTranscriptionError('Voice capture is unavailable at the moment. Please try again, or contact HR if this continues.')
      }
      const copy = voiceStatusCopy(action, captured)
      if (action === 'enroll' && captured) {
        showMessage(`${copy.title}. ${copy.detail}`, 'success')
        window.setTimeout(() => {
          if (phaseRef.current === 'enrollment' && !leavingInterviewRef.current) {
            void handleVoice('verify')
          }
        }, 700)
        return
      }
      showMessage(`${copy.title}. ${copy.detail}`, copy.ok ? 'success' : 'error')
    } catch (error) {
      showMessage(errorMessage(error), 'error')
    } finally {
      liveDictationStopRef.current?.()
      liveDictationStopRef.current = null
      setVoiceRecording(false)
      setBusy('')
    }
  }


  const flushQueue = useCallback(async (): Promise<void> => {
    const existing = flushPromiseRef.current
    if (existing) {
      await existing
      return
    }

    const current = credentialsRef.current
    if (!current) return

    const task: Promise<void> = (async () => {
      await flushRecordingQueue(current.sessionId, current.token)
    })()

    flushPromiseRef.current = task
    try {
      await task
    } finally {
      if (flushPromiseRef.current === task) {
        flushPromiseRef.current = null
      }
    }
  }, [])

  const queueChunk = useCallback((blob: Blob, metadata: {
    sequence: number
    segmentId: string
    segmentSequence: number
    isFinal: boolean
    capturedAt: string
    durationMs: number
  }) => {
    const current = credentialsRef.current
    if (!current) return
    chunkWritePromiseRef.current = chunkWritePromiseRef.current.then(async () => {
      const checksum = await sha256(blob)
      await putChunk({
        key: `${current.sessionId}:${metadata.segmentId}:${metadata.segmentSequence}:${metadata.sequence}`,
        sessionId: current.sessionId,
        sequence: metadata.sequence,
        segmentId: metadata.segmentId,
        segmentSequence: metadata.segmentSequence,
        isFinal: metadata.isFinal,
        capturedAt: metadata.capturedAt,
        durationMs: metadata.durationMs,
        checksum,
        blob,
        mimeType: blob.type || 'video/webm',
      })
      await flushQueue()
    })
  }, [flushQueue])

  const initializeSequence = useCallback(async () => {
    const current = credentialsRef.current
    if (!current) return
    const queued = await getChunks(current.sessionId).catch(() => [])
    const queuedSequences = queued.map((item) => item.sequence)
    const queuedSegments = queued.map((item) => item.segmentId)
    try {
      const status = await requestJson<{
        acknowledged_sequences: number[]
        segments: Array<{ segment_id: string }>
      }>(`/api/sessions/${current.sessionId}/recording/status`, {}, current.token)
      const allSequences = [...status.acknowledged_sequences, ...queuedSequences]
      sequenceRef.current = allSequences.length ? Math.max(...allSequences) + 1 : 0
      segmentIdsRef.current = new Set([...status.segments.map((item) => item.segment_id), ...queuedSegments])
    } catch {
      sequenceRef.current = queuedSequences.length ? Math.max(...queuedSequences) + 1 : 0
      segmentIdsRef.current = new Set(queuedSegments)
    }
  }, [])

  const beginFullRecording = useCallback(() => {
    const stream = streamRef.current
    if (!stream) throw new Error('Camera and microphone stream is unavailable')
    if (fullRecorderRef.current && fullRecorderRef.current.state !== 'inactive') return
    stopMediaStream(fullRecordStreamRef.current)
    const recordStream = cloneMediaStream(stream)
    fullRecordStreamRef.current = recordStream
    const segmentId = `segment-${crypto.randomUUID()}`
    segmentIdRef.current = segmentId
    segmentSequenceRef.current = 0
    segmentIdsRef.current.add(segmentId)
    lastChunkCapturedAtRef.current = Date.now()
    stoppingRecorderRef.current = false
    const recorder = startMediaRecorder(
      recordStream,
      5000,
      {
        videoBitsPerSecond: 900000,
        audioBitsPerSecond: 64000,
      },
      false,
      (created) => {
        created.ondataavailable = (event) => {
          if (event.data.size > 0) {
            const now = Date.now()
            const sequence = sequenceRef.current
            const segmentSequence = segmentSequenceRef.current
            sequenceRef.current += 1
            segmentSequenceRef.current += 1
            queueChunk(event.data, {
              sequence,
              segmentId,
              segmentSequence,
              isFinal: stoppingRecorderRef.current,
              capturedAt: new Date(now).toISOString(),
              durationMs: Math.max(0, now - lastChunkCapturedAtRef.current),
            })
            lastChunkCapturedAtRef.current = now
          }
        }
        created.onerror = (event) => {
          showMessage(`Recording error: ${(event as ErrorEvent).message || 'unknown MediaRecorder failure'}`, 'error')
          void reportInterruption('recording')
        }
      },
    )
    fullRecorderRef.current = recorder
  }, [queueChunk, reportInterruption, showMessage])

  const uploadAudioWindow = useCallback(async (
    job: AudioWindowJob,
    queueDepth: number,
    droppedStale: number,
  ) => {
    const { samples, sampleRate, windowStartMs, windowEndMs, sequenceNumber, segmentId } = job
    const current = credentialsRef.current
    if (!current || !samples.length) return
    const form = new FormData()
    form.append('window_start_ms', String(Math.max(0, windowStartMs)))
    form.append('window_end_ms', String(Math.max(windowStartMs, windowEndMs)))
    form.append('duration_ms', String(Math.max(0, windowEndMs - windowStartMs)))
    form.append('captured_at', new Date().toISOString())
    form.append('sequence_number', String(sequenceNumber))
    form.append('segment_id', segmentId || 'audio-segment-0')
    form.append('queue_depth', String(queueDepth))
    form.append('dropped_stale', String(droppedStale))
    form.append('audio', pcmToWav(samples, sampleRate), 'window.wav')
    try {
      const data = await requestJson<AnalysisResponse>(`/api/sessions/${current.sessionId}/analyze-audio`, { method: 'POST', body: form }, current.token, AUDIO_REQUEST_TIMEOUT_MS)
      const responseSequence = Number(data.performance?.sequence_number ?? sequenceNumber)
      if (responseSequence <= lastProcessedAudioSequenceRef.current) return
      lastProcessedAudioSequenceRef.current = responseSequence
      if (data.monitoring) {
        const audioIssue = data.monitoring.microphone === 'processing_issue'
        setVoiceLive({ label: audioIssue ? 'Audio analysis retrying' : 'Microphone active', state: audioIssue ? 'neutral' : 'ok' })
      } else {
        setVoiceLive(voiceLiveStatus(data.speaker_verification, data.status))
      }
    } catch (error) {
      console.warn('Continuous audio analysis failed', error)
    }
  }, [])

  const pumpAudioQueue = useCallback((): Promise<void> => {
    if (audioPumpPromiseRef.current) return audioPumpPromiseRef.current
    const pump = (async () => {
      while (audioQueueRef.current.depth > 0) {
        const job = audioQueueRef.current.shift()
        if (!job) break
        const dropped = audioQueueRef.current.takeDropped()
        await uploadAudioWindow(job, audioQueueRef.current.depth, dropped)
      }
    })().finally(() => {
      audioPumpPromiseRef.current = null
      if (audioQueueRef.current.depth > 0) {
        window.queueMicrotask(() => { void pumpAudioQueue() })
      }
    })
    audioPumpPromiseRef.current = pump
    return pump
  }, [uploadAudioWindow])

  const enqueueAudioWindow = useCallback((job: AudioWindowJob) => {
    audioQueueRef.current.push(job)
    void pumpAudioQueue()
  }, [pumpAudioQueue])

  const drainAudioQueue = useCallback(async () => {
    while (audioQueueRef.current.depth > 0 || audioPumpPromiseRef.current) {
      if (!audioPumpPromiseRef.current && audioQueueRef.current.depth > 0) void pumpAudioQueue()
      await (audioPumpPromiseRef.current ?? Promise.resolve())
    }
  }, [pumpAudioQueue])

  const beginAudioWindows = useCallback(async () => {
    if (isHrParticipantRef.current) return
    const stream = streamRef.current
    if (!stream) throw new Error('Microphone stream is unavailable')
    const AudioConstructor = window.AudioContext || window.webkitAudioContext
    if (!AudioConstructor) throw new Error('Web Audio is not supported')
    const context = new AudioConstructor()
    audioContextRef.current = context
    stopMediaStream(audioMonitorStreamRef.current)
    const monitorStream = cloneMediaStream(stream, 'audio')
    audioMonitorStreamRef.current = monitorStream
    const source = context.createMediaStreamSource(monitorStream)
    audioSourceRef.current = source
    audioChunksRef.current = []
    audioSampleCountRef.current = 0
    audioWindowStartedAtRef.current = Date.now()

    const consume = (block: Float32Array) => {
      if (!activeRef.current || !block?.length) return
      const copy = new Float32Array(block)
      audioChunksRef.current.push(copy)
      audioSampleCountRef.current += copy.length
      if (audioSampleCountRef.current >= context.sampleRate * 6) {
        const samples = mergePcm(audioChunksRef.current, audioSampleCountRef.current)
        const windowStartedAt = audioWindowStartedAtRef.current
        const windowEndedAt = Date.now()
        const windowStartMs = Math.max(0, windowStartedAt - startAtRef.current)
        const windowEndMs = Math.max(windowStartMs, windowEndedAt - startAtRef.current)
        const sequenceNumber = audioSequenceRef.current
        audioSequenceRef.current += 1
        audioChunksRef.current = []
        audioSampleCountRef.current = 0
        audioWindowStartedAtRef.current = windowEndedAt
        enqueueAudioWindow({ samples, sampleRate: context.sampleRate, windowStartMs, windowEndMs, sequenceNumber, segmentId: segmentIdRef.current || 'audio-segment-0' })
      }
    }

    let processor: AudioNode
    if (context.audioWorklet && window.AudioWorkletNode) {
      await context.audioWorklet.addModule(`${import.meta.env.BASE_URL}pcm-worklet.js`)
      const node = new AudioWorkletNode(context, 'agent5-pcm-processor')
      node.port.onmessage = (event: MessageEvent<Float32Array>) => consume(event.data)
      processor = node
    } else {
      const node = context.createScriptProcessor(4096, 1, 1)
      node.onaudioprocess = (event) => consume(event.inputBuffer.getChannelData(0))
      processor = node
    }
    audioNodeRef.current = processor

    const gain = context.createGain()
    gain.gain.value = 0
    audioGainRef.current = gain
    source.connect(processor)
    processor.connect(gain)
    gain.connect(context.destination)
    if (context.state === 'suspended') await context.resume()
  }, [enqueueAudioWindow])

  const analyzeFrame = useCallback(async () => {
    const current = credentialsRef.current
    if (!activeRef.current || !current || isHrParticipantRef.current) return
    if (frameInFlightRef.current) {
      droppedFrameRef.current += 1
      return
    }
    frameInFlightRef.current = true
    try {
      const capturedAt = new Date()
      const sequenceNumber = frameSequenceRef.current
      frameSequenceRef.current += 1
      const blob = await captureBlob()
      const form = new FormData()
      form.append('relative_ms', String(Math.max(0, capturedAt.getTime() - startAtRef.current)))
      form.append('captured_at', capturedAt.toISOString())
      form.append('sequence_number', String(sequenceNumber))
      form.append('dropped_stale', String(droppedFrameRef.current))
      form.append('queue_depth', frameInFlightRef.current ? '1' : '0')
      droppedFrameRef.current = 0
      form.append('image', blob, 'frame.jpg')
      const data = await requestJson<AnalysisResponse>(`/api/sessions/${current.sessionId}/analyze-frame`, { method: 'POST', body: form }, current.token, FRAME_REQUEST_TIMEOUT_MS)
      const responseSequence = Number(data.frame_sequence ?? sequenceNumber)
      if (responseSequence < lastProcessedFrameSequenceRef.current) return
      lastProcessedFrameSequenceRef.current = responseSequence
      if (data.monitoring) {
        const cameraIssue = data.monitoring.camera === 'processing_issue' || data.monitoring.camera === 'attention_required'
        setFaceLive({ label: cameraIssue ? 'Check camera position' : 'Camera active', state: cameraIssue ? 'bad' : 'ok' })
        setAttentionLive({ label: data.monitoring.analysis === 'processing_issue' ? 'Retrying analysis' : 'Monitoring active', state: data.monitoring.analysis === 'processing_issue' ? 'neutral' : 'ok' })
      } else {
        setFaceLive(faceLiveStatus(data))
        setAttentionLive(attentionLiveStatus(data.attention))
      }
    } catch (error) {
      setFaceLive({ label: 'Frame analysis unavailable', state: 'neutral' })
      setAttentionLive({ label: 'Low confidence', state: 'neutral' })
      console.warn('Continuous frame analysis failed', error)
    } finally {
      frameInFlightRef.current = false
    }
  }, [captureBlob])

  const terminateUi = useCallback((reason?: string | null) => {
    setTerminationReason(reason || 'policy termination')
    setActive(false)
    activeRef.current = false
  }, [])

  const connectWebSocket = useCallback(() => {
    const current = credentialsRef.current
    if (!current || !activeRef.current) return
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    const socket = new WebSocket(`${protocol}://${location.host}/ws/sessions/${current.sessionId}?token=${encodeURIComponent(current.token)}`)
    socketRef.current = socket
    socket.onopen = () => {
      setConnectionLive({ label: 'Connected', state: 'ok' })
      if (phaseRef.current === 'interview') {
        tearDownRoomPeer()
        ensureRoomPeer()
        if (isHrParticipantRef.current && roomPeerRef.current) {
          void roomPeerRef.current.makeOffer()
        }
      }
    }
    socket.onclose = () => {
      if (!activeRef.current) return
      setConnectionLive({ label: 'Reconnecting', state: 'bad' })
      void reportInterruption('connection')
      reconnectTimerRef.current = window.setTimeout(connectWebSocket, 2000)
    }
    socket.onerror = () => setConnectionLive({ label: 'Connection issue', state: 'bad' })
    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as {
          type: string
          status?: string
          risk_score?: number
          risk_classification?: string
          termination_reason?: string | null
          session?: AiInterviewSessionResponse
        }
        if (data.type === 'state') {
          if (data.status === 'terminated' && !isHrParticipantRef.current) terminateUi(data.termination_reason)
        }
        if (data.type === 'room_presence') {
          const candidates = Number((data as { candidates?: number }).candidates || 0)
          const interviewers = Number((data as { interviewers?: number }).interviewers || 0)
          setCandidatePresent(candidates > 0)
          setHrPresent(interviewers > 0)
        }
        if (data.type === 'webrtc_signal') {
          ensureRoomPeer()
          const signal = data as WebRtcSignalPayload & { type: string }
          if (signal.signal_type === 'offer' && signal.sdp) {
            void roomPeerRef.current?.handleSignal({ signal_type: 'offer', sdp: signal.sdp })
          } else if (signal.signal_type === 'answer' && signal.sdp) {
            void roomPeerRef.current?.handleSignal({ signal_type: 'answer', sdp: signal.sdp })
          } else if (signal.signal_type === 'ice') {
            void roomPeerRef.current?.handleSignal({ signal_type: 'ice', candidate: signal.candidate ?? null })
          }
        }
        if (data.type === 'mcq_session') {
          const nextMcq = (data as unknown as { mcq?: McqStateResponse }).mcq
          if (!nextMcq) {
            /* ignore */
          } else {
          setMcq(nextMcq)
          setMcqRemaining(Number(nextMcq.remaining_seconds || 0))
          if (isMcqActive(nextMcq)) {
            setInterviewStage('mcq')
          } else if (isMcqDone(nextMcq) && !oralStartedRef.current) {
            setMcqLockedOptionId(null)
            if (!isHrParticipantRef.current && credentialsRef.current) {
              void beginOralAfterMcqRef.current(
                credentialsRef.current,
                null,
                nextMcq.oral_rules_message,
              )
            } else {
              setInterviewStage('oral')
            }
          }
          }
        }
        if (data.type === 'ai_session' && data.session) {
          const nextId = data.session.current_question?.id || null
          setAiSession(data.session)
          if (data.session.duration_extended && !durationExtendedNotifiedRef.current) {
            durationExtendedNotifiedRef.current = true
            showMessage('Interview time was extended so remaining questions can be completed.', 'notice')
          }
          if (isClosingSession(data.session) && !isHrParticipantRef.current && credentialsRef.current && phaseRef.current === 'interview') {
            lastBroadcastQuestionIdRef.current = nextId
            void speakClosingThenHangUpRef.current(credentialsRef.current, data.session)
          } else if (
            !isHrParticipantRef.current
            && nextId
            && nextId !== lastBroadcastQuestionIdRef.current
            && !isClosingSession(data.session)
            && phaseRef.current === 'interview'
            && interviewStageRef.current !== 'mcq'
            && credentialsRef.current
          ) {
            lastBroadcastQuestionIdRef.current = nextId
            void speakAiQuestionRef.current?.(credentialsRef.current, data.session)
          } else {
            lastBroadcastQuestionIdRef.current = nextId
          }
        }
        if (data.type === 'interview_runtime') {
          const runtime = data as { state?: string; hr_speaking?: boolean; hr_message?: string | null }
          const intervening = Boolean(runtime.hr_speaking) || runtime.state === 'HR_INTERVENTION'
          setHrIntervention(intervening)
          setHrSpeakingLocal(intervening && isHrParticipantRef.current)
          setHrMessage(runtime.hr_message || (intervening ? 'HR has joined the conversation. The AI interviewer is paused.' : ''))
          if (intervening) {
            stopSpokenAudio(ttsAudioRef as AudioPlayerRef, setAiSpeaking)
            setConversationState('idle')
          }
        }
      } catch (error) {
        console.warn('Invalid WebSocket message', error)
      }
    }
    if (heartbeatTimerRef.current) window.clearInterval(heartbeatTimerRef.current)
    heartbeatTimerRef.current = window.setInterval(() => {
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send(JSON.stringify({
          type: 'client_state',
          relative_ms: Math.max(0, Date.now() - startAtRef.current),
          role: isHrParticipantRef.current ? 'hr' : 'candidate',
        }))
        socketRef.current.send(JSON.stringify({ type: 'presence' }))
      }
    }, 4000)
  }, [ensureRoomPeer, reportInterruption, tearDownRoomPeer, terminateUi])

  const startRuntime = useCallback(async (resuming: boolean) => {
    await ensureMedia()
    const token = credentialsRef.current?.token ?? ''
    const hrMode = token
      ? resolveParticipantRole(token, isHrParticipantRef.current ? 'hr' : 'candidate') === 'hr'
      : isHrParticipantRef.current
    if (hrMode !== isHrParticipantRef.current) {
      isHrParticipantRef.current = hrMode
      setParticipantRole(hrMode ? 'hr' : 'candidate')
    }
    if (resuming && !hrMode) {
      await initializeSequence()
      void flushQueue()
    } else if (!hrMode) {
      sequenceRef.current = 0
      segmentIdsRef.current = new Set()
      audioSequenceRef.current = 0
      frameSequenceRef.current = 0
      lastProcessedFrameSequenceRef.current = -1
      droppedFrameRef.current = 0
      audioQueueRef.current.clear()
      audioPumpPromiseRef.current = null
    }
    activeRef.current = true
    setActive(true)
    setResumeRequired(false)
    phaseRef.current = 'interview'
    setPhase('interview')
    setStep(3)
    const resumeOffset = resuming ? resumeElapsedRef.current : 0
    startAtRef.current = Date.now() - resumeOffset
    setElapsed(formatElapsed(resumeOffset))
    attachStream()
    syncInterviewVideos()
    if (!hrMode) {
      try {
        beginFullRecording()
      } catch (error) {
        console.warn('Full interview recorder failed to start', error)
        showMessage(errorMessage(error), 'error')
      }
      void beginAudioWindows().catch((error) => {
        console.warn('Continuous audio initialization failed', error)
        setVoiceLive({ label: 'Audio analysis unavailable', state: 'bad' })
      })
      if (frameTimerRef.current) window.clearInterval(frameTimerRef.current)
      void analyzeFrame()
      frameTimerRef.current = window.setInterval(() => void analyzeFrame(), FRAME_INTERVAL_MS)
    } else {
      setFaceLive({ label: 'HR — no fraud checks', state: 'ok' })
      setVoiceLive({ label: 'HR mic (control room)', state: 'ok' })
      setAttentionLive({ label: 'Fraud detection off', state: 'ok' })
    }
    connectWebSocket()
    if (clockTimerRef.current) window.clearInterval(clockTimerRef.current)
    clockTimerRef.current = window.setInterval(() => setElapsed(formatElapsed(Date.now() - startAtRef.current)), 1000)
  }, [analyzeFrame, attachStream, beginAudioWindows, beginFullRecording, connectWebSocket, ensureMedia, flushQueue, initializeSequence, showMessage, syncInterviewVideos])

  const enterFullscreen = async () => {
    const root = document.documentElement as HTMLElement & {
      webkitRequestFullscreen?: () => Promise<void> | void
      msRequestFullscreen?: () => Promise<void> | void
    }
    try {
      if (document.fullscreenElement) {
        setFullscreenLost(false)
        return
      }
      if (root.requestFullscreen) {
        await root.requestFullscreen({ navigationUI: 'hide' })
      } else if (root.webkitRequestFullscreen) {
        await root.webkitRequestFullscreen()
      } else if (root.msRequestFullscreen) {
        await root.msRequestFullscreen()
      } else {
        throw new Error('Fullscreen is not supported in this browser')
      }
      setFullscreenLost(false)
    } catch {
      setFullscreenLost(true)
    }
  }

  const enterHrLobby = useCallback(async () => {
    const current = credentialsRef.current
    if (!current) return
    setBusy('Opening HR / Admin control room')
    try {
      await ensureMedia()
      setFullscreenLost(false)
      try {
        await api(`/api/sessions/${current.sessionId}/start`, jsonRequest('POST', {}))
      } catch (error) {
        if (!(error instanceof ApiError && error.status === 409)) throw error
      }
      await startRuntime(false)
      try {
        const runtime = await requestJson<{ full_name?: string; job_position?: string }>(
          `/api/interview/room/sessions/${current.sessionId}/runtime`,
          {},
          current.token,
        )
        if (runtime.full_name) setCandidateDisplayName(runtime.full_name)
        if (runtime.job_position) setCandidateJobTitle(runtime.job_position)
      } catch { /* optional */ }
      try {
        const existing = await requestJson<AiInterviewSessionResponse>(
          `/api/interview/room/sessions/${current.sessionId}/ai/session`,
          {},
          current.token,
        )
        if (existing?.current_question || ['IN_PROGRESS', 'AWAITING_ANSWER', 'TURN_COMPLETE'].includes(existing.status)) {
          setAiSession(existing)
          setAiInterviewStarted(true)
          setIntroPlayed(true)
          showMessage('Candidate interview is already in progress — controls are live.', 'success')
        } else {
          showMessage('Waiting for the candidate to join the interview room…', 'notice')
        }
      } catch {
        showMessage('Waiting for the candidate to join the interview room…', 'notice')
      }
    } catch (error) {
      showMessage(errorMessage(error), 'error')
    } finally {
      setBusy('')
    }
  }, [ensureMedia, showMessage, startRuntime])

  const startInterview = async () => {
    const current = credentialsRef.current
    if (!current) return
    const hrMode = isHrParticipantRef.current
    if (hrMode && !candidatePresent && !aiInterviewStarted) {
      showMessage('Wait for the candidate to join before starting the AI interview.', 'warning')
      return
    }
    setBusy(resumeRequired ? 'Opening interview in fullscreen' : 'Starting in-app AI interview')
    try {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
      if (AudioCtx) {
        const ctx = new AudioCtx()
        await ctx.resume()
        ctx.close().catch(() => undefined)
      }
    } catch { /* ignore */ }
    try {
      if (!hrMode) await enterFullscreen()
      else setFullscreenLost(false)
      await ensureMedia()
      try {
        await api(`/api/sessions/${current.sessionId}/start`, jsonRequest('POST', {}))
      } catch (error) {
        if (!(resumeRequired && error instanceof ApiError && error.status === 409)) throw error
      }
      if (!resumeRequired) resumeElapsedRef.current = 0
      if (phaseRef.current !== 'interview') {
        await startRuntime(resumeRequired)
      }
      let session: AiInterviewSessionResponse | null = null
      if (resumeRequired || hrMode) {
        try {
          session = await requestJson<AiInterviewSessionResponse>(
            `/api/interview/room/sessions/${current.sessionId}/ai/session`,
            {},
            current.token,
          )
        } catch {
          session = null
        }
      }
      const alreadyLive = Boolean(
        session
        && (session.current_question || ['IN_PROGRESS', 'AWAITING_ANSWER', 'TURN_COMPLETE'].includes(session.status)),
      )
      if (!session || !session.current_question) {
        session = await requestJson<AiInterviewSessionResponse>(
          `/api/interview/room/sessions/${current.sessionId}/ai/start`,
          jsonRequest('POST', {}),
          current.token,
          120_000,
        )
      }
      setAiSession(session)
      setAiInterviewStarted(true)
      if (!hrMode) await enterFullscreen()
      let displayName = fullName.trim()
      let jobTitle = candidateJobTitle
      try {
        const runtime = await requestJson<{ full_name?: string; job_position?: string }>(
          `/api/interview/room/sessions/${current.sessionId}/runtime`,
          {},
          current.token,
        )
        if (runtime.full_name) displayName = runtime.full_name
        if (runtime.job_position) jobTitle = runtime.job_position
        setCandidateDisplayName(displayName)
        setCandidateJobTitle(jobTitle || '')
      } catch {
        if (displayName) setCandidateDisplayName(displayName)
      }
      showMessage(
        hrMode
          ? 'AI interview is live. Use the controls to manage questions.'
          : 'Interview started. Listen to the AI interviewer, then complete the short MCQ test.',
        'success',
      )
      let mcqState: McqStateResponse | null = null
      try {
        mcqState = await requestJson<McqStateResponse>(
          `/api/interview/room/sessions/${current.sessionId}/ai/mcq`,
          {},
          current.token,
          120_000,
        )
      } catch (error) {
        showMessage(`MCQ test unavailable: ${errorMessage(error)}. Continuing to the oral interview.`, 'warning')
      }
      if (mcqState) {
        setMcq(mcqState)
        setMcqRemaining(Number(mcqState.remaining_seconds || 0))
      }
      if (isMcqActive(mcqState)) {
        setInterviewStage('mcq')
        if (hrMode) {
          setIntroPlayed(true)
          return
        }
        if (mcqState?.status === 'pending') {
          const intro = session.welcome_message || mcqState.intro_message || ''
          if (intro) await speakAiText(current, intro)
          if (mcqState.rules_message) await speakAiText(current, mcqState.rules_message)
          mcqState = await requestJson<McqStateResponse>(
            `/api/interview/room/sessions/${current.sessionId}/ai/mcq/start`,
            jsonRequest('POST', {}),
            current.token,
            60_000,
          )
          setMcq(mcqState)
          setMcqRemaining(Number(mcqState.remaining_seconds || 0))
        }
        setIntroPlayed(true)
        return
      }
      setInterviewStage('oral')
      const hasOralAnswers = (session.turn_history || []).some((turn) => Boolean(String(turn.answer_text || '').trim()))
      if (hrMode && alreadyLive) {
        setIntroPlayed(true)
        return
      }
      if (isMcqDone(mcqState) && !hasOralAnswers && !hrMode && session.status !== 'COMPLETED') {
        await beginOralAfterMcqRef.current(current, session, mcqState?.oral_rules_message)
        return
      }
      if (!introPlayed && session.status !== 'COMPLETED' && session.welcome_message) {
        await speakAiText(current, session.welcome_message)
        await speakAiQuestion(current, session)
        setIntroPlayed(true)
      } else if (!introPlayed && session.status !== 'COMPLETED') {
        void speakAiQuestion(current, session)
        setIntroPlayed(true)
      } else if (!hrMode) {
        void speakAiQuestion(current, session)
      }
    } catch (error) {
      showMessage(errorMessage(error), 'error')
    } finally {
      setBusy('')
    }
  }

  useEffect(() => {
    if (!isHrParticipant || sessionGate !== 'ready' || hrAutoStartRef.current) return
    if (phase === 'interview' || phase === 'finished') return
    hrAutoStartRef.current = true
    showMessage('HR / Admin join — opening control room. AI waits until the candidate joins.', 'notice')
    void enterHrLobby()
  }, [enterHrLobby, isHrParticipant, phase, sessionGate, showMessage])

  useEffect(() => {
    if (!isHrParticipant || phase !== 'interview' || !candidatePresent) return
    if (aiInterviewStarted || hrStartTriggeredRef.current) return
    hrStartTriggeredRef.current = true
    showMessage('Candidate joined — starting AI interview.', 'success')
    void startInterview()
  }, [aiInterviewStarted, candidatePresent, isHrParticipant, phase, showMessage])

  const speakAiText = useCallback(async (
    current: CandidateSessionCredentials,
    text: string,
    autoListen = false,
  ): Promise<void> => {
    setConversationState('ai_speaking')
    try {
      await playSpokenText(current.sessionId, current.token, text, setAiSpeaking, ttsAudioRef as AudioPlayerRef)
    } catch (error) {
      showMessage(`Voice unavailable: ${errorMessage(error)}. Read the text on screen.`, 'warning')
    } finally {
      setConversationState('idle')
    }
    if (autoListen && phaseRef.current === 'interview' && !hrIntervention && !leavingInterviewRef.current && !isHrParticipantRef.current) {
      await startAnswerCaptureRef.current?.()
    }
  }, [showMessage, hrIntervention])

  const speakAiQuestion = useCallback(async (
    current: CandidateSessionCredentials,
    session: AiInterviewSessionResponse,
  ) => {
    if (hangingUpRef.current || leavingInterviewRef.current) return
    if (interviewStageRef.current === 'mcq') return
    if (isClosingSession(session)) {
      await speakClosingThenHangUpRef.current(current, session)
      return
    }
    const question = session.current_question
    const questionId = question?.id
    const text = question?.question_text
    if (!questionId && !text) return
    const speakKey = questionId || text || ''
    if (speakKey && speakingNowRef.current === speakKey) return
    speakingNowRef.current = speakKey
    lastBroadcastQuestionIdRef.current = questionId || null
    const ack = (session.turn_ack || '').trim()
    setConversationState('ai_speaking')
    try {
      if (ack && !question?.is_candidate_qna && !String(questionId || '').startsWith('qna-')) {
        await playSpokenText(
          current.sessionId,
          current.token,
          ack,
          setAiSpeaking,
          ttsAudioRef as AudioPlayerRef,
        )
      }
      if (question?.is_candidate_qna || String(questionId || '').startsWith('qna-')) {
        await playSpokenText(
          current.sessionId,
          current.token,
          text || '',
          setAiSpeaking,
          ttsAudioRef as AudioPlayerRef,
        )
      } else {
        await playQuestionAudio(
          current.sessionId,
          current.token,
          questionId,
          text,
          setAiSpeaking,
          ttsAudioRef as AudioPlayerRef,
        )
      }
    } catch (error) {
      showMessage(`Question voice unavailable: ${errorMessage(error)}. Read the question on screen.`, 'warning')
    } finally {
      if (speakingNowRef.current === speakKey) speakingNowRef.current = null
      setConversationState('idle')
    }
    if (
      phaseRef.current === 'interview'
      && !isClosingSession(session)
      && !hrIntervention
      && !leavingInterviewRef.current
      && !hangingUpRef.current
      && !isHrParticipantRef.current
    ) {
      await startAnswerCaptureRef.current?.()
    }
  }, [showMessage, hrIntervention])
  speakAiQuestionRef.current = speakAiQuestion

  const beginOralAfterMcq = useCallback(async (
    current: CandidateSessionCredentials,
    session: AiInterviewSessionResponse | null,
    oralRules?: string,
  ) => {
    if (oralStartedRef.current || hangingUpRef.current || leavingInterviewRef.current) return
    oralStartedRef.current = true
    setInterviewStage('oral')
    setMcqLockedOptionId(null)
    let oral = session
    if (!oral) {
      try {
        oral = await requestJson<AiInterviewSessionResponse>(
          `/api/interview/room/sessions/${current.sessionId}/ai/session`,
          {},
          current.token,
        )
        if (oral) setAiSession(oral)
      } catch {
        oral = null
      }
    }
    if (!isHrParticipantRef.current && oralRules) {
      await speakAiText(current, oralRules)
    }
    if (!isHrParticipantRef.current && oral && oral.status !== 'COMPLETED') {
      lastBroadcastQuestionIdRef.current = null
      speakingNowRef.current = null
      await speakAiQuestion(current, oral)
    }
    setIntroPlayed(true)
  }, [speakAiQuestion, speakAiText])
  beginOralAfterMcqRef.current = beginOralAfterMcq

  const applyMcqState = useCallback((next: McqStateResponse) => {
    setMcq(next)
    setMcqRemaining(Number(next.remaining_seconds || 0))
    if (isMcqDone(next)) {
      setMcqLockedOptionId(null)
      setInterviewStage('oral')
    } else if (isMcqActive(next)) {
      setInterviewStage('mcq')
    }
  }, [])

  const finishMcqAndBeginOral = useCallback(async (
    current: CandidateSessionCredentials,
    next: McqStateResponse,
  ) => {
    if (mcqFinishingRef.current && !isMcqDone(next)) return
    applyMcqState(next)
    if (!isMcqDone(next)) return
    mcqFinishingRef.current = true
    await beginOralAfterMcq(current, aiSession, next.oral_rules_message)
  }, [aiSession, applyMcqState, beginOralAfterMcq])

  const submitMcqChoice = useCallback(async (optionId?: string, skip = false) => {
    const current = credentialsRef.current
    if (!current || isHrParticipantRef.current || interviewStageRef.current !== 'mcq') return
    if (mcqBusyRef.current || mcqFinishingRef.current) return
    mcqBusyRef.current = true
    setMcqBusy(true)
    if (optionId) setMcqLockedOptionId(optionId)
    try {
      const next = await requestJson<McqStateResponse>(
        `/api/interview/room/sessions/${current.sessionId}/ai/mcq/answer`,
        jsonRequest('POST', {
          option_id: optionId || null,
          skip,
          question_id: mcqRef.current?.current_question?.id || null,
        }),
        current.token,
      )
      if (isMcqDone(next)) {
        await finishMcqAndBeginOral(current, next)
      } else {
        setMcqLockedOptionId(null)
        applyMcqState(next)
      }
    } catch (error) {
      setMcqLockedOptionId(null)
      showMessage(errorMessage(error), 'error')
    } finally {
      mcqBusyRef.current = false
      setMcqBusy(false)
    }
  }, [applyMcqState, finishMcqAndBeginOral, showMessage])

  const expireMcq = useCallback(async () => {
    const current = credentialsRef.current
    if (!current || isHrParticipantRef.current || mcqFinishingRef.current) return
    mcqFinishingRef.current = true
    try {
      const next = await requestJson<McqStateResponse>(
        `/api/interview/room/sessions/${current.sessionId}/ai/mcq/finish`,
        jsonRequest('POST', { timed_out: true }),
        current.token,
      )
      await finishMcqAndBeginOral(current, next)
    } catch (error) {
      mcqFinishingRef.current = false
      showMessage(errorMessage(error), 'error')
    }
  }, [finishMcqAndBeginOral, showMessage])

  useEffect(() => {
    if (interviewStage !== 'mcq' || mcq?.status !== 'in_progress') return
    const timer = window.setInterval(() => {
      setMcqRemaining((prev) => {
        if (prev <= 1) {
          window.clearInterval(timer)
          if (!isHrParticipantRef.current) void expireMcq()
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => window.clearInterval(timer)
  }, [expireMcq, interviewStage, mcq?.status])

  const stopTts = useCallback(() => {
    stopSpokenAudio(ttsAudioRef as AudioPlayerRef, setAiSpeaking)
    setConversationState('idle')
  }, [])

  const speakClosingThenHangUp = useCallback(async (
    current: CandidateSessionCredentials,
    session: AiInterviewSessionResponse,
  ) => {
    if (hangingUpRef.current || isHrParticipantRef.current) return
    hangingUpRef.current = true
    stopSilenceMonitor()
    submittingAnswerRef.current = true
    const text = (session.current_question?.question_text || '').trim() || CLOSING_FALLBACK
    lastBroadcastQuestionIdRef.current = session.current_question?.id || 'qna-close'
    setConversationState('ai_speaking')
    try {
      await awaitWithTimeout(
        playSpokenText(
          current.sessionId,
          current.token,
          text,
          setAiSpeaking,
          ttsAudioRef as AudioPlayerRef,
        ),
        45_000,
      )
    } catch (error) {
      showMessage(`Voice unavailable: ${errorMessage(error)}. Read the closing message on screen.`, 'warning')
    } finally {
      setConversationState('idle')
    }

    leavingInterviewRef.current = true
    stopTts()
    tearDownRoomPeer()
    setActive(false)
    activeRef.current = false
    setFinishState({
      title: 'Interview completed',
      text: 'Thank you. The AI interviewer has ended this session. Your HR team will follow up with next steps.',
    })
    setPhase('finished')
    setStep(4)
    try {
      await requestJson(`/api/interview/room/sessions/${current.sessionId}/leave`, jsonRequest('POST', {}), current.token)
    } catch {
      /* hang up locally even if leave fails */
    }
    try {
      await stopAndFinalizeRef.current('normal_completion')
    } catch {
      showMessage('Session ended. Report finalization can continue in the background.', 'notice')
    }
  }, [showMessage, stopSilenceMonitor, stopTts, tearDownRoomPeer])
  speakClosingThenHangUpRef.current = speakClosingThenHangUp

  const toggleCamera = useCallback(() => {
    const stream = streamRef.current
    if (!stream) return
    const next = !cameraEnabled
    stream.getVideoTracks().forEach((track) => {
      track.enabled = next
    })
    setCameraEnabled(next)
    syncInterviewVideos()
  }, [cameraEnabled, syncInterviewVideos])

  const toggleMic = useCallback(() => {
    const stream = streamRef.current
    if (!stream) return
    const next = !micEnabled
    stream.getAudioTracks().forEach((track) => {
      track.enabled = next
    })
    setMicEnabled(next)
  }, [micEnabled])

  const runHrControl = useCallback(async (
    action: 'skip' | 'next' | 'goto' | 'add_question' | 'speak' | 'return_to_ai',
    extra?: { question_text?: string; target_index?: number; ask_now?: boolean; message?: string },
  ) => {
    const current = credentialsRef.current
    if (!current || !isHrParticipantRef.current) return
    // Always interrupt TTS first so skip/next works mid-speech.
    stopTts()
    setBusy(`HR: ${action.replace('_', ' ')}`)
    try {
      const session = await requestJson<AiInterviewSessionResponse>(
        `/api/interview/room/sessions/${current.sessionId}/ai/hr-control`,
        jsonRequest('POST', { action, ...extra }),
        current.token,
      )
      setAiSession(session)
      setAiInterviewStarted(true)
      lastBroadcastQuestionIdRef.current = session.current_question?.id || null
      if (action === 'speak') {
        setHrSpeakingLocal(true)
        setHrIntervention(true)
        showMessage('You are speaking — AI is paused for the candidate.', 'notice')
      } else if (action === 'return_to_ai') {
        setHrSpeakingLocal(false)
        setHrIntervention(false)
        showMessage('Returned control to the AI interviewer.', 'success')
        if (session.current_question && session.status !== 'COMPLETED') {
          await speakAiQuestion(current, session)
        }
      } else if (session.status === 'COMPLETED') {
        showMessage('Interview question bank is complete.', 'success')
      } else if (session.current_question) {
        showMessage('Question updated for the candidate.', 'success')
        await speakAiQuestion(current, session)
      }
    } catch (error) {
      showMessage(errorMessage(error), 'error')
    } finally {
      setBusy('')
    }
  }, [showMessage, speakAiQuestion, stopTts])

  const startAnswerCapture = async () => {
    if (isHrParticipantRef.current) return
    if (interviewStageRef.current === 'mcq') return
    if (capturingAnswerRef.current || leavingInterviewRef.current || hangingUpRef.current) return
    try {
      const stream = streamRef.current
      if (!stream) throw new Error('Microphone is not available')
      stopSilenceMonitor()
      ttsAudioRef.current?.pause()
      window.speechSynthesis?.cancel()
      setAiSpeaking(false)
      answerChunksRef.current = []
      stopMediaStream(answerRecordStreamRef.current)
      const answerStream = cloneMediaStream(stream, 'audio')
      answerRecordStreamRef.current = answerStream
      const recorder = startMediaRecorder(answerStream, 1000, {}, true, (created) => {
        created.ondataavailable = (event) => {
          if (event.data.size) answerChunksRef.current.push(event.data)
        }
      })
      answerRecorderRef.current = recorder
      setCapturingAnswer(true)
      setConversationState('listening')
      silenceMonitorRef.current = startSilenceMonitor(stream, () => {
        if (!capturingAnswerRef.current || leavingInterviewRef.current || hangingUpRef.current) return
        void submitAnswerCaptureRef.current?.()
      })
    } catch (error) {
      stopMediaStream(answerRecordStreamRef.current)
      answerRecordStreamRef.current = null
      setConversationState('idle')
      showMessage(errorMessage(error), 'error')
    }
  }
  startAnswerCaptureRef.current = startAnswerCapture

  const submitAnswerCapture = async () => {
    const current = credentialsRef.current
    const session = aiSession
    if (!current || !session || leavingInterviewRef.current || hangingUpRef.current) return
    if (submittingAnswerRef.current) return
    submittingAnswerRef.current = true
    stopSilenceMonitor()
    const recorder = answerRecorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      await new Promise<void>((resolve) => {
        recorder.onstop = () => resolve()
        recorder.stop()
      })
    }
    answerRecorderRef.current = null
    stopMediaStream(answerRecordStreamRef.current)
    answerRecordStreamRef.current = null
    setCapturingAnswer(false)
    setConversationState('processing')
    setBusy('Processing your answer')
    try {
      const blob = new Blob(answerChunksRef.current, { type: supportedMime(true) || 'audio/webm' })
      if (!blob.size) throw new Error('No answer audio was captured.')
      const form = new FormData()
      form.append('file', blob, 'answer.webm')
      if (session.current_question?.id) form.append('question_id', session.current_question.id)
      const transcribed = await requestJson<{ text: string }>(
        `/api/interview/room/sessions/${current.sessionId}/ai/transcribe`,
        { method: 'POST', body: form },
        current.token,
        120_000,
      )
      const text = (transcribed.text || '').trim()
      if (!text) throw new Error('Could not detect your answer. Please speak clearly after the AI question.')
      const next = await requestJson<AiInterviewSessionResponse>(
        `/api/interview/room/sessions/${current.sessionId}/ai/answer`,
        jsonRequest('POST', { answer_text: text }),
        current.token,
        120_000,
      )
      setAiSession(next)
      if (next.duration_extended && !durationExtendedNotifiedRef.current) {
        durationExtendedNotifiedRef.current = true
        showMessage('Interview time was extended so remaining questions can be completed.', 'notice')
      }
      if (isClosingSession(next)) {
        await speakClosingThenHangUp(current, next)
        return
      }
      if (next.current_question?.is_candidate_qna) {
        showMessage('Interview questions are done. You can now share feedback or ask questions.', 'notice')
      }
      await speakAiQuestion(current, next)
    } catch (error) {
      setConversationState('idle')
      showMessage(errorMessage(error), 'error')
      if (phaseRef.current === 'interview' && !leavingInterviewRef.current) {
        await startAnswerCapture()
      }
    } finally {
      submittingAnswerRef.current = false
      setBusy('')
    }
  }
  submitAnswerCaptureRef.current = submitAnswerCapture

  const stopRecorders = useCallback(async () => {
    if (frameTimerRef.current) window.clearInterval(frameTimerRef.current)
    if (clockTimerRef.current) window.clearInterval(clockTimerRef.current)
    if (heartbeatTimerRef.current) window.clearInterval(heartbeatTimerRef.current)
    if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current)
    frameTimerRef.current = null
    clockTimerRef.current = null
    heartbeatTimerRef.current = null
    reconnectTimerRef.current = null

    socketRef.current?.close()
    socketRef.current = null

    try { audioNodeRef.current?.disconnect() } catch { /* no-op */ }
    try { audioSourceRef.current?.disconnect() } catch { /* no-op */ }
    try { audioGainRef.current?.disconnect() } catch { /* no-op */ }

    const context = audioContextRef.current
    if (context) {
      if (audioSampleCountRef.current >= context.sampleRate * 1.5) {
        const samples = mergePcm(audioChunksRef.current, audioSampleCountRef.current)
        const windowStartMs = Math.max(0, audioWindowStartedAtRef.current - startAtRef.current)
        const windowEndMs = Math.max(windowStartMs, Date.now() - startAtRef.current)
        const sequenceNumber = audioSequenceRef.current
        audioSequenceRef.current += 1
        enqueueAudioWindow({
          samples,
          sampleRate: context.sampleRate,
          windowStartMs,
          windowEndMs,
          sequenceNumber,
          segmentId: segmentIdRef.current || 'audio-segment-0',
        })
      }
      await drainAudioQueue()
      await context.close().catch(() => undefined)
    }
    audioContextRef.current = null
    audioNodeRef.current = null
    audioSourceRef.current = null
    audioGainRef.current = null
    audioChunksRef.current = []
    audioSampleCountRef.current = 0
    stopMediaStream(audioMonitorStreamRef.current)
    audioMonitorStreamRef.current = null

    const recorder = fullRecorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      stoppingRecorderRef.current = true
      await new Promise<void>((resolve, reject) => {
        let settled = false
        const timeout = window.setTimeout(() => {
          if (!settled) {
            settled = true
            reject(new Error('Full interview recorder did not stop within 10 seconds'))
          }
        }, 10000)
        recorder.addEventListener('stop', () => {
          if (!settled) {
            settled = true
            window.clearTimeout(timeout)
            resolve()
          }
        }, { once: true })
        recorder.stop()
      })
    }
    fullRecorderRef.current = null
    stopMediaStream(fullRecordStreamRef.current)
    fullRecordStreamRef.current = null
    stopMediaStream(answerRecordStreamRef.current)
    answerRecordStreamRef.current = null

    // Wait for the final dataavailable checksum and durable IndexedDB transaction.
    await chunkWritePromiseRef.current
    const current = credentialsRef.current
    if (!current) throw new Error('Candidate session is unavailable during recording finalization')

    // Drain queued chunks without relying on a fixed sleep.
    for (let attempt = 0; attempt < 8; attempt += 1) {
      await flushQueue()
      await chunkWritePromiseRef.current
      const queued = await getChunks(current.sessionId)
      if (queued.length === 0) break
      if (attempt === 7) throw new Error(`Recording upload queue still contains ${queued.length} chunk(s)`)
      await new Promise((resolve) => window.setTimeout(resolve, 250 * (attempt + 1)))
    }

    const segmentIds = [...segmentIdsRef.current]
    if (sequenceRef.current < 1 || segmentIds.length < 1) {
      throw new Error('No complete interview recording segment was captured')
    }

    // Backend verifies the global sequence range and that every MediaRecorder segment
    // received a final chunk before permitting FFmpeg assembly.
    for (let attempt = 0; attempt < 4; attempt += 1) {
      try {
        await requestJson(`/api/sessions/${current.sessionId}/recording/complete`, jsonRequest('POST', {
          expected_total_chunks: sequenceRef.current,
          segment_ids: segmentIds,
        }), current.token)
        return
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 409 || attempt === 3) throw error
        await flushQueue()
        await new Promise((resolve) => window.setTimeout(resolve, 300 * (attempt + 1)))
      }
    }
  }, [drainAudioQueue, enqueueAudioWindow, flushQueue])

  const stopAndFinalize = useCallback(async (reason: string) => {
    const current = credentialsRef.current
    if (!current || finishingRef.current) return
    finishingRef.current = true
    setBusy('Finalizing recording and report')
    try {
      activeRef.current = false
      setActive(false)
      await stopRecorders()
      const form = new FormData()
      form.append('reason', reason)
      const data = await requestJson<FinishResponse>(`/api/sessions/${current.sessionId}/finish`, { method: 'POST', body: form }, current.token)
      setPhase('finished')
      setStep(4)
      setTerminationReason(null)
      setFinishState({
        title: data.status === 'completed' ? 'Interview completed' : 'Interview terminated',
        text: `Status: ${data.status}.${data.termination_reason ? ` Reason: ${data.termination_reason}.` : ''} The admin can now review the recording, evidence, and report.`,
      })
      showMessage('Recording and report finalization completed.', 'success')
    } catch (error) {
      if (reason !== 'normal_completion') {
        try {
          const recovered = await requestJson<{ status: string; report_completeness: string; termination_reason?: string | null }>(
            `/api/sessions/${current.sessionId}/recover-finalization`,
            jsonRequest('POST', {}),
            current.token,
          )
          setPhase('finished')
          setStep(4)
          setTerminationReason(null)
          setFinishState({
            title: 'Interview terminated',
            text: `Status: ${recovered.status}. Reason: ${recovered.termination_reason ?? reason}. A ${recovered.report_completeness} report is available for authorized review.`,
          })
          showMessage('Termination was preserved and report recovery completed.', 'warning')
        } catch (recoveryError) {
          showMessage(`${errorMessage(error)} Recovery also failed: ${errorMessage(recoveryError)}`, 'error')
        }
      } else if (hangingUpRef.current || phaseRef.current === 'finished') {
        showMessage('Interview ended. Report finalization can continue in the background.', 'notice')
      } else {
        setResumeRequired(true)
        showMessage(`${errorMessage(error)} Resume recording and retry completion.`, 'error')
      }
    } finally {
      finishingRef.current = false
      setBusy('')
    }
  }, [showMessage, stopRecorders])
  stopAndFinalizeRef.current = stopAndFinalize

  const sendTabEpisode = useCallback(async (episode: TabVisibilityEpisode, visibleReturnedAt: string, hiddenDurationMs: number) => {
    const current = credentialsRef.current
    if (!activeRef.current || finishingRef.current || !current || hiddenDurationMs < TAB_MIN_HIDDEN_MS) return
    try {
      const data = await requestJson<TabSwitchResponse>(`/api/sessions/${current.sessionId}/tab-switch`, jsonRequest('POST', {
        signal: 'visibility_episode',
        episode_id: episode.episodeId,
        client_timestamp: visibleReturnedAt,
        relative_ms: Math.max(0, Date.now() - startAtRef.current),
        visibility_state: document.visibilityState,
        hidden_started_at: episode.hiddenStartedAt,
        visible_returned_at: visibleReturnedAt,
        hidden_duration_ms: hiddenDurationMs,
        focus_lost: episode.focusLost,
        triggering_events: episode.triggeringEvents,
      }), current.token)
      if (data.action === 'warn') {
        showMessage(data.message || 'Warning: the interview page was hidden. A second confirmed switch will terminate the interview.', 'warning')
      }
      if (data.action === 'terminate') {
        terminateUi(data.termination_reason)
        await stopAndFinalize('repeated_tab_switch')
      }
    } catch (error) {
      console.warn('Tab visibility episode failed', error)
    }
  }, [showMessage, stopAndFinalize, terminateUi])

  useEffect(() => {
    if (phase !== 'interview' || isHrParticipant) return
    // Win+Tab / Alt+Tab opens OS task switcher — the page stays "visible" but
    // the window loses focus. We treat a blur lasting ≥ 1 s as a virtual episode.
    const WIN_TAB_BLUR_MS = 1000
    let blurTimerId: ReturnType<typeof window.setTimeout> | null = null
    let blurStartedAt = 0

    const addEpisodeEvent = (name: string) => {
      const episode = tabVisibilityEpisodeRef.current
      if (episode && !episode.triggeringEvents.includes(name)) episode.triggeringEvents.push(name)
    }
    const visibility = () => {
      if (!activeRef.current || finishingRef.current) return
      if (document.visibilityState === 'hidden') {
        if (!tabVisibilityEpisodeRef.current) {
          const now = Date.now()
          tabVisibilityEpisodeRef.current = {
            episodeId: crypto.randomUUID(),
            hiddenStartedAt: new Date(now).toISOString(),
            hiddenStartedMs: now,
            focusLost: !document.hasFocus(),
            triggeringEvents: ['visibilitychange:hidden'],
          }
        } else {
          addEpisodeEvent('visibilitychange:hidden:duplicate')
        }
        return
      }

      const episode = tabVisibilityEpisodeRef.current
      if (!episode) return
      addEpisodeEvent('visibilitychange:visible')
      tabVisibilityEpisodeRef.current = null
      const visibleAt = Date.now()
      const hiddenDurationMs = Math.max(0, visibleAt - episode.hiddenStartedMs)
      if (hiddenDurationMs >= TAB_MIN_HIDDEN_MS) {
        void sendTabEpisode(episode, new Date(visibleAt).toISOString(), hiddenDurationMs)
      }
    }
    const blur = () => {
      if (!activeRef.current || finishingRef.current) return
      const episode = tabVisibilityEpisodeRef.current
      if (episode) {
        episode.focusLost = true
        addEpisodeEvent('window:blur')
      }
      // Win+Tab / Alt+Tab: page stays visible but window loses focus.
      // Start a timer — if focus does not return within WIN_TAB_BLUR_MS treat as switch.
      if (!tabVisibilityEpisodeRef.current) {
        blurStartedAt = Date.now()
        blurTimerId = window.setTimeout(() => {
          if (!activeRef.current || finishingRef.current || tabVisibilityEpisodeRef.current) return
          if (document.hasFocus()) return
          const now = Date.now()
          const hiddenDurationMs = Math.max(0, now - blurStartedAt)
          const episode = {
            episodeId: crypto.randomUUID(),
            hiddenStartedAt: new Date(blurStartedAt).toISOString(),
            hiddenStartedMs: blurStartedAt,
            focusLost: true,
            triggeringEvents: ['window:blur:sustained'],
          }
          void sendTabEpisode(episode, new Date(now).toISOString(), hiddenDurationMs)
          showMessage('Warning: you switched away from the interview window. This has been recorded.', 'warning')
        }, WIN_TAB_BLUR_MS)
      }
    }
    const focus = () => {
      if (blurTimerId !== null) {
        window.clearTimeout(blurTimerId)
        blurTimerId = null
      }
      addEpisodeEvent('window:focus')
    }
    const pageHide = () => addEpisodeEvent('pagehide')
    const pageShow = () => addEpisodeEvent('pageshow')
    const online = () => void flushQueue()
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (activeRef.current) {
        event.preventDefault()
        event.returnValue = 'Interview recording is active.'
      }
    }
    document.addEventListener('visibilitychange', visibility)
    window.addEventListener('blur', blur)
    window.addEventListener('focus', focus)
    window.addEventListener('pagehide', pageHide)
    window.addEventListener('pageshow', pageShow)
    window.addEventListener('online', online)
    window.addEventListener('beforeunload', beforeUnload)
    return () => {
      if (blurTimerId !== null) window.clearTimeout(blurTimerId)
      document.removeEventListener('visibilitychange', visibility)
      window.removeEventListener('blur', blur)
      window.removeEventListener('focus', focus)
      window.removeEventListener('pagehide', pageHide)
      window.removeEventListener('pageshow', pageShow)
      window.removeEventListener('online', online)
      window.removeEventListener('beforeunload', beforeUnload)
      tabVisibilityEpisodeRef.current = null
    }
  }, [phase, isHrParticipant, flushQueue, sendTabEpisode, showMessage])


  useEffect(() => {
    if (!['127.0.0.1', 'localhost'].includes(location.hostname)) return
    window.__agent5Diagnostics = {
      session: () => ({ sessionId: credentialsRef.current?.sessionId ?? null, active: activeRef.current, sequence: sequenceRef.current }),
      replaceStream: async (stream: MediaStream) => {
        if (!stream.getVideoTracks().length || !stream.getAudioTracks().length) {
          throw new Error('Replacement stream requires audio and video tracks')
        }
        streamRef.current = stream
        attachStream()
        return { video: stream.getVideoTracks()[0].readyState, audio: stream.getAudioTracks()[0].readyState }
      },
    }
    return () => { delete window.__agent5Diagnostics }
  }, [attachStream])

  useEffect(() => () => {
    if (messageTimerRef.current) window.clearTimeout(messageTimerRef.current)
    if (!activeRef.current) streamRef.current?.getTracks().forEach((track) => track.stop())
    setFacePhotoUrl((current) => {
      if (current) URL.revokeObjectURL(current)
      return null
    })
  }, [])

  const canStart = useMemo(() => Object.values(biometrics).every(Boolean) && devices.camera === 'ready' && devices.microphone === 'ready' && mandatoryModelsReady, [biometrics, devices, mandatoryModelsReady])

  const startBlockers = useMemo(() => {
    const missing: string[] = []
    if (!biometrics.faceEnrolled || !biometrics.faceVerified) missing.push('face verification')
    if (!biometrics.voiceEnrolled) missing.push('voice enrollment')
    else if (!biometrics.voiceVerified) missing.push('voice identity confirmation — speak the sentence once more')
    if (devices.camera !== 'ready' || devices.microphone !== 'ready') missing.push('camera and microphone checks')
    if (!mandatoryModelsReady) missing.push('required AI models')
    return missing
  }, [biometrics, devices, mandatoryModelsReady])

  const confirmLeaveInterview = useCallback(async () => {
    const current = credentialsRef.current
    leavingInterviewRef.current = true
    setLeaveOpen(false)
    stopSilenceMonitor()
    stopTts()
    tearDownRoomPeer()
    activeRef.current = false
    setActive(false)
    setPhase('finished')
    setStep(4)
    setFinishState({
      title: isHrParticipantRef.current ? 'Left HR control room' : 'Interview ended',
      text: isHrParticipantRef.current
        ? 'You left the HR control room. The candidate session continues unless you ended it from the dashboard.'
        : 'Thank you. Your session is being finalized. You may close this tab.',
    })
    if (current) {
      try {
        const leave = await requestJson<{
          can_rejoin?: boolean
          finalize_session?: boolean
          room_join_count?: number
          max_room_joins?: number
        }>(`/api/interview/room/sessions/${current.sessionId}/leave`, jsonRequest('POST', {}), current.token)
        if (!isHrParticipantRef.current && leave.finalize_session) {
          await stopAndFinalize('candidate_left')
        } else if (!isHrParticipantRef.current) {
          const used = Number(leave.room_join_count || 0)
          const maxJoins = Number(leave.max_room_joins || 3)
          setFinishState({
            title: 'Interview paused',
            text: `You left the interview. HR has a report of the questions you answered. You may rejoin ${Math.max(0, maxJoins - used)} more time(s) (${used} of ${maxJoins} used).`,
          })
        }
      } catch {
        /* finalize anyway */
        if (!isHrParticipantRef.current) {
          await stopAndFinalize('candidate_left')
        }
      }
    }
    sessionStorage.removeItem('agent5-session')
    if (document.fullscreenElement) {
      try { await document.exitFullscreen() } catch { /* ignore */ }
    }
    closeInterviewTab()
  }, [closeInterviewTab, stopAndFinalize, stopSilenceMonitor, stopTts, tearDownRoomPeer])

  useEffect(() => {
    const onFullscreen = () => {
      if (leavingInterviewRef.current || phaseRef.current !== 'interview') return
      if (isHrParticipantRef.current) {
        setFullscreenLost(false)
        return
      }
      const lost = !document.fullscreenElement
      setFullscreenLost(lost)
      if (lost) {
        window.setTimeout(() => {
          if (!leavingInterviewRef.current && phaseRef.current === 'interview' && !isHrParticipantRef.current) {
            void enterFullscreen()
          }
        }, 400)
      }
    }
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (leavingInterviewRef.current) return
      if (phaseRef.current !== 'interview' || !activeRef.current) return
      event.preventDefault()
      event.returnValue = 'Are you sure you want to leave the interview?'
    }
    const onPopState = () => {
      if (phaseRef.current !== 'interview') return
      window.history.pushState(null, '', window.location.href)
      setLeaveOpen(true)
    }
    document.addEventListener('fullscreenchange', onFullscreen)
    window.addEventListener('beforeunload', onBeforeUnload)
    window.addEventListener('popstate', onPopState)
    if (phase === 'interview') {
      window.history.pushState(null, '', window.location.href)
    }
    return () => {
      document.removeEventListener('fullscreenchange', onFullscreen)
      window.removeEventListener('beforeunload', onBeforeUnload)
      window.removeEventListener('popstate', onPopState)
    }
  }, [phase])

  return (
    <>
      {phase !== 'interview' && <TopBar title="AI Interview" badge="Secure session" />}
      {facePhotoUrl && phase === 'interview' && !isHrParticipant && (
        <aside className={`identity-snapshot ${phase === 'interview' ? 'in-room' : ''}`} aria-label="Identity photo">
          <img src={facePhotoUrl} alt="" />
        </aside>
      )}
      <main className={phase === 'interview' ? `interview-shell${isHrParticipant ? ' hr-shell' : ''}` : phase === 'enrollment' || phase === 'devices' ? 'shell enrollment-stage' : 'shell'}>
        {phase !== 'interview' && <Stepper current={step} />}
        {phase !== 'interview' && (
          <div id="message">
            <MessageBanner
              text={message.text}
              kind={message.kind}
              onDismiss={() => setMessage({ text: '', kind: 'notice' })}
            />
          </div>
        )}
        {busy && <div className="busy-banner"><Spinner label={busy} /></div>}

        {sessionGate === 'loading' && (
          <section className="card hero-card">
            <Spinner label="Loading interview session" />
          </section>
        )}

        {sessionGate === 'missing' && (
          <section className="card hero-card" id="registration">
            <div className="section-kicker">Interview access</div>
            <h1>Invalid or expired interview link</h1>
            <p className="lead">
              Open the secure join link from your interview confirmation email. Direct registration is disabled.
            </p>
          </section>
        )}

        {sessionGate === 'blocked' && (
          <section className="card completion-card" id="sessionBlocked">
            <BrandMark subtitle="Interview access" />
            <div className="completion-icon blocked">!</div>
            <h2>{accessError?.title || 'This interview is no longer available'}</h2>
            <p>{accessError?.text || 'Please contact HR if you need a new interview link.'}</p>
            <div className="controls" style={{ justifyContent: 'center', marginTop: 20 }}>
              <button type="button" onClick={closeInterviewTab}>Close this tab</button>
            </div>
          </section>
        )}

        {sessionGate === 'ready' && phase === 'registration' && (
          <section className="card hero-card" id="registration">
            <Spinner label="Preparing verification session" />
          </section>
        )}

        {sessionGate === 'ready' && phase === 'devices' && (
          <section className="card" id="devices">
            <div className="section-header">
              <div><div className="section-kicker">Step 1</div><h2>Camera and microphone check</h2></div>
            </div>
            <div className="grid two">
              <div className="video-wrap">
                <video id="preview" ref={previewRef} autoPlay muted playsInline />
                <span id="cameraBadge" className="video-badge">{devices.camera === 'ready' ? 'Camera active' : 'Allow camera'}</span>
              </div>
              <div className="panel-content">
                <p>Allow camera and microphone access in this browser. Both must pass before face photos and the interview can continue.</p>
                <div className="status-row">
                  <span id="cameraStatus"><StatusPill label={devices.camera === 'ready' ? 'Camera ready' : devices.camera === 'failed' ? 'Camera failed' : 'Camera pending'} state={devices.camera === 'ready' ? 'ok' : devices.camera === 'failed' ? 'bad' : 'neutral'} /></span>
                  <span id="micStatus"><StatusPill label={devices.microphone === 'ready' ? 'Microphone ready' : devices.microphone === 'failed' ? 'Microphone failed' : 'Microphone pending'} state={devices.microphone === 'ready' ? 'ok' : devices.microphone === 'failed' ? 'bad' : 'neutral'} /></span>
                </div>
                <div className="controls"><button id="deviceButton" type="button" onClick={checkDevices} disabled={Boolean(busy)}>Check devices</button></div>
              </div>
            </div>
          </section>
        )}

        {sessionGate === 'ready' && phase === 'enrollment' && (
          <section className="card" id="enrollment">
            <div className="section-header">
              <div><div className="section-kicker">Step 2</div><h2>Identity photos and voice</h2></div>
              <span className="privacy-badge">Still photos only</span>
            </div>
            <div className="video-wrap compact-video">
              <video id="preview" ref={previewRef} autoPlay muted playsInline />
              <span className="video-badge">Live viewfinder — take a still photo</span>
              {facePhotoUrl && (
                <aside className="viewfinder-snapshot" aria-label="Latest face photo">
                  <img src={facePhotoUrl} alt="" />
                </aside>
              )}
              <div className="viewfinder-actions" role="group" aria-label="Face photo controls">
                <button
                  id={biometrics.faceEnrolled ? 'faceVerify' : 'faceEnroll'}
                  type="button"
                  className="viewfinder-btn capture"
                  onClick={() => void handleFace(biometrics.faceEnrolled ? 'verify' : 'enroll')}
                  disabled={Boolean(busy) || biometrics.faceVerified}
                  aria-label={biometrics.faceEnrolled ? 'Capture verification photo' : 'Capture face photo'}
                >
                  <svg className="viewfinder-btn-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                    <path fill="currentColor" d="M9 3 7.17 5H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-3.17L15 3H9Zm3 15a5 5 0 1 1 0-10 5 5 0 0 1 0 10Zm0-2.2A2.8 2.8 0 1 0 12 10.2a2.8 2.8 0 0 0 0 5.6Z" />
                  </svg>
                  <span>
                    {biometrics.faceVerified
                      ? 'Verified'
                      : biometrics.faceEnrolled
                        ? 'Capture'
                        : `Capture${faceSampleCount > 0 ? ` (${faceSampleCount}/3)` : ''}`}
                  </span>
                </button>
                <button
                  id="faceRecapture"
                  type="button"
                  className="viewfinder-btn recapture"
                  onClick={() => void handleFace(biometrics.faceEnrolled ? 'verify' : 'enroll')}
                  disabled={Boolean(busy) || biometrics.faceVerified || (!facePhotoUrl && faceSampleCount < 1)}
                  aria-label="Recapture face photo"
                >
                  Recapture
                </button>
              </div>
            </div>
            <div className="grid two enrollment-grid">
              <article className="subcard">
                <div className="subcard-heading"><span className="feature-icon">F</span><div><h3>Face photo</h3><p>Look at the camera and use Capture or Recapture on the viewfinder. Your latest photo appears as a circle in the top-right corner.</p></div></div>
                <div className="status-row">
                  <StatusPill label={biometrics.faceEnrolled ? 'Captured' : 'Not captured'} state={biometrics.faceEnrolled ? 'ok' : 'neutral'} />
                  <StatusPill label={biometrics.faceVerified ? 'Face verified' : 'Not verified'} state={biometrics.faceVerified ? 'ok' : 'neutral'} />
                </div>
                <div id="faceResult">{faceResult && (() => {
                  const copy = faceStatusCopy(biometrics.faceEnrolled && !biometrics.faceVerified ? 'verify' : (biometrics.faceVerified ? 'verify' : 'enroll'), faceResult)
                  return (
                    <div className={`result-box ${copy.ok ? 'success' : 'error'}`}>
                      <strong>{copy.title}</strong>
                      <span>{copy.detail}</span>
                    </div>
                  )
                })()}</div>
              </article>

              <article className="subcard">
                <div className="subcard-heading"><span className="feature-icon">V</span><div><h3>Voice identity and sentence confirmation</h3><p>Read the highlighted sentence naturally. First we enroll your voice, then you speak it once more to confirm identity.</p></div></div>
                <div className="voice-prompt" aria-live="polite">
                  {voiceSentence ? voiceProgress.words.map((word) => (
                    <span key={`${word.expectedIndex}-${word.expected}`} className={`voice-word ${word.state}`} aria-label={`${word.expected}: ${word.state}`}>
                      <span aria-hidden="true">{word.state === 'completed' ? '✓' : word.state === 'skipped' ? '↷' : word.state === 'incorrect' ? '!' : word.state === 'current' ? '▶' : '•'}</span>
                      {word.expected}
                    </span>
                  )) : <span>Loading verification sentence…</span>}
                </div>
                <p className="voice-progress" id="voiceProgress">
                  {voiceRecording
                    ? (isLiveDictationSupported()
                      ? 'Listening… please read the full sentence clearly.'
                      : 'Recording… please read the full sentence clearly.')
                    : 'Read every word of the sentence. If it is not captured in full, you will be asked to try again.'}
                </p>
                {recognizedTranscript && <p className="recognized-text"><strong>{voiceRecording ? 'Live transcript:' : 'Whisper transcript:'}</strong> {recognizedTranscript}</p>}
                {transcriptionError && <p className="field-error">Transcription: {transcriptionError}</p>}
                <div className="status-row">
                  <StatusPill label={biometrics.voiceEnrolled ? 'Voice captured' : 'Not captured'} state={biometrics.voiceEnrolled ? 'ok' : 'neutral'} />
                  <StatusPill label={biometrics.voiceVerified ? 'Voice verified' : 'Not verified'} state={biometrics.voiceVerified ? 'ok' : 'neutral'} />
                </div>
                <div className="controls">
                  <button id="changeVoiceSentence" type="button" className="secondary" onClick={() => void loadVoiceSentence(true)} disabled={Boolean(busy) || voiceRecording || biometrics.voiceEnrolled}>Change sentence</button>
                  {biometrics.voiceEnrolled ? (
                    <button id="voiceVerify" type="button" onClick={() => void handleVoice('verify')} disabled={Boolean(busy) || !voiceSentence}>
                      {biometrics.voiceVerified ? 'Re-verify speaker' : 'Confirm it is you'}
                    </button>
                  ) : (
                    <button id="voiceEnroll" type="button" onClick={() => void handleVoice('enroll')} disabled={Boolean(busy) || !voiceSentence}>Enroll your voice</button>
                  )}
                </div>
                <div id="voiceResult">{voiceResult && (() => {
                  const captured = voiceFullyCaptured(voiceResult)
                  const copy = voiceStatusCopy(biometrics.voiceVerified || (biometrics.voiceEnrolled && captured) ? 'verify' : 'enroll', captured)
                  return (
                    <div className={`result-box ${copy.ok ? 'success' : 'error'}`}>
                      <strong>{copy.title}</strong>
                      <span>{copy.detail}</span>
                    </div>
                  )
                })()}</div>
              </article>
            </div>
            <div className="start-panel">
              <div>
                <strong>{canStart ? 'Ready to enter the interview' : 'Finish identity checks'}</strong>
                <p>
                  {canStart
                    ? 'Click the button below. Chrome will hide tabs, the address bar, and window controls for this interview. Press Esc only if you must leave fullscreen.'
                    : `Start stays locked until you finish ${startBlockers.join(', ')}.`}
                </p>
              </div>
              <button id="startButton" type="button" onClick={() => void startInterview()} disabled={Boolean(busy) || !canStart}>
                {resumeRequired ? 'Open interview in fullscreen' : 'Start AI interview in fullscreen'}
              </button>
            </div>
          </section>
        )}

        {sessionGate === 'ready' && phase === 'interview' && (
          <section className={`meet-room${isHrParticipant ? ' hr-room' : ''}`} id="interview">
            {fullscreenLost && !isHrParticipant && (
              <div className="meet-fullscreen-blocker" role="alertdialog" aria-modal="true">
                <div className="meet-fullscreen-card">
                  <h2>Return to interview mode</h2>
                  <p>The interview must stay in fullscreen until you finish. Click below to continue.</p>
                  <button type="button" className="meet-control-btn primary" onClick={() => void enterFullscreen()}>
                    <FullscreenIcon /> Return to fullscreen
                  </button>
                </div>
              </div>
            )}
            {message.text && (
              <div className={`meet-interview-notice ${message.kind}`} role="status">
                {message.text}
              </div>
            )}
            <header className="meet-topbar">
              <div className="meet-topbar-left">
                <BrandMark subtitle="" size="sm" />
                <div>
                  <div className="meet-topbar-title">{brand.interviewTitle}</div>
                  <div className="meet-topbar-sub">{candidateDisplayName || 'Candidate'}{candidateJobTitle ? ` · ${candidateJobTitle}` : ''}</div>
                </div>
              </div>
              <div className="meet-topbar-right">
                {isHrParticipant && (
                  <span className={`meet-presence ${candidatePresent ? 'ok' : 'wait'}`}>
                    <PersonIcon width={14} height={14} />
                    {candidatePresent ? 'Candidate in room' : 'Waiting for candidate'}
                  </span>
                )}
                <span className="meet-timer" aria-label="Meeting timer">
                  {elapsed}
                  {aiSession?.planned_duration_minutes
                    ? ` / ${String(aiSession.planned_duration_minutes).padStart(2, '0')}:00`
                    : ''}
                  {aiSession?.duration_extended ? ' +ext' : ''}
                </span>
              </div>
            </header>
            {isHrParticipant && !aiInterviewStarted && (
              <div className="hr-banner hr-wait-banner">
                {candidatePresent
                  ? 'Candidate joined — starting AI interview…'
                  : 'Do not start yet — waiting for the candidate to join this room.'}
              </div>
            )}
            {hrIntervention && !isHrParticipant && (
              <div className="hr-banner">HR is speaking. The AI interviewer is paused. {hrMessage}</div>
            )}
            <div className="meet-stage">
              <div className="meet-video-pane meet-video-stage">
                <video id="liveVideo" ref={liveVideoRef} autoPlay muted playsInline />
                <div className="meet-video-overlay meet-video-overlay-top">
                  <div className="meet-question-label">{interviewStage === 'mcq' ? 'MCQ test' : 'Current question'}</div>
                  <p className={`meet-overlay-question-text${interviewStage === 'mcq' ? ' mcq-lock' : ''}`}>{currentQuestionText}</p>
                  <p className={`meet-overlay-question-meta${interviewStage === 'mcq' ? ' mcq-lock' : ''}`}>{currentQuestionMeta}</p>
                </div>
                <div className="meet-tile-chrome">
                  <span className={`meet-rec-badge${active && !isHrParticipant ? ' live' : ''}`}>
                    {isHrParticipant ? 'HR VIEW' : active ? `REC ${elapsed}` : 'Camera live'}
                  </span>
                  {otherPartyPresent && !remoteStream && (
                    <span className="meet-remote-wait">Connecting video…</span>
                  )}
                  <div className="meet-tile-nameplate">
                    <PersonIcon width={16} height={16} />
                    <span>{mainParticipantLabel}</span>
                    {pinnedView === 'local' && !micEnabled && <MicOffIcon width={14} height={14} />}
                    {pinnedView === 'local' && !cameraEnabled && <CamOffIcon width={14} height={14} />}
                  </div>
                </div>
                {remoteStream ? (
                  <button
                    type="button"
                    className="meet-pip-tile"
                    onClick={() => setPinnedView((current) => (current === 'local' ? 'remote' : 'local'))}
                    aria-label={`Pin ${pipParticipantLabel}`}
                    title={`Pin ${pipParticipantLabel}`}
                  >
                    <video ref={pipVideoRef} autoPlay muted playsInline />
                    <span className="meet-pip-label">{pipParticipantLabel}</span>
                    <span className="meet-pip-pin" aria-hidden="true"><PinIcon width={14} height={14} /></span>
                  </button>
                ) : (
                  <video ref={pipVideoRef} className="meet-pip-hidden" autoPlay playsInline aria-hidden="true" tabIndex={-1} />
                )}
                {pinnedView === 'local' && !cameraEnabled && (
                  <div className="meet-cam-off">
                    <CamOffIcon width={48} height={48} />
                    <span>Camera is off</span>
                  </div>
                )}
                <div className="meet-video-overlay meet-video-overlay-bottom">
                  <div className="meet-fab-rail meet-fab-rail-overlay" role="toolbar" aria-label="Meeting controls">
                    {isHrParticipant && (
                      <>
                        <MeetFab
                          label={micEnabled ? 'Turn microphone off' : 'Turn microphone on'}
                          variant={micEnabled ? 'default' : 'off'}
                          onClick={toggleMic}
                        >
                          {micEnabled ? <MicIcon /> : <MicOffIcon />}
                        </MeetFab>
                        <MeetFab
                          label={cameraEnabled ? 'Turn camera off' : 'Turn camera on'}
                          variant={cameraEnabled ? 'default' : 'off'}
                          onClick={toggleCamera}
                        >
                          {cameraEnabled ? <CamIcon /> : <CamOffIcon />}
                        </MeetFab>
                        <MeetFab label="Stop TTS" variant="default" onClick={() => stopTts()}>
                          <SpeakerOffIcon />
                        </MeetFab>
                      </>
                    )}
                    <MeetFab
                      label={isHrParticipant ? 'Leave room' : 'End interview'}
                      variant="danger"
                      disabled={Boolean(busy) && conversationState === 'processing' && !isHrParticipant}
                      onClick={() => setLeaveOpen(true)}
                    >
                      <HangUpIcon />
                    </MeetFab>
                  </div>
                </div>
              </div>
              <div className="meet-side-panel">
                <div className="meet-ai-card meet-tile">
                  <div className="meet-ai-header">
                    <div className="meet-ai-avatar" aria-hidden="true">
                      {isHrParticipant ? <PersonIcon /> : <BotIcon />}
                    </div>
                    <div className="meet-ai-meta">
                      <h3>{isHrParticipant ? 'Live interview controls' : interviewStage === 'mcq' ? 'MCQ test' : 'AI Interviewer'}</h3>
                      <p>{currentQuestionMeta}</p>
                    </div>
                  </div>
                  {isHrParticipant ? (
                    <div className="hr-control-panel">
                      <div className="hr-control-row hr-icon-row">
                        <MeetFab label="Stop TTS" variant="default" onClick={() => stopTts()}>
                          <SpeakerOffIcon />
                        </MeetFab>
                        {!hrSpeakingLocal ? (
                          <MeetFab label="Speak (pause AI)" variant="primary" disabled={Boolean(busy) && !aiSpeaking} onClick={() => void runHrControl('speak')}>
                            <PauseIcon />
                          </MeetFab>
                        ) : (
                          <MeetFab label="Return to AI" variant="primary" disabled={Boolean(busy) && !aiSpeaking} onClick={() => void runHrControl('return_to_ai')}>
                            <PlayIcon />
                          </MeetFab>
                        )}
                        <MeetFab label="Skip question" variant="default" disabled={interviewStage === 'mcq' || (Boolean(busy) && !aiSpeaking)} onClick={() => void runHrControl('skip')}>
                          <SkipIcon />
                        </MeetFab>
                        <MeetFab label="Next question" variant="default" disabled={interviewStage === 'mcq' || (Boolean(busy) && !aiSpeaking)} onClick={() => void runHrControl('next')}>
                          <NextIcon />
                        </MeetFab>
                      </div>
                      {!aiInterviewStarted && candidatePresent && (
                        <button type="button" className="meet-control-btn primary meet-text-btn" disabled={Boolean(busy)} onClick={() => void startInterview()}>
                          <PlayIcon width={18} height={18} /> Start AI interview now
                        </button>
                      )}
                      {interviewStage === 'mcq' && mcq ? (
                        <McqPanel
                          mcq={mcq}
                          remainingSeconds={mcqRemaining}
                          lockedOptionId={mcqLockedOptionId}
                          busy={mcqBusy}
                          isHr
                          onSelect={() => undefined}
                          onSkip={() => undefined}
                        />
                      ) : (
                      <>
                      <div className="hr-question-list">
                        <div className="meet-question-label">All questions</div>
                        <ul>
                          {(aiSession?.questions || []).map((q, idx) => {
                            const activeQ = idx === (aiSession?.current_index ?? -1)
                            return (
                              <li key={q.id || idx} className={activeQ ? 'active' : ''}>
                                <button
                                  type="button"
                                  disabled={interviewStage === 'mcq' || (Boolean(busy) && !aiSpeaking)}
                                  onClick={() => void runHrControl('goto', { target_index: idx })}
                                >
                                  <span>{idx + 1}.</span> {q.question_text || 'Question'}
                                  {q.added_by_hr ? ' (HR)' : ''}
                                </button>
                              </li>
                            )
                          })}
                        </ul>
                        {(aiSession?.questions || []).length === 0 && (
                          <p className="muted" style={{ margin: '8px 0 0', color: '#9aa0a6', fontSize: 13 }}>
                            Question list appears after the AI interview starts.
                          </p>
                        )}
                      </div>
                      <div className="hr-add-question">
                        <textarea
                          value={hrNewQuestion}
                          onChange={(e) => setHrNewQuestion(e.target.value)}
                          placeholder="Add a live question for the candidate…"
                          rows={3}
                        />
                        <button
                          type="button"
                          className="meet-control-btn primary meet-text-btn"
                          disabled={interviewStage === 'mcq' || (Boolean(busy) && !aiSpeaking) || !hrNewQuestion.trim() || !aiInterviewStarted}
                          onClick={() => {
                            const text = hrNewQuestion.trim()
                            setHrNewQuestion('')
                            void runHrControl('add_question', { question_text: text, ask_now: true })
                          }}
                        >
                          <AddIcon width={18} height={18} /> Add & ask now
                        </button>
                      </div>
                      </>
                      )}
                    </div>
                  ) : interviewStage === 'mcq' && mcq ? (
                    <McqPanel
                      mcq={mcq}
                      remainingSeconds={mcqRemaining}
                      lockedOptionId={mcqLockedOptionId}
                      busy={mcqBusy}
                      isHr={false}
                      onSelect={(optionId) => void submitMcqChoice(optionId)}
                      onSkip={() => void submitMcqChoice(undefined, true)}
                    />
                  ) : (
                    <>
                      <p className={`meet-status-line ${conversationState === 'ai_speaking' || aiSpeaking ? 'speaking' : conversationState === 'listening' || capturingAnswer ? 'listening' : conversationState === 'processing' ? 'speaking' : ''}`}>
                        {conversationState === 'processing' || busy
                          ? 'Processing your answer…'
                          : aiSpeaking || conversationState === 'ai_speaking'
                            ? 'AI is speaking — please listen'
                            : capturingAnswer || conversationState === 'listening'
                              ? 'Your turn — speak naturally, we detect when you finish'
                              : hrIntervention
                                ? 'Paused for HR'
                                : 'Waiting for the AI interviewer'}
                      </p>
                    </>
                  )}
                </div>
                {!isHrParticipant && (
                  <div className="meet-status-stack">
                    <div><span>Camera</span><StatusPill label={faceLive.state === 'bad' ? 'Adjust position' : 'Active'} state={faceLive.state} /></div>
                    <div><span>Microphone</span><StatusPill label={capturingAnswer ? 'Recording answer' : voiceLive.state === 'bad' ? 'Check mic' : 'Active'} state={capturingAnswer ? 'ok' : voiceLive.state === 'bad' ? 'bad' : 'ok'} /></div>
                    <div><span>Session</span><StatusPill label={active ? 'Recording' : 'Paused'} state={active ? 'ok' : 'warning'} /></div>
                    <div><span>Connection</span><StatusPill label={connectionLive.label} state={connectionLive.state} /></div>
                  </div>
                )}
              </div>
            </div>
          </section>
        )}

        {sessionGate === 'ready' && phase === 'finished' && finishState && (
          <section className="card completion-card" id="finished">
            <BrandMark subtitle="Interview complete" />
            <div className="completion-icon">✓</div>
            <h2 id="finishTitle">{finishState.title}</h2>
            <p id="finishText">{finishState.text}</p>
            <p className="lead">Your HR team will review the proctoring report in the main application.</p>
            <div className="controls" style={{ justifyContent: 'center', marginTop: 20 }}>
              <button type="button" onClick={closeInterviewTab}>Close this tab</button>
            </div>
          </section>
        )}

        {phase !== 'interview' && (
          <p className="page-footer">{brand.footer}</p>
        )}
      </main>

      {leaveOpen && (
        <div className="overlay" role="alertdialog" aria-modal="true">
          <div className="termination-card">
            <h1>Leave the interview?</h1>
            <p>Are you sure you want to leave the interview? Leaving may end your session.</p>
            <div className="controls">
              <button type="button" onClick={() => setLeaveOpen(false)}>Continue interview</button>
              <button type="button" className="danger" onClick={() => void confirmLeaveInterview()}>Leave interview</button>
            </div>
          </div>
        </div>
      )}

      {terminationReason && (
        <div className="overlay" role="alertdialog" aria-modal="true">
          <div className="termination-card">
            <div className="termination-icon">!</div>
            <h1>Interview terminated</h1>
            <p>Reason: {terminationReason}. Recording and evidence are being finalized.</p>
            {busy && <Spinner label={busy} />}
          </div>
        </div>
      )}
    </>
  )
}
