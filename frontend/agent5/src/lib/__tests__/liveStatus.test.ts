import { describe, expect, it } from 'vitest'
import { faceLiveStatus, voiceLiveStatus } from '../liveStatus'

describe('truthful live detector status mapping', () => {
  it('never invents zero faces when a technical result has no count', () => {
    expect(faceLiveStatus({ status: 'stale_frame', face_count: null }).label).toBe('Frame analysis delayed')
    expect(faceLiveStatus({ status: 'frame_decode_error', face_count: null }).label).toBe('Camera frame could not be processed')
    expect(faceLiveStatus({}).label).toBe('Frame analysis unavailable')
  })

  it('keeps face count and identity separate', () => {
    expect(faceLiveStatus({ face_state: 'face_detected', face_count: 1 }).label).toContain('verification pending')
    expect(faceLiveStatus({ face_state: 'face_match', face_count: 1, face_verification: { passed: true, label: 'face_match', confidence: 0.9, measurements: {} } }).label).toBe('Face matched')
  })

  it('does not display insufficient speech as a voice mismatch', () => {
    const status = voiceLiveStatus({ passed: false, label: 'insufficient_speech', confidence: 1, measurements: {} })
    expect(status.label).toBe('Insufficient speech')
    expect(status.state).toBe('neutral')
  })
})
