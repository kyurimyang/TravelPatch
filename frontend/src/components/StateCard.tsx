import type { ReactNode } from 'react'
import cancel from '../assets/patches/hole-cancel.svg'
import mend from '../assets/patches/patch-mend.svg'
import roadwork from '../assets/patches/hole-roadwork.svg'
import wind from '../assets/patches/hole-wind.svg'
import './StateCard.css'

// One look for every "nothing here / something went wrong" moment, in the patchwork language:
// empty = a patch still to sew, error = a torn hole, not found = a road closed, offline = wind.
const ART = { empty: mend, error: cancel, notfound: roadwork, offline: wind } as const

type Props = {
  kind: keyof typeof ART
  title: string
  children?: ReactNode
  /** Buttons / links, stacked under the text. */
  actions?: ReactNode
}

export function StateCard({ kind, title, children, actions }: Props) {
  return (
    <section className={`state-card state-card--${kind} tp-fabric`} role={kind === 'error' ? 'alert' : undefined}>
      <img src={ART[kind]} alt="" aria-hidden="true" />
      <h2>{title}</h2>
      {children && <div className="state-card__text">{children}</div>}
      {actions && <div className="state-card__actions">{actions}</div>}
    </section>
  )
}
