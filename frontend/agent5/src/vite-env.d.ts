/// <reference types="vite/client" />

interface Window {
  webkitAudioContext?: typeof AudioContext
  __agent5Diagnostics?: {
    session: () => { sessionId: string | null; active: boolean; sequence: number }
    replaceStream: (stream: MediaStream) => Promise<{ video: MediaStreamTrackState; audio: MediaStreamTrackState }>
  }
}

interface ImportMetaEnv {
  readonly VITE_AGENT5_FRAME_REQUEST_TIMEOUT_MS?: string
  readonly VITE_AGENT5_AUDIO_REQUEST_TIMEOUT_MS?: string
  readonly VITE_INTERVIEW_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

