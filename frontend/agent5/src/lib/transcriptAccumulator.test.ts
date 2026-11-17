import { describe, expect, it } from 'vitest'
import { TranscriptAccumulator } from './transcriptAccumulator'
import { floatToPcm16k } from './streamingStt'

describe('TranscriptAccumulator', () => {
  it('keeps partials out of finalized text', () => {
    const acc = new TranscriptAccumulator()
    acc.setPartial('I built a')
    expect(acc.finalizedText(false)).toBe('')
    expect(acc.displayText()).toBe('I built a')
    acc.addFinalSegment('I built a FastAPI service.')
    expect(acc.finalizedText()).toBe('I built a FastAPI service.')
    acc.setPartial('with Redis')
    expect(acc.displayText()).toContain('with Redis')
    expect(acc.finalizedText()).toBe('I built a FastAPI service.')
  })

  it('dedupes identical consecutive finals', () => {
    const acc = new TranscriptAccumulator()
    expect(acc.addFinalSegment('Hello world.')).toBe(true)
    expect(acc.addFinalSegment('Hello world.')).toBe(false)
    expect(acc.segmentCount).toBe(1)
  })
})

describe('floatToPcm16k', () => {
  it('emits int16 pcm and supports linear downsample', () => {
    const input = new Float32Array(480) // 10ms at 48k
    for (let i = 0; i < input.length; i += 1) input[i] = Math.sin(i / 10)
    const buf = floatToPcm16k(input, 48_000)
    expect(buf.byteLength).toBeGreaterThan(0)
    expect(buf.byteLength % 2).toBe(0)
    // ~160 samples at 16k for 10ms
    expect(new Int16Array(buf).length).toBeGreaterThanOrEqual(150)
    expect(new Int16Array(buf).length).toBeLessThanOrEqual(170)
  })

  it('passes through same-rate audio', () => {
    const input = new Float32Array([0, 0.5, -0.5, 1])
    const buf = floatToPcm16k(input, 16_000)
    expect(new Int16Array(buf).length).toBe(4)
  })
})
