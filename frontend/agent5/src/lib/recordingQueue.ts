import { deleteChunk, getChunks, type RecordingChunkQueueItem } from './idbQueue'
import { ApiError, requestJson } from './api'

export type ChunkReader = (sessionId: string) => Promise<RecordingChunkQueueItem[]>
export type ChunkDeleter = (key: string) => Promise<void>
export type ChunkUploader = (
  path: string,
  options: RequestInit,
  token?: string,
) => Promise<unknown>

export interface QueueFlushResult {
  uploaded: number
  deferred: number
}

function conflictDetail(error: unknown): string {
  if (!(error instanceof ApiError)) return ''
  return String(error.detail ?? error.message ?? '').toLowerCase()
}

function isDuplicateChunkConflict(error: unknown): boolean {
  if (!(error instanceof ApiError) || error.status !== 409) return false
  const detail = conflictDetail(error)
  return detail.includes('already exists') || detail.includes('duplicate')
}

function isTerminalChunkConflict(error: unknown): boolean {
  if (!(error instanceof ApiError) || error.status !== 409) return false
  const detail = conflictDetail(error)
  return (
    detail.includes('already marked complete')
    || detail.includes('not accepted')
    || detail.includes('not active')
  )
}

/**
 * Upload queued recording chunks in sequence order. The first failed upload is
 * retained along with all later chunks so reconnect recovery cannot create a
 * hidden sequence gap. Any successful server acknowledgement, including an
 * idempotent duplicate acknowledgement, permits the local copy to be deleted.
 */
export async function flushRecordingQueue(
  sessionId: string,
  token: string,
  dependencies: {
    read?: ChunkReader
    remove?: ChunkDeleter
    upload?: ChunkUploader
  } = {},
): Promise<QueueFlushResult> {
  const read = dependencies.read ?? getChunks
  const remove = dependencies.remove ?? deleteChunk
  const upload: ChunkUploader = dependencies.upload
    ?? ((path, options, requestToken) =>
      requestJson<unknown>(path, options, requestToken))
  const chunks = await read(sessionId)
  let uploaded = 0

  for (const item of chunks) {
    const form = new FormData()
    form.append('sequence', String(item.sequence))
    form.append('segment_id', item.segmentId)
    form.append('segment_sequence', String(item.segmentSequence))
    form.append('is_final', String(item.isFinal))
    form.append('captured_at', item.capturedAt)
    form.append('duration_ms', String(item.durationMs))
    form.append('checksum', item.checksum)
    form.append('chunk', item.blob, item.mimeType.includes('mp4') ? `chunk_${item.sequence}.mp4` : `chunk_${item.sequence}.webm`)

    try {
      await upload(`/api/sessions/${sessionId}/recording/chunks`, { method: 'POST', body: form }, token)
      await remove(item.key)
      uploaded += 1
    } catch (error) {
      if (isDuplicateChunkConflict(error)) {
        await remove(item.key)
        uploaded += 1
        continue
      }
      console.warn('Recording chunk upload deferred', error)
      if (isTerminalChunkConflict(error)) {
        break
      }
      break
    }
  }

  return { uploaded, deferred: Math.max(0, chunks.length - uploaded) }
}
