const DB_NAME = 'agent5-recording-queue-v3'
const STORE = 'chunks'

export interface RecordingChunkQueueItem {
  key: string
  sessionId: string
  sequence: number
  segmentId: string
  segmentSequence: number
  isFinal: boolean
  capturedAt: string
  durationMs: number
  checksum: string
  blob: Blob
  mimeType: string
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: 'key' })
        store.createIndex('session', 'sessionId')
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('IndexedDB open failed'))
  })
}

export async function putChunk(item: RecordingChunkQueueItem): Promise<void> {
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const transaction = db.transaction(STORE, 'readwrite', { durability: 'strict' })
    transaction.objectStore(STORE).put(item)
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error ?? new Error('IndexedDB write failed'))
    transaction.onabort = () => reject(transaction.error ?? new Error('IndexedDB write aborted'))
  })
  db.close()
}

export async function deleteChunk(key: string): Promise<void> {
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const transaction = db.transaction(STORE, 'readwrite', { durability: 'strict' })
    transaction.objectStore(STORE).delete(key)
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error ?? new Error('IndexedDB delete failed'))
    transaction.onabort = () => reject(transaction.error ?? new Error('IndexedDB delete aborted'))
  })
  db.close()
}

export async function getChunks(sessionId: string): Promise<RecordingChunkQueueItem[]> {
  const db = await openDb()
  const items = await new Promise<RecordingChunkQueueItem[]>((resolve, reject) => {
    const transaction = db.transaction(STORE, 'readonly')
    const request = transaction.objectStore(STORE).index('session').getAll(sessionId)
    request.onsuccess = () => resolve((request.result as RecordingChunkQueueItem[]).sort((a, b) => a.sequence - b.sequence))
    request.onerror = () => reject(request.error ?? new Error('IndexedDB read failed'))
  })
  db.close()
  return items
}
