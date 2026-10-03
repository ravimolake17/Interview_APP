import { beforeEach, describe, expect, it, vi } from 'vitest'
import { formatElapsed, mergePcm, pcmToWav, sha256, supportedMime } from '../media'

describe('media utilities', () => {
  beforeEach(() => {
    vi.stubGlobal('MediaRecorder', { isTypeSupported: vi.fn((value: string) => value.includes('vp8') || value.includes('opus')) })
  })

  it('selects a supported recording MIME type', () => {
    expect(supportedMime(false)).toBe('video/webm;codecs=vp8,opus')
    expect(supportedMime(true)).toBe('audio/webm;codecs=opus')
  })

  it('computes a deterministic SHA-256 checksum', async () => {
    const result = await sha256(new Blob(['agent5']))
    expect(result).toMatch(/^[a-f0-9]{64}$/)
    expect(result).toBe(await sha256(new Blob(['agent5'])))
  })

  it('merges PCM without losing sequence order', () => {
    expect([...mergePcm([new Float32Array([1, 2]), new Float32Array([3])], 3)]).toEqual([1, 2, 3])
  })

  it('writes a valid mono PCM WAV header and clips samples', async () => {
    const wav = pcmToWav(new Float32Array([-2, 0, 2]), 16000)
    const bytes = new Uint8Array(await wav.arrayBuffer())
    expect(new TextDecoder().decode(bytes.slice(0, 4))).toBe('RIFF')
    expect(new TextDecoder().decode(bytes.slice(8, 12))).toBe('WAVE')
    expect(wav.type).toBe('audio/wav')
    expect(wav.size).toBe(50)
  })

  it('formats elapsed interview time', () => {
    expect(formatElapsed(-1)).toBe('00:00')
    expect(formatElapsed(65_000)).toBe('01:05')
    expect(formatElapsed(3_661_000)).toBe('01:01:01')
  })
})
