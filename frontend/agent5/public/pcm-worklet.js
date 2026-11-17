// Batches 128-sample render quanta into ~40-50 ms frames so the STT WebSocket
// is not flooded with hundreds of tiny messages per second.
const BATCH_SAMPLES = 2048

class Agent5PcmProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.buffer = new Float32Array(BATCH_SAMPLES)
    this.filled = 0
    this.port.onmessage = (event) => {
      if (event.data === 'flush') this.flush()
    }
  }

  flush() {
    if (!this.filled) return
    this.port.postMessage(this.buffer.slice(0, this.filled))
    this.filled = 0
  }

  process(inputs) {
    const input = inputs[0]
    const channel = input && input[0]
    if (channel && channel.length) {
      let offset = 0
      while (offset < channel.length) {
        const take = Math.min(channel.length - offset, BATCH_SAMPLES - this.filled)
        this.buffer.set(channel.subarray(offset, offset + take), this.filled)
        this.filled += take
        offset += take
        if (this.filled >= BATCH_SAMPLES) this.flush()
      }
    }
    return true
  }
}

registerProcessor('agent5-pcm-processor', Agent5PcmProcessor)
