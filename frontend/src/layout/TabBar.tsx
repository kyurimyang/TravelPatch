import type { ReactNode } from 'react'
import { NavLink } from 'react-router'
import './TabBar.css'

const svgProps = {
  'aria-hidden': true,
  width: 22,
  height: 22,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.9,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const

const TABS: { to: string; label: string; icon: ReactNode }[] = [
  {
    to: '/',
    label: '오늘',
    icon: (
      <svg {...svgProps}>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </svg>
    ),
  },
  {
    to: '/trips',
    label: '여행 원단',
    icon: (
      <svg {...svgProps}>
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <path d="M3 10h18" strokeDasharray="2 2" />
        <path d="M9 4v16" strokeDasharray="2 2" />
      </svg>
    ),
  },
  {
    to: '/patchwork',
    label: '패치 모음',
    icon: (
      <svg {...svgProps}>
        <rect x="3" y="3" width="8" height="8" rx="1" />
        <rect x="13" y="3" width="8" height="8" rx="1" strokeDasharray="2 2" />
        <rect x="3" y="13" width="8" height="8" rx="1" strokeDasharray="2 2" />
        <rect x="13" y="13" width="8" height="8" rx="1" />
      </svg>
    ),
  },
]

export default function TabBar() {
  return (
    <nav className="tab-bar tp-pinked-top" aria-label="주요 메뉴">
      {/* NavLink = <a> that knows the current URL: it adds aria-current="page" and the
          "active" class when `to` matches. `end` on "/" stops it matching every path. */}
      {TABS.map((t) => (
        <NavLink key={t.to} to={t.to} end={t.to === '/'} className="tab-bar__item">
          {t.icon}
          {t.label}
        </NavLink>
      ))}
    </nav>
  )
}
