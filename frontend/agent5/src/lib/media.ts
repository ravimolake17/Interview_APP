export function supportedMime(audioOnly = false): string {
  const options = audioOnly
    ? ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
    : ['video/webm;codecs=vp8,opus', 'video/webm;codecs=vp9,opus', 'video/webm', 'video/mp4']
  return options.find((option) => MediaRecorder.isTypeSupported(option)) ?? ''
}

export function cloneMediaStream(stream: MediaStream, kind?: 'audio' | 'video'): MediaStream {
  const tracks = (kind ? stream.getTracks().filter((track) => track.kind === kind) : stream.getTracks())
    .map((track) => track.clone())
  return new MediaStream(tracks)
}

export function stopMediaStream(stream: MediaStream | null | undefined): void {
  stream?.getTracks().forEach((track) => {
    try {
      track.stop()
    } catch {
      /* already stopped */
    }
  })
}

export function startMediaRecorder(
  stream: MediaStream,
  timesliceMs: number,
  options: MediaRecorderOptions = {},
  audioOnly = false,
  attach?: (recorder: MediaRecorder) => void,
): MediaRecorder {
  const mimeType = options.mimeType || supportedMime(audioOnly)
  const attempts: Array<MediaRecorderOptions | undefined> = [
    { ...options, ...(mimeType ? { mimeType } : {}) },
    Object.keys(options).length ? { videoBitsPerSecond: options.videoBitsPerSecond, audioBitsPerSecond: options.audioBitsPerSecond } : undefined,
    undefined,
  ]
  let lastError: unknown
  for (const attempt of attempts) {
    try {
      const recorder = attempt ? new MediaRecorder(stream, attempt) : new MediaRecorder(stream)
      attach?.(recorder)
      recorder.start(timesliceMs)
      if (recorder.state !== 'recording') {
        throw new Error('MediaRecorder did not enter the recording state')
      }
      return recorder
    } catch (error) {
      lastError = error
    }
  }
  throw lastError instanceof Error ? lastError : new Error('Could not start MediaRecorder')
}

export async function sha256(blob: Blob): Promise<string> {
  const bytes = await blob.arrayBuffer()
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  return [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, '0')).join('')
}

export function captureVideoFrame(video: HTMLVideoElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || video.videoWidth < 160 || video.videoHeight < 120) {
      reject(new Error('Camera frame is not ready'))
      return
    }
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const context = canvas.getContext('2d')
    if (!context) {
      reject(new Error('Canvas rendering is unavailable'))
      return
    }
    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    // Reject an uninitialised or blank canvas before it is sent to the backend.
    // Browsers can report HAVE_CURRENT_DATA briefly while the first decoded
    // webcam frame is still black, especially immediately after a stream swap.
    const sampleWidth = Math.min(64, canvas.width)
    const sampleHeight = Math.min(48, canvas.height)
    const sample = context.getImageData(0, 0, sampleWidth, sampleHeight).data
    let sum = 0
    let sumSquares = 0
    let pixels = 0
    for (let index = 0; index < sample.length; index += 16) {
      const luminance = 0.2126 * sample[index] + 0.7152 * sample[index + 1] + 0.0722 * sample[index + 2]
      sum += luminance
      sumSquares += luminance * luminance
      pixels += 1
    }
    const mean = pixels ? sum / pixels : 0
    const variance = pixels ? Math.max(0, sumSquares / pixels - mean * mean) : 0
    if (mean < 2 || variance < 0.5) {
      reject(new Error('Camera returned a blank frame'))
      return
    }
    canvas.toBlob((blob) => {
      if (blob) resolve(blob)
      else reject(new Error('Could not capture a camera frame'))
    }, 'image/jpeg', 0.9)
  })
}

export function mergePcm(chunks: Float32Array[], total: number): Float32Array {
  const merged = new Float32Array(total)
  let offset = 0
  for (const chunk of chunks) {
    merged.set(chunk, offset)
    offset += chunk.length
  }
  return merged
}

export function pcmToWav(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  const write = (offset: number, text: string) => {
    for (let index = 0; index < text.length; index += 1) {
      view.setUint8(offset + index, text.charCodeAt(index))
    }
  }
  write(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  write(8, 'WAVE')
  write(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  write(36, 'data')
  view.setUint32(40, samples.length * 2, true)
  let offset = 44
  for (const value of samples) {
    const clipped = Math.max(-1, Math.min(1, value))
    view.setInt16(offset, clipped < 0 ? clipped * 32768 : clipped * 32767, true)
    offset += 2
  }
  return new Blob([buffer], { type: 'audio/wav' })
}

export function formatElapsed(milliseconds: number): string {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remaining = seconds % 60
  if (hours > 0) {
    return [hours, minutes, remaining].map((value) => String(value).padStart(2, '0')).join(':')
  }
  return [minutes, remaining].map((value) => String(value).padStart(2, '0')).join(':')
}
