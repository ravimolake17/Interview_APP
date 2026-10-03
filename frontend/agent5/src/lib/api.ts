export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail))
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

let interviewApiOrigin = String(import.meta.env.VITE_INTERVIEW_API_URL || '').replace(/\/$/, '')
let runtimeConfigPromise: Promise<void> | null = null

export function loadRuntimeConfig(): Promise<void> {
  if (!runtimeConfigPromise) {
    runtimeConfigPromise = fetch('/api/runtime-config')
      .then((response) => (response.ok ? response.json() : {}))
      .then((data: { interview_api_origin?: string }) => {
        const origin = String(data?.interview_api_origin || '').replace(/\/$/, '')
        if (origin) interviewApiOrigin = origin
      })
      .catch(() => {
        /* same-origin mode */
      })
  }
  return runtimeConfigPromise
}

export function resolveApiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path
  if (path.startsWith('/api/interview') && interviewApiOrigin) {
    return `${interviewApiOrigin}${path}`
  }
  return path
}

async function parseResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) {
    return response.json()
  }
  return response.text()
}

export async function requestJson<T>(path: string, options: RequestInit = {}, token?: string, timeoutMs = 30_000): Promise<T> {
  const headers = new Headers(options.headers)
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  const controller = new AbortController()
  const upstreamSignal = options.signal
  const abortFromUpstream = () => controller.abort(upstreamSignal?.reason)
  if (upstreamSignal) {
    if (upstreamSignal.aborted) abortFromUpstream()
    else upstreamSignal.addEventListener('abort', abortFromUpstream, { once: true })
  }
  const timeout = window.setTimeout(() => controller.abort(new DOMException('Request timed out', 'TimeoutError')), timeoutMs)
  let response: Response
  try {
    response = await fetch(resolveApiUrl(path), { ...options, headers, signal: controller.signal })
  } catch (error) {
    if (controller.signal.aborted && !upstreamSignal?.aborted) {
      throw new Error(`Request timed out after ${timeoutMs} ms`)
    }
    throw error
  } finally {
    window.clearTimeout(timeout)
    upstreamSignal?.removeEventListener('abort', abortFromUpstream)
  }
  const body = await parseResponse(response)
  if (!response.ok) {
    const detail = typeof body === 'object' && body !== null && 'detail' in body
      ? (body as { detail: unknown }).detail
      : body
    throw new ApiError(response.status, detail)
  }
  return body as T
}

export async function requestBlob(path: string, options: RequestInit = {}, token?: string, timeoutMs = 120_000): Promise<Blob> {
  const headers = new Headers(options.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(new DOMException('Request timed out', 'TimeoutError')), timeoutMs)
  try {
    const response = await fetch(resolveApiUrl(path), { ...options, headers, signal: controller.signal })
    if (!response.ok) {
      const body = await parseResponse(response)
      const detail = typeof body === 'object' && body !== null && 'detail' in body
        ? (body as { detail: unknown }).detail
        : body
      throw new ApiError(response.status, detail)
    }
    return response.blob()
  } finally {
    window.clearTimeout(timeout)
  }
}

export function jsonRequest(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}
