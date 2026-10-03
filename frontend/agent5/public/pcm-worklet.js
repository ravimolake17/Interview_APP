class Agent5PcmProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0]
    if (input && input[0] && input[0].length) {
      this.port.postMessage(input[0].slice())
    }
    return true
  }
}

registerProcessor('agent5-pcm-processor', Agent5PcmProcessor)
