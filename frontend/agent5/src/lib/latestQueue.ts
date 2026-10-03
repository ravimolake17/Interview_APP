/**
 * Small bounded latest-first queue for live analysis work.
 * When full, the oldest unprocessed item is discarded so latency cannot grow
 * without bound. The dropped count is exposed as detector telemetry.
 */
export class LatestQueue<T> {
  private readonly items: T[] = []
  private droppedSinceRead = 0

  constructor(readonly capacity: number) {
    if (!Number.isInteger(capacity) || capacity < 1) {
      throw new Error('LatestQueue capacity must be a positive integer')
    }
  }

  push(item: T): void {
    while (this.items.length >= this.capacity) {
      this.items.shift()
      this.droppedSinceRead += 1
    }
    this.items.push(item)
  }

  shift(): T | undefined {
    return this.items.shift()
  }

  takeDropped(): number {
    const value = this.droppedSinceRead
    this.droppedSinceRead = 0
    return value
  }

  clear(): void {
    this.items.length = 0
    this.droppedSinceRead = 0
  }

  get depth(): number {
    return this.items.length
  }
}
