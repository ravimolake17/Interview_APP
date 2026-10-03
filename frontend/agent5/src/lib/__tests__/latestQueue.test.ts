import { describe, expect, it } from 'vitest'

import { LatestQueue } from '../latestQueue'

describe('LatestQueue', () => {
  it('drops stale oldest work and reports queue telemetry', () => {
    const queue = new LatestQueue<number>(2)
    queue.push(1)
    queue.push(2)
    queue.push(3)
    expect(queue.depth).toBe(2)
    expect(queue.shift()).toBe(2)
    expect(queue.shift()).toBe(3)
    expect(queue.takeDropped()).toBe(1)
    expect(queue.takeDropped()).toBe(0)
  })
})
