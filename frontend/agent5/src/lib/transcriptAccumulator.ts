/**
 * Client-side mirror of backend TranscriptAccumulator.
 * Partials stay separate from finals; finals are ordered and de-duplicated.
 */

function normalizeForDedupe(text: string): string {
  return text.toLowerCase().split(/\s+/).filter(Boolean).join(' ')
}

export class TranscriptAccumulator {
  private segments: string[] = []
  private partial = ''

  setPartial(text: string): void {
    this.partial = text.trim().replace(/\s+/g, ' ')
  }

  clearPartial(): void {
    this.partial = ''
  }

  addFinalSegment(text: string): boolean {
    let cleaned = text.trim().replace(/\s+/g, ' ')
    if (!cleaned) return false
    if (this.segments.length) {
      const prev = this.segments[this.segments.length - 1] || ''
      if (prev === cleaned || normalizeForDedupe(prev) === normalizeForDedupe(cleaned)) {
        this.partial = ''
        return false
      }
      const prevTokens = prev.split(' ')
      const nextTokens = cleaned.split(' ')
      const maxOverlap = Math.min(8, prevTokens.length, nextTokens.length)
      for (let size = maxOverlap; size > 2; size -= 1) {
        if (prevTokens.slice(-size).join(' ') === nextTokens.slice(0, size).join(' ')) {
          cleaned = nextTokens.slice(size).join(' ').trim()
          break
        }
      }
      if (!cleaned) {
        this.partial = ''
        return false
      }
    }
    this.segments.push(cleaned)
    this.partial = ''
    return true
  }

  displayText(): string {
    const parts = [...this.segments]
    if (this.partial) parts.push(this.partial)
    return parts.join(' ').trim()
  }

  finalizedText(includeTrailingPartialIfEmpty = true): string {
    const joined = this.segments.join(' ').trim()
    if (joined) return joined
    if (includeTrailingPartialIfEmpty && this.partial) return this.partial
    return ''
  }

  reset(): void {
    this.segments = []
    this.partial = ''
  }

  get segmentCount(): number {
    return this.segments.length
  }
}
