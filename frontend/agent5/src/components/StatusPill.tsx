interface StatusPillProps {
  label: string
  state?: 'neutral' | 'ok' | 'bad' | 'warning'
}

export function StatusPill({ label, state = 'neutral' }: StatusPillProps) {
  return <span className={`pill ${state}`}>{label}</span>
}
