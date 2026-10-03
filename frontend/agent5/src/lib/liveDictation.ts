/** Browser live dictation for enrollment word highlighting (Chrome / Edge). */

export type LiveDictationHandle = {
  stop: () => void
  supported: boolean
}

type SpeechRecognitionLike = {
  continuous: boolean
  interimResults: boolean
  lang: string
  maxAlternatives: number
  start: () => void
  stop: () => void
  abort: () => void
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onerror: ((event: { error?: string }) => void) | null
  onend: (() => void) | null
}

type SpeechRecognitionEventLike = {
  resultIndex: number
  results: ArrayLike<{
    isFinal: boolean
    0: { transcript: string }
  }>
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike

function getSpeechRecognitionCtor(): SpeechRecognitionCtor | null {
  const w = window as Window & {
    SpeechRecognition?: SpeechRecognitionCtor
    webkitSpeechRecognition?: SpeechRecognitionCtor
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

export function isLiveDictationSupported(): boolean {
  return getSpeechRecognitionCtor() !== null
}

/**
 * Starts continuous interim speech recognition and reports the full transcript
 * so sentence word chips can turn green as each word is spoken.
 */
export function startLiveDictation(
  onTranscript: (transcript: string) => void,
  options?: { lang?: string },
): LiveDictationHandle {
  const Ctor = getSpeechRecognitionCtor()
  if (!Ctor) {
    return { supported: false, stop: () => undefined }
  }

  let stopped = false
  let recognition: SpeechRecognitionLike | null = null
  let finalTranscript = ''

  const startInstance = () => {
    if (stopped) return
    const instance = new Ctor()
    recognition = instance
    instance.continuous = true
    instance.interimResults = true
    instance.lang = options?.lang ?? 'en-US'
    instance.maxAlternatives = 1

    instance.onresult = (event) => {
      let interim = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const piece = event.results[i][0]?.transcript ?? ''
        if (event.results[i].isFinal) {
          finalTranscript = `${finalTranscript} ${piece}`.replace(/\s+/g, ' ').trim()
        } else {
          interim += piece
        }
      }
      const combined = `${finalTranscript} ${interim}`.replace(/\s+/g, ' ').trim()
      if (combined) onTranscript(combined)
    }

    instance.onerror = () => {
      // Keep recording path alive; Whisper still runs server-side at the end.
    }

    instance.onend = () => {
      // Chrome stops after pauses; restart until we explicitly stop.
      if (!stopped) {
        try {
          startInstance()
        } catch {
          /* ignore restart failures */
        }
      }
    }

    try {
      instance.start()
    } catch {
      /* already started */
    }
  }

  startInstance()

  return {
    supported: true,
    stop: () => {
      stopped = true
      const instance = recognition
      recognition = null
      if (!instance) return
      instance.onresult = null
      instance.onerror = null
      instance.onend = null
      try {
        instance.stop()
      } catch {
        try {
          instance.abort()
        } catch {
          /* ignore */
        }
      }
    },
  }
}
