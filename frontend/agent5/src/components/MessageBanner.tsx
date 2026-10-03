import type { MessageKind } from '../lib/types'

interface MessageBannerProps {
  text: string
  kind: MessageKind
  onDismiss?: () => void
}

export function MessageBanner({ text, kind, onDismiss }: MessageBannerProps) {
  if (!text) return null
  return (
    <div className={`message-banner ${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      <span>{text}</span>
      {onDismiss && (
        <button className="icon-button" type="button" onClick={onDismiss} aria-label="Dismiss message">×</button>
      )}
    </div>
  )
}
