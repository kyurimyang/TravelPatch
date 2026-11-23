import type { ReactNode } from 'react'
import { Link, useNavigate } from 'react-router'
import { exitFlow, type Flow } from '../lib/nav'

// "그대로 둘게요" / "오늘 일정으로": leaves the flow back to where it was opened (see lib/nav).
// Still an <a href="/"> so it works as a link (new tab, no JS) and reads as one.
export function ExitLink({ flow, className, children }: { flow: Flow; className?: string; children: ReactNode }) {
  const navigate = useNavigate()
  return (
    <Link
      className={className}
      to="/"
      onClick={(e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
        e.preventDefault()
        exitFlow(navigate, flow)
      }}
    >
      {children}
    </Link>
  )
}
