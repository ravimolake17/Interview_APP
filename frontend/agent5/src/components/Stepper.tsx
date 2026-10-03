const STEPS = ['Registration', 'Devices', 'Enrollment', 'Interview', 'Report']

export function Stepper({ current }: { current: number }) {
  return (
    <nav className="steps" aria-label="Candidate workflow">
      {STEPS.map((step, index) => (
        <div key={step} className={`step ${index < current ? 'done' : index === current ? 'active' : ''}`}>
          <span className="step-index">{index < current ? '✓' : index + 1}</span>
          <span>{step}</span>
        </div>
      ))}
    </nav>
  )
}
