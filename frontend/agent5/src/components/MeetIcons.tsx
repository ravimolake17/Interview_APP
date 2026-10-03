import type { ReactNode, SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement> & { title?: string }

function IconBase({ title, children, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden={title ? undefined : true} role={title ? 'img' : 'presentation'} {...props}>
      {title ? <title>{title}</title> : null}
      {children}
    </svg>
  )
}

export function MicIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path fill="currentColor" d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2Z" />
    </IconBase>
  )
}

export function MicOffIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path fill="currentColor" d="M19 11h-1.7c0 .58-.13 1.13-.35 1.63l1.27 1.27A6.95 6.95 0 0 0 19 11Zm-5.16.84 1.55 1.55c.4-.57.61-1.25.61-1.99V6a3 3 0 0 0-5.94-.5l1.67 1.67c.1-.05.2-.08.32-.08.83 0 1.5.67 1.5 1.5v3.16c0 .12-.03.23-.08.33ZM4.27 3 3 4.27l6.01 6.01V11c0 1.66 1.34 3 3 3 .23 0 .45-.03.67-.08L14.73 16c-.66.33-1.39.53-2.16.58V21h2v-3.08c.81-.1 1.57-.35 2.26-.73L19.73 21 21 19.73 4.27 3Z" />
    </IconBase>
  )
}

export function CamIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path fill="currentColor" d="M17 10.5V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-3.5l4 4v-11l-4 4Z" />
    </IconBase>
  )
}

export function CamOffIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path fill="currentColor" d="M21 6.5 17 10.5V7a2 2 0 0 0-2-2H8.82l12.47 12.47 1.41-1.41L3.27 3 1.86 4.41 3.59 6.14A2 2 0 0 0 2 8v10a2 2 0 0 0 2 2h11c.72 0 1.34-.38 1.69-.95L21 21.5 22.41 20.09 21 18.68V6.5Z" />
    </IconBase>
  )
}

export function HangUpIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path fill="currentColor" d="M6.62 10.79c1.44 2.83 3.76 5.15 6.59 6.59l2.2-2.2c.28-.28.67-.36 1.02-.25 1.12.37 2.32.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1C10.4 21 3 13.6 3 4c0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2Z" transform="rotate(135 12 12)" />
    </IconBase>
  )
}

export function SpeakerOffIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path fill="currentColor" d="M16.5 12a4.5 4.5 0 0 0-2.36-3.97l1.06-1.06A5.98 5.98 0 0 1 18.5 12c0 .95-.22 1.85-.6 2.65l-1.1-1.1c.19-.48.3-1 .3-1.55ZM4.27 3 3 4.27 7.73 9H3v6h4l5 5V13.27l5.73 5.73 1.27-1.27L4.27 3ZM14 3.23v2.06c1.74.5 3.14 1.8 3.74 3.48l1.7-1.7A7.98 7.98 0 0 0 14 3.23ZM12 7.73 10.27 6 12 4.27v3.46Z" />
    </IconBase>
  )
}

export function PauseIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path fill="currentColor" d="M8 5h3v14H8V5Zm5 0h3v14h-3V5Z" />
    </IconBase>
  )
}

export function PinIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path fill="currentColor" d="M14 4v4h4l-5 5-5-5h4V4H14Zm-6 9 5 5v4h2v-4h4l-5-5-5 5h4v-4H8v4Z" />
    </IconBase>
  )
}

export function PlayIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path fill="currentColor" d="M8 5v14l11-7L8 5Z" />
    </IconBase>
  )
}

export function SkipIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path fill="currentColor" d="M6 18 14.5 12 6 6v12Zm9-12v12h2V6h-2Z" />
    </IconBase>
  )
}

export function NextIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path fill="currentColor" d="m6.5 5.5 8 6.5-8 6.5v-13Zm9 0h2v13h-2v-13Z" />
    </IconBase>
  )
}

export function PersonIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path fill="currentColor" d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4Zm0 2c-4.42 0-8 2.24-8 5v1h16v-1c0-2.76-3.58-5-8-5Z" />
    </IconBase>
  )
}

export function BotIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path fill="currentColor" d="M12 2a2 2 0 0 1 2 2v1h3a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V8a3 3 0 0 1 3-3h3V4a2 2 0 0 1 2-2Zm-3.5 8.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Zm7 0a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3ZM9 16h6v1.5H9V16Z" />
    </IconBase>
  )
}

export function AddIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path fill="currentColor" d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5Z" />
    </IconBase>
  )
}

export function FullscreenIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path fill="currentColor" d="M7 14H5v5h5v-2H7v-3Zm12 0h-2v3h-3v2h5v-5ZM7 5h3V3H5v5h2V5Zm12-2h-5v2h3v3h2V3Z" />
    </IconBase>
  )
}

export function MoreIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path fill="currentColor" d="M6 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm6 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm6 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z" />
    </IconBase>
  )
}

type MeetFabProps = {
  label: string
  onClick?: () => void
  disabled?: boolean
  variant?: 'default' | 'off' | 'danger' | 'primary'
  children: ReactNode
}

export function MeetFab({ label, onClick, disabled, variant = 'default', children }: MeetFabProps) {
  return (
    <button
      type="button"
      className={`meet-fab meet-fab-${variant}`}
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
    >
      <span className="meet-fab-icon">{children}</span>
      <span className="meet-fab-label">{label}</span>
    </button>
  )
}
