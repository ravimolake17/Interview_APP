export type WordState = 'pending' | 'current' | 'completed' | 'skipped' | 'incorrect'

export interface LiveWordResult {
  expectedIndex: number
  expected: string
  recognized?: string
  state: WordState
}

export interface LiveSentenceResult {
  words: LiveWordResult[]
  completionPercentage: number
  completedCount: number
  skippedCount: number
  incorrectCount: number
  extraWords: string[]
}

export function normalizeWords(text: string): string[] {
  return text.toLowerCase().match(/[a-z]+(?:'[a-z]+)?/g) ?? []
}

// Explicit alias used by tests and UI-facing sentence terminology.
export const normalizeSentenceWords = normalizeWords

export function evaluateLiveSentence(expectedText: string, transcript: string): LiveSentenceResult {
  const expected = normalizeWords(expectedText)
  const recognized = normalizeWords(transcript)
  const rows = expected.length + 1
  const cols = recognized.length + 1
  const cost = Array.from({ length: rows }, () => Array<number>(cols).fill(0))
  const op = Array.from({ length: rows }, () => Array<string>(cols).fill(''))
  for (let i = 1; i < rows; i += 1) { cost[i][0] = i; op[i][0] = 'delete' }
  for (let j = 1; j < cols; j += 1) { cost[0][j] = j; op[0][j] = 'insert' }
  for (let i = 1; i < rows; i += 1) {
    for (let j = 1; j < cols; j += 1) {
      const same = expected[i - 1] === recognized[j - 1]
      const candidates: Array<[number, string, number]> = [
        [cost[i - 1][j - 1] + (same ? 0 : 1), same ? 'equal' : 'replace', 0],
        [cost[i - 1][j] + 1, 'delete', 1],
        [cost[i][j - 1] + 1, 'insert', 2],
      ]
      candidates.sort((a, b) => a[0] - b[0] || a[2] - b[2])
      cost[i][j] = candidates[0][0]
      op[i][j] = candidates[0][1]
    }
  }

  const aligned: Array<{ operation: string; expected?: string; recognized?: string }> = []
  let i = expected.length
  let j = recognized.length
  while (i || j) {
    const operation = op[i][j]
    if (operation === 'equal' || operation === 'replace') {
      aligned.push({ operation, expected: expected[i - 1], recognized: recognized[j - 1] })
      i -= 1
      j -= 1
    } else if (operation === 'delete') {
      aligned.push({ operation, expected: expected[i - 1] })
      i -= 1
    } else if (operation === 'insert') {
      aligned.push({ operation, recognized: recognized[j - 1] })
      j -= 1
    } else {
      break
    }
  }
  aligned.reverse()

  // Deletions after the final recognized token are not skipped words yet: they
  // are still pending while the candidate continues speaking. A deletion
  // between two recognized tokens is a genuine possible skip.
  let lastRecognizedOperation = -1
  aligned.forEach((item, index) => {
    if (item.recognized !== undefined) lastRecognizedOperation = index
  })

  const words: LiveWordResult[] = []
  const extraWords: string[] = []
  let completedCount = 0
  let skippedCount = 0
  let incorrectCount = 0
  aligned.forEach((item, alignedIndex) => {
    if (!item.expected) {
      if (item.recognized) extraWords.push(item.recognized)
      return
    }
    if (item.operation === 'equal') {
      words.push({ expectedIndex: words.length, expected: item.expected, recognized: item.recognized, state: 'completed' })
      completedCount += 1
    } else if (item.operation === 'replace') {
      words.push({ expectedIndex: words.length, expected: item.expected, recognized: item.recognized, state: 'incorrect' })
      incorrectCount += 1
    } else if (alignedIndex > lastRecognizedOperation) {
      words.push({ expectedIndex: words.length, expected: item.expected, state: 'pending' })
    } else {
      words.push({ expectedIndex: words.length, expected: item.expected, state: 'skipped' })
      skippedCount += 1
    }
  })

  while (words.length < expected.length) {
    words.push({ expectedIndex: words.length, expected: expected[words.length], state: 'pending' })
  }
  const firstPending = words.findIndex((word) => word.state === 'pending')
  if (firstPending >= 0) words[firstPending] = { ...words[firstPending], state: 'current' }

  return {
    words,
    completionPercentage: expected.length ? Math.round((completedCount / expected.length) * 10000) / 100 : 0,
    completedCount,
    skippedCount,
    incorrectCount,
    extraWords,
  }
}
