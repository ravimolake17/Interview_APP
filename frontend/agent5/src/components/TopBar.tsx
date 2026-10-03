import { BrandMark } from './BrandMark'

interface TopBarProps {
  title: string
  badge?: string
}

export function TopBar({ title, badge }: TopBarProps) {
  return (
    <header className="topbar">
      <BrandMark subtitle={title} />
      {badge ? <span className="topbar-badge">{badge}</span> : null}
    </header>
  )
}
