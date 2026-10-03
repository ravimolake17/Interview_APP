export type WebRtcSignalPayload =
  | { signal_type: 'offer'; sdp: RTCSessionDescriptionInit }
  | { signal_type: 'answer'; sdp: RTCSessionDescriptionInit }
  | { signal_type: 'ice'; candidate: RTCIceCandidateInit | null }

type SignalSender = (payload: WebRtcSignalPayload) => void

const ICE_SERVERS: RTCIceServer[] = [
  { urls: 'stun:stun.l.google.com:19302' },
  { urls: 'stun:stun1.l.google.com:19302' },
]

export class RoomPeerConnection {
  private pc: RTCPeerConnection | null = null
  private makingOffer = false
  private ignoreOffer = false
  private pendingIce: RTCIceCandidateInit[] = []

  constructor(
    private readonly localStream: MediaStream,
    private readonly isOfferer: boolean,
    private readonly onRemoteStream: (stream: MediaStream | null) => void,
    private readonly sendSignal: SignalSender,
  ) {}

  connect(): void {
    if (this.pc) return
    const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS })
    this.pc = pc
    this.localStream.getTracks().forEach((track) => pc.addTrack(track, this.localStream))
    pc.ontrack = (event) => {
      const stream = event.streams[0] ?? new MediaStream([event.track])
      this.onRemoteStream(stream)
    }
    pc.onicecandidate = (event) => {
      if (!event.candidate) return
      this.sendSignal({ signal_type: 'ice', candidate: event.candidate.toJSON() })
    }
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === 'failed') {
        this.onRemoteStream(null)
      }
      if (pc.connectionState === 'closed') {
        this.onRemoteStream(null)
      }
    }
    pc.onnegotiationneeded = () => {
      if (this.isOfferer) {
        void this.makeOffer()
      }
    }
  }

  private async flushPendingIce(): Promise<void> {
    const pc = this.pc
    if (!pc?.remoteDescription) return
    const pending = [...this.pendingIce]
    this.pendingIce = []
    for (const candidate of pending) {
      try {
        await pc.addIceCandidate(candidate)
      } catch {
        /* ignore stale ICE */
      }
    }
  }

  async makeOffer(): Promise<void> {
    const pc = this.pc
    if (!pc || !this.isOfferer) return
    try {
      this.makingOffer = true
      if (pc.signalingState === 'have-local-offer') {
        await pc.setLocalDescription({ type: 'rollback' } as RTCSessionDescriptionInit)
      }
      if (pc.signalingState !== 'stable') return
      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)
      if (pc.localDescription) {
        this.sendSignal({ signal_type: 'offer', sdp: pc.localDescription })
      }
    } finally {
      this.makingOffer = false
    }
  }

  async handleSignal(signal: WebRtcSignalPayload): Promise<void> {
    const pc = this.pc
    if (!pc) return

    if (signal.signal_type === 'offer') {
      const offerCollision = this.makingOffer || pc.signalingState !== 'stable'
      this.ignoreOffer = !this.isOfferer && offerCollision
      if (this.ignoreOffer) return
      await pc.setRemoteDescription(signal.sdp)
      await this.flushPendingIce()
      const answer = await pc.createAnswer()
      await pc.setLocalDescription(answer)
      if (pc.localDescription) {
        this.sendSignal({ signal_type: 'answer', sdp: pc.localDescription })
      }
      return
    }

    if (signal.signal_type === 'answer') {
      if (pc.signalingState === 'have-local-offer') {
        await pc.setRemoteDescription(signal.sdp)
        await this.flushPendingIce()
      }
      return
    }

    if (signal.signal_type === 'ice' && signal.candidate) {
      if (!pc.remoteDescription) {
        this.pendingIce.push(signal.candidate)
        return
      }
      try {
        await pc.addIceCandidate(signal.candidate)
      } catch {
        /* ignore stale ICE */
      }
    }
  }

  close(): void {
    this.pc?.close()
    this.pc = null
    this.pendingIce = []
    this.onRemoteStream(null)
  }
}
