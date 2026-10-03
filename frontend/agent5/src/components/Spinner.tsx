export function Spinner({ label = 'Working' }: { label?: string }) {
  return (
    <span className="spinner-wrap" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </span>
  )
}
