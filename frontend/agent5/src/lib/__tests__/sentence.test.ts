import { describe, expect, it } from 'vitest'

import { evaluateLiveSentence, normalizeSentenceWords } from '../sentence'

describe('voice sentence highlighting', () => {
  it('normalizes punctuation and case', () => {
    expect(normalizeSentenceWords('Clear, COMMUNICATION works.'))
      .toEqual(['clear', 'communication', 'works'])
  })

  it('keeps completed words, marks the next word current, and leaves later words pending', () => {
    const result = evaluateLiveSentence(
      'Honesty and regular effort help us achieve meaningful success.',
      'Honesty and regular',
    )
    expect(result.words.slice(0, 3).map((word) => word.state)).toEqual([
      'completed',
      'completed',
      'completed',
    ])
    expect(result.words[3].state).toBe('current')
    expect(result.words.slice(4).every((word) => word.state === 'pending')).toBe(true)
    expect(result.skippedCount).toBe(0)
    expect(result.completedCount).toBe(3)
  })

  it('marks an interior missing word as skipped once later words are recognized', () => {
    const result = evaluateLiveSentence(
      'Good preparation builds confidence before every important interview.',
      'Good preparation confidence before',
    )
    expect(result.words.find((word) => word.expected === 'builds')?.state).toBe('skipped')
    expect(result.words.find((word) => word.expected === 'every')?.state).toBe('current')
  })

  it('marks incorrect words without treating transcript success as speaker identity', () => {
    const result = evaluateLiveSentence(
      'Good preparation builds confidence before every important interview.',
      'Good planning builds confidence before every important interview',
    )
    expect(result.words.some((word) => word.state === 'incorrect')).toBe(true)
    expect(result).not.toHaveProperty('speakerVerified')
  })
})
