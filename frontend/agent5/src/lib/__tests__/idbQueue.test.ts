import { beforeEach, describe, expect, it } from 'vitest'
import { deleteChunk, getChunks, putChunk, type RecordingChunkQueueItem } from '../idbQueue'

function item(sequence: number): RecordingChunkQueueItem {
  return {
    key: `session-a:${sequence}`,
    sessionId: 'session-a',
    sequence,
    segmentId: 'segment-1',
    segmentSequence: sequence,
    isFinal: sequence === 2,
    capturedAt: new Date(0).toISOString(),
    durationMs: 5000,
    checksum: String(sequence).padStart(64, '0'),
    blob: new Blob([String(sequence)], { type: 'video/webm' }),
    mimeType: 'video/webm',
  }
}

describe('IndexedDB recording recovery queue', () => {
  beforeEach(async () => {
    for (const queued of await getChunks('session-a')) await deleteChunk(queued.key)
  })

  it('persists, sorts, and deletes recording chunks', async () => {
    await putChunk(item(2))
    await putChunk(item(0))
    await putChunk(item(1))
    expect((await getChunks('session-a')).map((value) => value.sequence)).toEqual([0, 1, 2])
    await deleteChunk('session-a:1')
    expect((await getChunks('session-a')).map((value) => value.sequence)).toEqual([0, 2])
  })

  it('replaces duplicate sequence keys idempotently', async () => {
    await putChunk(item(1))
    await putChunk({ ...item(1), durationMs: 7000 })
    const queued = await getChunks('session-a')
    expect(queued).toHaveLength(1)
    expect(queued[0].durationMs).toBe(7000)
  })
})
