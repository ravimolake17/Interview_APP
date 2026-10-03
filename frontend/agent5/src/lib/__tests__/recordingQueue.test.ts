import { describe, expect, it, vi } from 'vitest'
import { flushRecordingQueue } from '../recordingQueue'
import type { RecordingChunkQueueItem } from '../idbQueue'

function queued(sequence: number): RecordingChunkQueueItem {
  return {
    key: `session-a:segment-a:${sequence}:${sequence}`,
    sessionId: 'session-a',
    sequence,
    segmentId: 'segment-a',
    segmentSequence: sequence,
    isFinal: sequence === 2,
    capturedAt: new Date(sequence * 5000).toISOString(),
    durationMs: 5000,
    checksum: String(sequence).padStart(64, '0'),
    blob: new Blob([`chunk-${sequence}`], { type: 'video/webm' }),
    mimeType: 'video/webm',
  }
}

describe('recording upload queue', () => {
  it('drains acknowledged chunks in sequence order', async () => {
    const removed: string[] = []
    const upload = vi.fn(
      async (
        _path: string,
        _options: RequestInit,
        _token?: string,
      ): Promise<unknown> => ({ created: true }),
    )
    const result = await flushRecordingQueue('session-a', 'token-a', {
      read: async () => [queued(0), queued(1), queued(2)],
      remove: async (key) => { removed.push(key) },
      upload,
    })

    expect(result).toEqual({ uploaded: 3, deferred: 0 })
    expect(removed).toEqual([
      'session-a:segment-a:0:0',
      'session-a:segment-a:1:1',
      'session-a:segment-a:2:2',
    ])
    expect(upload).toHaveBeenCalledTimes(3)
    const firstCall = upload.mock.calls[0]
    expect(firstCall).toBeDefined()
    if (!firstCall) throw new Error('Expected the first upload call')
    const firstForm = firstCall[1].body as FormData
    expect(firstForm.get('sequence')).toBe('0')
    expect(firstForm.get('segment_sequence')).toBe('0')
    expect(firstForm.get('is_final')).toBe('false')
  })

  it('treats duplicate acknowledgement as successful', async () => {
    const remove = vi.fn(async () => undefined)
    const result = await flushRecordingQueue('session-a', 'token-a', {
      read: async () => [queued(0)],
      remove,
      upload: async (
        _path: string,
        _options: RequestInit,
        _token?: string,
      ): Promise<unknown> => ({ created: false, duplicate: true }),
    })

    expect(result).toEqual({ uploaded: 1, deferred: 0 })
    expect(remove).toHaveBeenCalledWith('session-a:segment-a:0:0')
  })

  it('retains the failed chunk and all later chunks for retry', async () => {
    const remove = vi.fn(async () => undefined)
    const upload = vi.fn(
      async (
        _path: string,
        _options: RequestInit,
        _token?: string,
      ): Promise<unknown> => ({ created: true }),
    )
    upload
      .mockResolvedValueOnce({ created: true })
      .mockRejectedValueOnce(new Error('network offline'))

    const result = await flushRecordingQueue('session-a', 'token-a', {
      read: async () => [queued(0), queued(1), queued(2)],
      remove,
      upload,
    })

    expect(result).toEqual({ uploaded: 1, deferred: 2 })
    expect(remove).toHaveBeenCalledTimes(1)
    expect(remove).toHaveBeenCalledWith('session-a:segment-a:0:0')
    expect(upload).toHaveBeenCalledTimes(2)
  })

  it('treats duplicate sequence conflicts as acknowledged', async () => {
    const { ApiError } = await import('../api')
    const remove = vi.fn(async () => undefined)
    const result = await flushRecordingQueue('session-a', 'token-a', {
      read: async () => [queued(0), queued(1)],
      remove,
      upload: async () => {
        throw new ApiError(409, 'sequence already exists with different checksum')
      },
    })

    expect(result).toEqual({ uploaded: 2, deferred: 0 })
    expect(remove).toHaveBeenCalledTimes(2)
  })

  it('stops flushing when recording upload is already complete', async () => {
    const { ApiError } = await import('../api')
    const remove = vi.fn(async () => undefined)
    const result = await flushRecordingQueue('session-a', 'token-a', {
      read: async () => [queued(0), queued(1)],
      remove,
      upload: async () => {
        throw new ApiError(409, 'recording upload is already marked complete')
      },
    })

    expect(result).toEqual({ uploaded: 0, deferred: 2 })
    expect(remove).not.toHaveBeenCalled()
  })
})
