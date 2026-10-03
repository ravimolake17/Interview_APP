import type { McqStateResponse } from '../lib/types'

function formatClock(total: number): string {
  const seconds = Math.max(0, Math.floor(total))
  const mm = String(Math.floor(seconds / 60)).padStart(2, '0')
  const ss = String(seconds % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

function blockCopy(event: { preventDefault: () => void }) {
  event.preventDefault()
}

interface McqPanelProps {
  mcq: McqStateResponse
  remainingSeconds: number
  lockedOptionId: string | null
  busy: boolean
  isHr: boolean
  onSelect: (optionId: string) => void
  onSkip: () => void
}

export function McqPanel({
  mcq,
  remainingSeconds,
  lockedOptionId,
  busy,
  isHr,
  onSelect,
  onSkip,
}: McqPanelProps) {
  const question = mcq.current_question
  const total = mcq.total_questions || 0
  const current = Math.min(total, (mcq.current_index || 0) + (question ? 1 : 0))
  const locked = Boolean(lockedOptionId) || busy || isHr || mcq.status !== 'in_progress'

  return (
    <div
      className="mcq-secure"
      onCopy={blockCopy}
      onCut={blockCopy}
      onContextMenu={blockCopy}
      onDragStart={blockCopy}
      onKeyDown={(event) => {
        const key = event.key.toLowerCase()
        if ((event.ctrlKey || event.metaKey) && ['c', 'x', 'a'].includes(key)) {
          event.preventDefault()
        }
      }}
      tabIndex={-1}
    >
      <div className="mcq-toolbar">
        <span className="mcq-progress">MCQ {current || 0} of {total}</span>
        <span className={`mcq-timer${remainingSeconds <= 30 ? ' warn' : ''}`}>{formatClock(remainingSeconds)}</span>
      </div>
      {question ? (
        <>
          <p className="mcq-question" onMouseDown={blockCopy}>{question.question_text}</p>
          <div className="mcq-options" role="group" aria-label="Answer options">
            {(question.options || []).map((option) => {
              const selected = lockedOptionId === option.id
              return (
                <button
                  key={option.id}
                  type="button"
                  className={`mcq-option${selected ? ' selected' : ''}${locked ? ' locked' : ''}`}
                  disabled={locked}
                  onClick={() => onSelect(option.id)}
                >
                  <span className="mcq-option-id">{option.id}</span>
                  <span className="mcq-option-text">{option.text}</span>
                </button>
              )
            })}
          </div>
          {!isHr && (
            <button
              type="button"
              className="mcq-skip"
              disabled={locked}
              onClick={onSkip}
            >
              Skip question
            </button>
          )}
          {isHr && (
            <p className="mcq-hr-note">Candidate is taking the written test. Answers lock automatically. There is no back button.</p>
          )}
        </>
      ) : (
        <p className="mcq-question">Preparing the next question…</p>
      )}
    </div>
  )
}
