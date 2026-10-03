import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MessageBanner } from '../MessageBanner'
import { StatusPill } from '../StatusPill'

describe('status components', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  it('renders API failures as an alert and dismisses them', () => {
    const dismiss = vi.fn()
    act(() => {
      root.render(
        <MessageBanner
          text="Camera permission denied"
          kind="error"
          onDismiss={dismiss}
        />,
      )
    })

    const alert = container.querySelector('[role="alert"]')
    expect(alert?.textContent).toContain('Camera permission denied')
    const button = container.querySelector<HTMLButtonElement>('button[aria-label="Dismiss message"]')
    expect(button).not.toBeNull()
    act(() => button?.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    expect(dismiss).toHaveBeenCalledOnce()
  })

  it('does not render an empty message', () => {
    act(() => root.render(<MessageBanner text="" kind="notice" />))
    expect(container.innerHTML).toBe('')
  })

  it('renders risk state semantically through the expected class', () => {
    act(() => root.render(<StatusPill label="High risk" state="bad" />))
    const pill = container.querySelector('.pill.bad')
    expect(pill?.textContent).toBe('High risk')
  })
})
